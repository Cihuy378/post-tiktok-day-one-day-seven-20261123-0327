// Entry program for make.fun's "Day one, day seven" TikTok bounty.
//
// The entry itself is a short video posted on TikTok: the same tiny
// agent-built game on the day it was made and after a week of daily
// updates. This program's only job is to hand the house the video's
// address: it copies VIDEO.json from the repository root into the output
// directory, where the gate reads it and scores the video's views and
// interactions from TikTok directly. Nothing this program writes about
// the video is scored.
//
// It runs under Node 22 with the standard library only: no network, no
// wall clock, no files outside the repository, and two runs always write
// the same bytes (a plain file copy).
//
// Local check (from the repository root):
//   mkdir -p out && MAKEFUN_BOT_DIR=. MAKEFUN_OUTPUT_DIR=out node main.ts
// Afterwards out/VIDEO.json is byte for byte this directory's VIDEO.json.

import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const repoRoot = process.env.MAKEFUN_BOT_DIR ?? "/bot";
const outDir = process.env.MAKEFUN_OUTPUT_DIR ?? "/output";
const videoFile = "VIDEO.json";

const source = join(repoRoot, videoFile);
if (!existsSync(source)) {
  console.error(`missing ${videoFile} in ${repoRoot}; nothing to hand in`);
  process.exit(1);
}

mkdirSync(outDir, { recursive: true });
copyFileSync(source, join(outDir, videoFile));
