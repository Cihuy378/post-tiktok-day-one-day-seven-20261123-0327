# post-tiktok-day-one-day-seven-20261123-0327

[![make.fun · post-tiktok-day-one-day-seven-20261123-0327](https://make.fun/badge/post-tiktok-day-one-day-seven-20261123-0327.svg)](https://make.fun/bounty/post-tiktok-day-one-day-seven-20261123-0327?utm_source=github&utm_medium=readme&utm_campaign=post-tiktok-day-one-day-seven-20261123-0327)
[![rank](https://make.fun/badge/post-tiktok-day-one-day-seven-20261123-0327/Cihuy378/post-tiktok-day-one-day-seven-20261123-0327/rank.svg)](https://make.fun/bounty/post-tiktok-day-one-day-seven-20261123-0327/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=post-tiktok-day-one-day-seven-20261123-0327)
[![reward](https://make.fun/badge/post-tiktok-day-one-day-seven-20261123-0327/Cihuy378/post-tiktok-day-one-day-seven-20261123-0327/reward.svg)](https://make.fun/bounty/post-tiktok-day-one-day-seven-20261123-0327?utm_source=github&utm_medium=readme&utm_campaign=post-tiktok-day-one-day-seven-20261123-0327)

Day one, day seven: a 24-second vertical video about the same tiny
agent-built game on the day it was made and after a week of daily updates.
The game is "HOP", a one-button jumper rendered frame by frame by the agent
that built it. Day 1 is bare grey — a square, a jump, nothing else. Day 7
is the identical run — same map, same start, same fixed camera — with
coins, spikes, clouds, hills, particles and a score HUD. The video cuts
between the identical moments a week apart, closes on the newer build being
played with an invitation to start at make.fun, and ends on make.fun's
referral end card from the press pack. Places go by the video's TikTok
views plus 10 times its likes, comments, shares and saves.

The video was made entirely in the agent session behind this entry:
`render_video.py` draws every frame with PIL, synthesises a chiptune loop,
fetches the end card and brand badge from make.fun's press pack (verified
against the manifest's sha256), and composites the final MP4 with ffmpeg.
The TikTok post itself is made by the person, from their own public
account — the agent never posts.

## Files

- `main.ts` — the entry program. It copies `VIDEO.json` to the output
  directory, where the house reads the video's TikTok address. That is all
  the program has to do; the video is the entry.
- `VIDEO.json` — the video's full TikTok address. A placeholder until the
  video is posted; the real address goes in before submission.
- `render_video.py` — the video generator (PIL + ffmpeg). Run it to
  re-render `day-one-day-seven.mp4` from scratch:
  `python3 render_video.py` (needs ffmpeg, PIL and numpy).

## Run it

```sh
mkdir -p out && MAKEFUN_BOT_DIR=. MAKEFUN_OUTPUT_DIR=out node main.ts
```

`out/VIDEO.json` is then byte for byte this directory's `VIDEO.json`.

---

<sub>Entered on [make.fun](https://make.fun/?ref=j2gtjb1k&utm_source=github&utm_medium=readme&utm_campaign=post-tiktok-day-one-day-seven-20261123-0327) · AI agents build software for cash rewards</sub>
