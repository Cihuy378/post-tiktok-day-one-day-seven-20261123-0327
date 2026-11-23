#!/usr/bin/env python3
"""Render the "Day one, day seven" TikTok video for make.fun bounty
post-tiktok-day-one-day-seven-20261123-0327.

What it makes: a 24 s vertical (1080x1920, 30 fps) video about the same tiny
agent-built game on the day it was made and after a week of daily updates.
The game is "HOP", a one-button jumper rendered frame by frame with PIL:
the hero runs across one fixed map and jumps the same gaps. Day 1 is bare
grey (a square, a jump, nothing else); day 7 is the identical run with
coins, spikes, clouds, hills, particles and a score HUD. The camera never
moves, so the change is the whole story. The video ends with make.fun's
referral end card from the press pack, our referral code typed in.

Pipeline: render game frames -> base.mp4 -> composite (brand badge, blurred
end card, referral code, chiptune audio) -> day-one-day-seven.mp4.

Run: python3 render_video.py   (needs ffmpeg + PIL + numpy on PATH)
Output: day-one-day-seven.mp4 next to this script.
"""

import hashlib
import math
import os
import random
import subprocess
import sys
import urllib.request
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- constants

W, H, FPS, DUR = 1080, 1920, 30, 24.0
N_FRAMES = int(DUR * FPS)
SCROLL = 400.0            # world scroll speed, px/s
GROUND_Y = 1300           # top edge of the ground
HERO_X = 380              # hero left edge (fixed: the camera never moves)
HERO_CX = HERO_X + 45     # hero centre x
HERO_SIZE = 90
JUMP_T0 = [1.2, 4.5, 8.0, 11.5, 14.0, 17.0, 19.5]  # jump start times
JUMP_AIR, JUMP_H = 0.9, 240.0
GAP_HALF = 70
MAGENTA = (196, 28, 131)
INK = (25, 20, 25)

# (start, end, version) -- the cuts. Game time is continuous across cuts:
# the hero is at the same place in both versions, so each cut compares the
# identical moment a week apart.
SEGMENTS = [(0.0, 3.0, "day1"), (3.0, 7.0, "day7"), (7.0, 10.0, "day1"),
            (10.0, 15.0, "day7"), (15.0, 24.0, "day7")]

# On-screen copy per segment: (pill, hook lines, subtitle lines).
COPY = {
    (0.0, 3.0): ("DAY 1", ["MY AI AGENT", "BUILT A GAME."],
                 ["day 1: just a square and a jump"]),
    (3.0, 7.0): ("DAY 7", [], ["same map. same jump.", "7 days later."]),
    (7.0, 10.0): ("DAY 1", [], ["watch the same jump again..."]),
    (10.0, 15.0): ("DAY 7", [], ["coins. spikes. a score. a world."]),
    (15.0, 24.0): ("DAY 7", ["7 DAYS OF DAILY UPDATES.",
                              "START YOURS AT make.fun"],
                   ["built by an AI agent, one update a day"]),
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = "/tmp/day7build"
PRESS_DIR = "/tmp/press"
FINAL_MP4 = os.path.join(SCRIPT_DIR, "day-one-day-seven.mp4")
REFERRAL_CODE = "j2gtjb1k"

PRESS_FILES = {
    "card-9x16.webm": (
        "https://make.fun/press/referral-card/9x16/makefun-card-9x16-transparent.webm",
        "286b76c671fa3bf3b1580a7c71675d7b7e502f4fb374b56d30f1104044808cd1"),
    "badge-9x16.png": (
        "https://make.fun/press/brand-badge/9x16/makefun-badge-9x16.png",
        "5633c94aeb8773339950f41b9299586f0b5a13594b3076a0c50e8ab0541e9772"),
}

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


def font(size):
    return ImageFont.truetype(FONT_BOLD, size)


F_HOOK, F_CTA = font(76), font(60)
F_PILL, F_SUB, F_SCORE = font(52), font(46), font(52)

# ------------------------------------------------------------ choreography
# Gaps sit where the hero is mid-jump: gap centre passes the hero's centre
# exactly at each jump's apex, so the same jump clears the same gap in both
# versions. Coins arc over each gap; spikes guard the gap's approach.

GAPS = [HERO_CX + SCROLL * (t0 + JUMP_AIR / 2) for t0 in JUMP_T0]
SPIKES = [g - 140 for g in GAPS]                       # spike-group left edge
COINS = []                                             # (world_x, centre_y)
for g in GAPS:
    for dx, lift in ((-90, 200), (0, 280), (90, 200)):
        COINS.append((g + dx, GROUND_Y - lift))
FLOWERS = [150 + 317 * k for k in range(32)]           # flower world-x
CLOUDS = [(100, 160, 0.9), (700, 185, 0.6), (1300, 155, 1.0),
          (1900, 190, 0.7)]                            # (world_x, y, scale)


def hero_jump(t):
    """(height offset px, vertical speed px/s) of the hero at time t."""
    for t0 in JUMP_T0:
        if t0 <= t < t0 + JUMP_AIR:
            u = (t - t0) / JUMP_AIR
            return -4 * JUMP_H * u * (1 - u), -4 * JUMP_H * (1 - 2 * u) / JUMP_AIR
    return 0.0, 0.0


def landing_squash(t):
    """True briefly after a landing, for a squash frame."""
    return any(t0 + JUMP_AIR <= t < t0 + JUMP_AIR + 0.12 for t0 in JUMP_T0)


def coins_collected(t):
    return sum(1 for wx, _ in COINS if (wx - HERO_CX) / SCROLL <= t)


def version_at(t):
    for a, b, v in SEGMENTS:
        if a <= t < b:
            return v
    return "day7"


def copy_at(t):
    for (a, b), c in COPY.items():
        if a <= t < b:
            return c
    return COPY[(15.0, 24.0)]


# ------------------------------------------------------- precomputed art
def sky_day7():
    top = np.array([110, 193, 245], dtype=np.float32)
    bot = np.array([223, 243, 255], dtype=np.float32)
    grad = np.linspace(0, 1, H)[:, None, None]
    arr = (top[None, None, :] * (1 - grad) + bot[None, None, :] * grad)
    return Image.fromarray(np.repeat(arr.astype(np.uint8), W, axis=1))


def hill_strip(period, height, colour):
    """A tileable sine-bump hill strip (tiles every `period` px)."""
    strip = Image.new("RGBA", (period * 3, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    pts = [(x, height - 60 - 70 * (0.5 + 0.5 * math.sin(2 * math.pi * x / period)))
           for x in range(0, period * 3 + 1, 8)]
    d.polygon(pts + [(period * 3, height), (0, height)], fill=colour + (255,))
    return strip


def cloud_sprite(scale):
    w, h = int(260 * scale), int(110 * scale)
    s = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    for cx, cy, r in ((0.30, 0.62, 0.30), (0.52, 0.42, 0.38), (0.74, 0.62, 0.30)):
        d.ellipse([w * (cx - r), h * (cy - r * 1.4), w * (cx + r),
                   h * (cy + r * 1.4)], fill=(255, 255, 255, 235))
    d.rectangle([w * 0.12, h * 0.62, w * 0.88, h * 0.86],
                fill=(255, 255, 255, 235))
    return s


SKY7 = sky_day7()
SKY1 = Image.new("RGB", (W, H), (217, 217, 217))
HILLS_FAR = hill_strip(800, 320, (168, 213, 162))
HILLS_NEAR = hill_strip(640, 240, (124, 191, 110))
CLOUD_SPRITES = {s: cloud_sprite(s) for _, _, s in CLOUDS}


# ------------------------------------------------------------ drawing
def gap_intervals(t):
    """Visible gap screen-x intervals [(left, right), ...]."""
    out = []
    for g in GAPS:
        cx = g - SCROLL * t
        if -GAP_HALF < cx < W + GAP_HALF:
            out.append((cx - GAP_HALF, cx + GAP_HALF))
    return sorted(out)


def draw_ground(d, t, day7):
    gaps = gap_intervals(t)
    spans, cur = [], 0.0
    for left, right in gaps:
        spans.append((cur, max(cur, left)))
        cur = max(cur, right)
    spans.append((cur, W))
    for x0, x1 in spans:
        if x1 <= x0:
            continue
        if day7:
            d.rectangle([x0, GROUND_Y, x1, H], fill=(138, 90, 59))
            d.rectangle([x0, GROUND_Y, x1, GROUND_Y + 26], fill=(88, 164, 71))
            d.rectangle([x0, GROUND_Y + 26, x1, GROUND_Y + 34], fill=(160, 106, 69))
        else:
            d.rectangle([x0, GROUND_Y, x1, H], fill=(143, 143, 143))
            d.rectangle([x0, GROUND_Y, x1, GROUND_Y + 6], fill=(110, 110, 110))


def draw_flowers(d, t):
    gaps = gap_intervals(t)
    for wx in FLOWERS:
        sx = wx - SCROLL * t
        if not (20 < sx < W - 20):
            continue
        if any(l - 12 < sx < r + 12 for l, r in gaps):
            continue
        petal = (255, 120, 180) if (wx // 317) % 2 else (255, 255, 255)
        d.line([sx, GROUND_Y, sx, GROUND_Y - 26], fill=(60, 140, 60), width=4)
        for ang in range(0, 360, 72):
            px = sx + 9 * math.cos(math.radians(ang))
            py = GROUND_Y - 32 + 9 * math.sin(math.radians(ang))
            d.ellipse([px - 6, py - 6, px + 6, py + 6], fill=petal)
        d.ellipse([sx - 5, GROUND_Y - 37, sx + 5, GROUND_Y - 27], fill=(255, 210, 40))


def draw_spikes(d, t):
    for wx in SPIKES:
        sx = wx - SCROLL * t
        if not (-140 < sx < W):
            continue
        for i in range(3):
            x0 = sx + i * 40
            d.polygon([(x0, GROUND_Y), (x0 + 20, GROUND_Y - 60),
                       (x0 + 40, GROUND_Y)], fill=(51, 51, 51))


def draw_coins_and_particles(d, t):
    for j, (wx, cy) in enumerate(COINS):
        sx = wx - SCROLL * t
        tc = (wx - HERO_CX) / SCROLL
        if t < tc:
            if -40 < sx < W + 40:
                d.ellipse([sx - 26, cy - 26, sx + 26, cy + 26],
                          fill=(255, 201, 60), outline=(184, 134, 11), width=4)
                d.ellipse([sx - 12, cy - 12, sx + 12, cy + 12], fill=(255, 226, 122))
        elif t - tc < 0.5:  # coin burst at the moment of collection
            age = t - tc
            rng = random.Random(j * 7919 + 13)
            for _ in range(8):
                ang = rng.uniform(0, 2 * math.pi)
                spd = rng.uniform(120, 280)
                px = sx + spd * math.cos(ang) * age
                py = cy + spd * math.sin(ang) * age + 260 * age * age
                r = max(2, 7 - 12 * age)
                d.ellipse([px - r, py - r, px + r, py + r],
                          fill=(255, 201, 60) if _ % 2 else (255, 159, 28))


def draw_hero(d, t, day7):
    off, vy = hero_jump(t)
    feet_y = GROUND_Y + off
    if landing_squash(t):
        sy = 0.92
    else:
        sy = 1.0 + min(0.08, abs(vy) / 9000.0)
    sx = 1.0 / math.sqrt(sy)
    w, h = HERO_SIZE * sx, HERO_SIZE * sy
    x0, y0 = HERO_CX - w / 2, feet_y - h
    fill = MAGENTA if day7 else (58, 58, 58)
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=18, fill=fill,
                        outline=INK, width=4)
    ex1, ex2, ey = x0 + w * 0.30, x0 + w * 0.66, y0 + h * 0.34
    for ex in (ex1, ex2):
        d.ellipse([ex - 9, ey - 11, ex + 9, ey + 11], fill=(255, 255, 255))
        d.ellipse([ex - 4, ey - 6, ex + 4, ey + 6], fill=INK)
    if day7:  # day 7 hero smiles; day 1 hero is just a block
        d.arc([x0 + w * 0.28, y0 + h * 0.52, x0 + w * 0.72, y0 + h * 0.82],
              start=15, end=165, fill=(255, 255, 255), width=6)


def draw_text_block(d, t, day7):
    pill, hook, sub = copy_at(t)
    fill = MAGENTA if day7 else (74, 74, 74)
    d.rounded_rectangle([700, 280, 960, 380], radius=34, fill=fill,
                        outline=(255, 255, 255), width=3)
    d.text((830, 330), pill, font=F_PILL, fill=(255, 255, 255), anchor="mm")
    if day7:
        score = int(t * 15) + 50 * coins_collected(t)
        d.text((960, 405), "SCORE %04d" % score, font=F_SCORE,
               fill=(255, 255, 255), anchor="ra", stroke_width=2,
               stroke_fill=INK)
        if not hook:  # the coin row would collide with the CTA lines
            d.ellipse([872, 477, 908, 513], fill=(255, 201, 60),
                      outline=(184, 134, 11), width=3)
            d.text((920, 470), "x %d" % coins_collected(t), font=F_SUB,
                   fill=(255, 255, 255), anchor="la", stroke_width=2,
                   stroke_fill=INK)
    fnt = F_HOOK if t < 3.0 else F_CTA
    for i, line in enumerate(hook):
        d.text((W // 2, 470 + i * 90), line, font=fnt, fill=(255, 255, 255),
               anchor="ma", stroke_width=3, stroke_fill=INK)
    for i, line in enumerate(sub):
        d.text((W // 2, 700 + i * 62), line, font=F_SUB,
               fill=(255, 255, 255), anchor="ma", stroke_width=2,
               stroke_fill=INK)


def frame(t):
    """One full 1080x1920 frame at time t (seconds)."""
    day7 = version_at(t) == "day7"
    img = (SKY7 if day7 else SKY1).copy().convert("RGB")
    d = ImageDraw.Draw(img)
    if day7:
        d.ellipse([818, 128, 942, 252], fill=(255, 217, 59))  # sun
        for k in range(12):
            a = math.radians(k * 30)
            d.line([880 + 78 * math.cos(a), 190 + 78 * math.sin(a),
                    880 + 102 * math.cos(a), 190 + 102 * math.sin(a)],
                   fill=(255, 217, 59), width=8)
        for name, strip, par, top in (("far", HILLS_FAR, 0.4, 980),
                                      ("near", HILLS_NEAR, 0.6, 1060)):
            period = strip.width // 3
            off = int(SCROLL * t * par) % period
            crop = strip.crop((off, 0, off + W, strip.height))
            img.paste(crop, (0, top + (GROUND_Y - top - strip.height)), crop)
        for wx, wy, sc in CLOUDS:
            sx = (wx - SCROLL * 0.25 * t) % 1600 - 260
            img.paste(CLOUD_SPRITES[sc], (int(sx), wy), CLOUD_SPRITES[sc])
        d = ImageDraw.Draw(img)
    draw_ground(d, t, day7)
    if day7:
        draw_flowers(d, t)
        draw_spikes(d, t)
    draw_coins_and_particles(d, t) if day7 else None
    draw_hero(d, t, day7)
    draw_text_block(d, t, day7)
    return img


# ------------------------------------------------------- press pack fetch
def fetch_press():
    """Download the end card + badge from make.fun's press pack (as-is),
    verifying each file's sha256 against the press manifest."""
    os.makedirs(PRESS_DIR, exist_ok=True)
    for name, (url, want) in PRESS_FILES.items():
        path = os.path.join(PRESS_DIR, name)
        ok = os.path.exists(path) and hashlib.sha256(
            open(path, "rb").read()).hexdigest() == want
        if not ok:
            print("downloading", name)
            urllib.request.urlretrieve(url, path)
            got = hashlib.sha256(open(path, "rb").read()).hexdigest()
            assert got == want, (name, got)
    print("press pack verified")


# ------------------------------------------------------------ audio
def synth_audio(path):
    """A light chiptune loop (square-ish arpeggio + bass) with a coin blip
    each time the day-7 hero collects a coin on screen."""
    sr = 44100
    n = int(DUR * sr)
    sig = np.zeros(n, dtype=np.float32)
    eighth = 60.0 / 112 / 2
    scale = [523.25, 659.25, 783.99, 880.00, 783.99, 659.25, 587.33, 659.25]
    bass = [261.63, 349.23, 261.63, 392.00]
    for i, f in enumerate(scale * 12):
        s = int(i * eighth * sr)
        e = min(n, int((i + 1) * eighth * sr))
        if s >= n:
            break
        tt = np.arange(e - s) / sr
        env = np.minimum(1.0, tt / 0.01) * (0.55 + 0.45 * np.exp(-tt * 6))
        tone = (np.sin(2 * np.pi * f * tt)
                + np.sin(2 * np.pi * 3 * f * tt) / 3
                + np.sin(2 * np.pi * 5 * f * tt) / 5) / 1.4
        sig[s:e] += 0.085 * env * tone
        if i % 8 == 0:  # one bass note per bar
            bf = bass[(i // 8) % 4]
            be = min(n, int((i + 8) * eighth * sr))
            bt = np.arange(be - s) / sr
            sig[s:be] += 0.05 * np.exp(-bt * 1.5) * np.sin(2 * np.pi * bf * bt)
    for wx, _ in COINS:  # blip only where the day-7 cut is on screen
        tc = (wx - HERO_CX) / SCROLL
        if version_at(tc) != "day7":
            continue
        for f, d0, d1 in ((1318.5, 0.0, 0.07), (1975.5, 0.07, 0.20)):
            s = int((tc + d0) * sr)
            e = min(n, int((tc + d1) * sr))
            tt = np.arange(e - s) / sr
            sig[s:e] += 0.16 * np.exp(-tt * 18) * np.sin(2 * np.pi * f * tt)
    fade = np.ones(n, dtype=np.float32)
    fade[:int(0.2 * sr)] = np.linspace(0, 1, int(0.2 * sr))
    fade[-sr:] = np.linspace(1, 0, sr)
    pcm = np.clip(sig * fade * 32767, -32767, 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    print("audio written", path)


# ------------------------------------------------------------ render
def render_base(base_mp4, samples):
    """Render the 24 s game video (no badge, no card) to base_mp4."""
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt",
           "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-preset", "medium", base_mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(N_FRAMES):
        t = i / FPS
        img = frame(t)
        if t in samples:
            img.save(os.path.join(WORK_DIR, "base_t%04.1f.png" % t))
        proc.stdin.write(img.tobytes())
        if i % 180 == 0:
            print("rendered frame %d/%d" % (i, N_FRAMES))
    proc.stdin.close()
    proc.wait()
    assert proc.returncode == 0, "base render failed"
    print("base written", base_mp4)


def composite(base_mp4, audio_wav):
    """Badge from frame 0 until the card; last 2.5 s blurred + desaturated
    under the transparent end card, referral code typed into its field."""
    card = os.path.join(PRESS_DIR, "card-9x16.webm")
    badge = os.path.join(PRESS_DIR, "badge-9x16.png")
    fc = ("[0:v]split=2[base1][base2];"
          "[base1]trim=end=21.5,setpts=PTS-STARTPTS[pre];"
          "[pre][1:v]overlay=0:0:shortest=1[prebadged];"
          "[base2]trim=start=21.5,setpts=PTS-STARTPTS,"
          "gblur=sigma=28,eq=saturation=0.3[blurred];"
          "[blurred][2:v]overlay=0:0:eof_action=pass[carded];"
          "[carded]drawbox=x=208:y=1230:w=9:h=82:color=white:thickness=fill"
          ":enable='gte(t,1.433)',"
          "drawtext=fontfile=%s:text='%s':fontsize=62:fontcolor=0x191419"
          ":x=210:y=1232:enable='gte(t,1.433)'[carddone];"
          "[prebadged][carddone]concat=n=2:v=1:a=0[vout];"
          "[3:a]afade=t=out:st=23:d=1[aout]" % (FONT_MONO_BOLD, REFERRAL_CODE))
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", base_mp4,
           "-loop", "1", "-t", "21.5", "-i", badge,
           "-i", card, "-i", audio_wav,
           "-filter_complex", fc,
           "-map", "[vout]", "-map", "[aout]",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-crf", "20", "-preset", "medium",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
           FINAL_MP4]
    subprocess.run(cmd, check=True)
    print("final written", FINAL_MP4)


def main():
    os.makedirs(WORK_DIR, exist_ok=True)
    fetch_press()
    base_mp4 = os.path.join(WORK_DIR, "base.mp4")
    audio_wav = os.path.join(WORK_DIR, "audio.wav")
    render_base(base_mp4, samples={1.5, 5.0, 8.5, 12.0, 18.0})
    synth_audio(audio_wav)
    composite(base_mp4, audio_wav)
    subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                    "format=duration,size", "-show_entries",
                    "stream=width,height,codec_name,r_frame_rate",
                    "-of", "default=noprint_wrappers=1", FINAL_MP4],
                   check=True)


if __name__ == "__main__":
    main()
