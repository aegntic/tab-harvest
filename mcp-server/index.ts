import { YoutubeTranscript } from "youtube-transcript";
import { Innertube } from "youtubei.js";
import { MCPServer } from "mcp-use";
import { z } from "zod";

const MAX_TEXT = 60_000;

const server = new MCPServer({
  name: "tab-harvest",
  title: "Tab Harvest",
  version: "1.2.0",
  description:
    "Cloud-viable tools from the tab-harvest project: YouTube transcript, metadata, search and channel tools, plus public tweet extraction. Browser-tab harvesting itself runs locally through the tab-harvest CLI.",
});

function extractVideoId(input: string): string {
  const raw = input.trim();
  if (/^[\w-]{11}$/.test(raw)) return raw;
  const m =
    raw.match(/[?&]v=([\w-]{11})/) ??
    raw.match(/youtu\.be\/([\w-]{11})/) ??
    raw.match(/shorts\/([\w-]{11})/) ??
    raw.match(/embed\/([\w-]{11})/);
  if (m) return m[1];
  throw new Error(`Could not extract a YouTube video id from: ${input}`);
}

function extractTweetId(input: string): string {
  const raw = input.trim();
  if (/^\d{1,25}$/.test(raw)) return raw;
  const m = raw.match(/status\/(\d{1,25})/);
  if (m) return m[1];
  throw new Error(`Could not extract a tweet id from: ${input}`);
}

function mcpResult(obj: unknown) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(obj) }],
    structuredContent: obj,
  };
}

server.tool(
  {
    name: "server-info",
    title: "Server info",
    description:
      "Describe this server: what it hosts, what runs locally vs in the cloud",
    inputSchema: z.object({}),
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
  },
  async () => {
    const info = {
      server: "tab-harvest",
      version: "1.2.0",
      cloud_tools: [
        "get-youtube-transcript",
        "get-video-metadata",
        "search-youtube",
        "get-channel-videos",
        "get-tweet",
      ],
      local_only:
        "harvesting open browser tabs via CDP runs locally with the tab-harvest CLI (pip install tab-harvest), not on this server",
    };
    return mcpResult(info);
  }
);

server.tool(
  {
    name: "get-youtube-transcript",
    title: "Get YouTube transcript",
    description:
      "Fetch the spoken-content transcript of a YouTube video (auto-generated or manual subtitles) as plain text",
    inputSchema: z.object({
      url: z.string().describe("YouTube video URL or 11-char video id"),
      language: z
        .string()
        .default("en")
        .describe("Subtitle language code, e.g. en, de, es"),
    }),
    outputSchema: z.object({
      url: z.string(),
      language: z.string(),
      chars: z.number(),
      transcript: z.string(),
    }),
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: true },
  },
  async ({ url, language }) => {
    const videoId = extractVideoId(url);
    const cues = await YoutubeTranscript.fetchTranscript(videoId, language);
    if (!cues || cues.length === 0) {
      throw new Error(
        `No transcript available for ${videoId} in language '${language}'`
      );
    }
    const text = cues
      .map((c) => c.text.replace(/&amp;/g, "&").replace(/&#39;/g, "'"))
      .join(" ")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, MAX_TEXT);
    const result = {
      url: `https://youtu.be/${videoId}`,
      language,
      chars: text.length,
      transcript: text,
    };
    return mcpResult(result);
  }
);

server.tool(
  {
    name: "get-video-metadata",
    title: "Get video metadata",
    description:
      "Fetch YouTube video metadata: title, channel, duration, views and description",
    inputSchema: z.object({
      url: z.string().describe("YouTube video URL or 11-char video id"),
    }),
    outputSchema: z.object({
      title: z.string(),
      channel: z.string(),
      duration_seconds: z.number(),
      views: z.number().nullable(),
      description: z.string(),
    }),
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: true },
  },
  async ({ url }) => {
    const videoId = extractVideoId(url);
    const yt = await Innertube.create();
    const info = await yt.getInfo(videoId);
    const b = info.basic_info;
    const result = {
      title: String(b.title ?? ""),
      channel: String(b.author ?? ""),
      duration_seconds: Number(b.duration ?? 0),
      views: b.view_count == null ? null : Number(b.view_count),
      description: String(b.short_description ?? "").slice(0, 4000),
    };
    return mcpResult(result);
  }
);

function mapVideo(v: any) {
  const title = typeof v.title === "string" ? v.title : v.title?.text ?? "";
  return {
    video_id: String(v.video_id ?? v.id ?? ""),
    title: String(title),
    channel: String(v.author?.name ?? v.author ?? ""),
    views: v.view_count == null ? null : Number(v.view_count),
    length_seconds:
      v.length?.seconds == null
        ? v.duration?.seconds == null
          ? null
          : Number(v.duration.seconds)
        : Number(v.length.seconds),
  };
}

server.tool(
  {
    name: "search-youtube",
    title: "Search YouTube",
    description:
      "Search YouTube for videos matching a query, with view counts and durations",
    inputSchema: z.object({
      query: z.string().describe("Search query"),
      limit: z
        .number()
        .int()
        .min(1)
        .max(40)
        .default(10)
        .describe("Max results to return"),
    }),
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: true },
  },
  async ({ query, limit }) => {
    const yt = await Innertube.create();
    const results = await yt.search(query);
    const raw: any[] = (results as any).videos ?? (results as any).items ?? [];
    const videos = raw.slice(0, limit).map(mapVideo);
    return mcpResult({ query, count: videos.length, videos });
  }
);

server.tool(
  {
    name: "get-channel-videos",
    title: "Get channel videos",
    description:
      "List the latest videos from a YouTube channel (handle like @mkbhd or channel URL)",
    inputSchema: z.object({
      channel: z
        .string()
        .describe("Channel @handle, channel URL, or channel id"),
      limit: z
        .number()
        .int()
        .min(1)
        .max(40)
        .default(10)
        .describe("Max results to return"),
    }),
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: true },
  },
  async ({ channel, limit }) => {
    const yt = await Innertube.create();
    const ch = await yt.getChannel(channel);
    const raw: any[] = (ch as any).videos?.items ?? (ch as any).videos ?? [];
    const videos = raw.slice(0, limit).map(mapVideo);
    return mcpResult({
      channel: String((ch as any).name ?? channel),
      count: videos.length,
      videos,
    });
  }
);

async function fetchTweetViaSyndication(id: string) {
  const res = await fetch(
    `https://cdn.syndication.twimg.com/tweet-result?id=${id}&lang=en&token=x`,
    { headers: { "User-Agent": "Mozilla/5.0 (compatible; tab-harvest/1.2)" } }
  );
  if (!res.ok) throw new Error(`syndication http ${res.status}`);
  const j: any = await res.json();
  return {
    id: String(j.id ?? id),
    author: String(j.user?.screen_name ?? j.user?.name ?? ""),
    text: String(j.text ?? ""),
    created_at: String(j.created_at ?? ""),
    likes: j.favorite_count == null ? null : Number(j.favorite_count),
    parent_id: j.parent?.id_str ? String(j.parent.id_str) : null,
    photos: Array.isArray(j.mediaDetails)
      ? j.mediaDetails.map((m: any) => String(m.media_url_https))
      : [],
  };
}

async function fetchTweetViaOembed(id: string) {
  const res = await fetch(
    `https://publish.twitter.com/oembed?url=https://twitter.com/i/web/status/${id}`
  );
  if (!res.ok) throw new Error(`oembed http ${res.status}`);
  const j: any = await res.json();
  const text = String(j.html ?? "")
    .replace(/<[^>]+>/g, " ")
    .replace(/&mdash;/g, "—")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
  return {
    id,
    author: String(j.author_name ?? ""),
    text,
    created_at: "",
    likes: null,
    parent_id: null,
    photos: [],
  };
}

server.tool(
  {
    name: "get-tweet",
    title: "Get tweet",
    description:
      "Fetch a public tweet or the first post of a thread: author, text, timestamp, likes, photos. Works for public tweets only (no login-walled content).",
    inputSchema: z.object({
      url: z
        .string()
        .describe("Tweet URL (x.com or twitter.com .../status/<id>) or raw id"),
    }),
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: true },
  },
  async ({ url }) => {
    const id = extractTweetId(url);
    let tweet: Awaited<ReturnType<typeof fetchTweetViaSyndication>>;
    try {
      tweet = await fetchTweetViaSyndication(id);
    } catch {
      tweet = await fetchTweetViaOembed(id);
    }
    return mcpResult(tweet);
  }
);

export default server;
