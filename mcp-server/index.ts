import { YoutubeTranscript } from "youtube-transcript";
import { Innertube } from "youtubei.js";
import { MCPServer } from "mcp-use";
import { z } from "zod";

const MAX_TEXT = 60_000;

const server = new MCPServer({
  name: "tab-harvest",
  title: "Tab Harvest",
  version: "1.1.0",
  description:
    "Cloud-viable tools from the tab-harvest project: YouTube transcript and metadata extraction. Browser-tab harvesting itself runs locally through the tab-harvest CLI.",
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

server.tool(
  {
    name: "server-info",
    description:
      "Describe this server: what it hosts, what runs locally vs in the cloud",
    inputSchema: z.object({}),
    annotations: { readOnlyHint: true },
  },
  async () => {
    const info = {
      server: "tab-harvest",
      version: "1.1.0",
      cloud_tools: ["get-youtube-transcript", "get-video-metadata"],
      local_only:
        "harvesting open browser tabs via CDP runs locally with the tab-harvest CLI (pip install tab-harvest), not on this server",
    };
    return {
      content: [{ type: "text", text: JSON.stringify(info) }],
      structuredContent: info,
    };
  }
);

server.tool(
  {
    name: "get-youtube-transcript",
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
    annotations: { readOnlyHint: true, openWorldHint: true },
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
    return {
      content: [{ type: "text", text: JSON.stringify(result) }],
      structuredContent: result,
    };
  }
);

server.tool(
  {
    name: "get-video-metadata",
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
    annotations: { readOnlyHint: true, openWorldHint: true },
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
    return {
      content: [{ type: "text", text: JSON.stringify(result) }],
      structuredContent: result,
    };
  }
);

export default server;
