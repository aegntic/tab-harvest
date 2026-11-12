import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { readFile, readdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MCPServer } from "mcp-use";
import { z } from "zod";

const run = promisify(execFile);
const MAX_TEXT = 60_000;

const server = new MCPServer({
  name: "tab-harvest",
  title: "Tab Harvest",
  version: "1.0.0",
  description:
    "Cloud-viable tools from the tab-harvest project: YouTube transcript and metadata extraction via yt-dlp. Browser-tab harvesting itself runs locally through the tab-harvest CLI.",
});

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
      version: "1.0.0",
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

async function transcriptText(url: string, language: string): Promise<string> {
  const out = join(tmpdir(), `tabharvest-${Date.now()}`);
  await run("yt-dlp", [
    "--skip-download",
    "--write-auto-subs",
    "--write-subs",
    "--sub-langs",
    language,
    "--convert-subs",
    "vtt",
    "-o",
    join(out, "%(id)s"),
    url,
  ]);
  const files = await readdir(out);
  const vtt = files.find((f) => f.endsWith(".vtt"));
  if (!vtt) throw new Error(`No subtitles found for language '${language}'`);
  const raw = await readFile(join(out, vtt), "utf8");
  // strip WebVTT cue numbering, timestamps and metadata lines -> plain text
  const text = raw
    .split("\n")
    .filter(
      (l) =>
        !l.startsWith("WEBVTT") &&
        !l.startsWith("Kind:") &&
        !l.startsWith("Language:") &&
        !l.includes("-->") &&
        !/^\d+$/.test(l.trim()) &&
        l.trim() !== ""
    )
    .join(" ")
    .replace(/<[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, MAX_TEXT);
  if (!text) throw new Error("Subtitle track found but contained no text");
  return text;
}

server.tool(
  {
    name: "get-youtube-transcript",
    description:
      "Fetch the spoken-content transcript of a YouTube video (auto-generated or manual subtitles) as plain text",
    inputSchema: z.object({
      url: z.string().url().describe("YouTube video URL"),
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
    const transcript = await transcriptText(url, language);
    const result = { url, language, chars: transcript.length, transcript };
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
      "Fetch YouTube video metadata: title, channel, duration, views, upload date and description",
    inputSchema: z.object({
      url: z.string().url().describe("YouTube video URL"),
    }),
    outputSchema: z.object({
      title: z.string(),
      channel: z.string(),
      duration_seconds: z.number(),
      views: z.number().nullable(),
      upload_date: z.string(),
      description: z.string(),
    }),
    annotations: { readOnlyHint: true, openWorldHint: true },
  },
  async ({ url }) => {
    const { stdout } = await run("yt-dlp", ["--dump-single-json", "--no-warnings", url]);
    const meta = JSON.parse(stdout);
    const result = {
      title: String(meta.title ?? ""),
      channel: String(meta.channel ?? meta.uploader ?? ""),
      duration_seconds: Number(meta.duration ?? 0),
      views: meta.view_count == null ? null : Number(meta.view_count),
      upload_date: String(meta.upload_date ?? ""),
      description: String(meta.description ?? "").slice(0, 4000),
    };
    return {
      content: [{ type: "text", text: JSON.stringify(result) }],
      structuredContent: result,
    };
  }
);

export default server;
