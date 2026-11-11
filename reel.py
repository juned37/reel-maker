#!/usr/bin/env python3
"""reel.py - turn a script JSON into an animated explainer video (1080x1920 MP4).

  python reel.py render scripts/ramadan.json out/video.mp4 [--tts edge|espeak|silent]
  python reel.py generate "your topic" scripts/generated.json     (needs GEMINI_API_KEY)
"""
import asyncio, json, math, os, re, shutil, subprocess, sys, tempfile, time, urllib.request
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, SS = 1080, 1920, 30, 2          # canvas, fps, line-art supersampling
GAP, END_GAP = 0.45, 1.1                    # pause after each scene / after the last
INK, GOLD = (59, 49, 40), (176, 128, 36)
PAPER, PAPER2 = (250, 245, 235), (238, 229, 214)
SUN, GOLDL = (240, 196, 92), (222, 178, 80)
GROUND_Y, STAGE_CY = 1180, 800
ELEMENTS = {"figures", "arches", "scale", "crescent", "sun", "book", "mosque",
            "kaaba", "calendar", "question", "text"}

# ---------------------------------------------------------------- fonts
SERIF = ["fonts/regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"]
SERIF_B = ["fonts/bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
           "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"]

@lru_cache(None)
def font(size, bold=False):
    for p in (SERIF_B if bold else SERIF):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)

# ---------------------------------------------------------------- line-art helpers
class Art:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
    def s(self, v): return [x * SS for x in v]
    def line(self, pts, w=4, fill=INK): self.d.line(self.s(pts), fill=fill, width=w * SS, joint="curve")
    def poly(self, pts, fill=PAPER, w=4):
        self.d.polygon(self.s(pts), fill=fill)
        if w: self.line(pts + pts[:2], w)
    def rect(self, x0, y0, x1, y1, fill=PAPER, w=4):
        self.d.rectangle(self.s([x0, y0, x1, y1]), fill=fill, outline=INK if w else None, width=w * SS)
    def ell(self, x0, y0, x1, y1, fill=PAPER, w=4):
        self.d.ellipse(self.s([x0, y0, x1, y1]), fill=fill, outline=INK if w else None, width=w * SS)
    def arc(self, box, a0, a1, w=4): self.d.arc(self.s(box), a0, a1, fill=INK, width=w * SS)
    def pie(self, box, a0, a1, fill=PAPER): self.d.pieslice(self.s(box), a0, a1, fill=fill)
    def mask_shape(self, mask, fill, ow=3):
        dil = mask.filter(ImageFilter.MaxFilter(2 * ow * SS // 1 + 1))
        self.img.paste(Image.new("RGBA", self.img.size, INK + (255,)), (0, 0), dil)
        self.img.paste(Image.new("RGBA", self.img.size, fill + (255,)), (0, 0), mask)
    def done(self): return self.img.resize((self.w, self.h), Image.Resampling.LANCZOS)

def star_pts(cx, cy, ro, ri):
    return [c for i in range(10) for c in (
        cx + (ro if i % 2 == 0 else ri) * math.sin(i * math.pi / 5),
        cy - (ro if i % 2 == 0 else ri) * math.cos(i * math.pi / 5))]

def row_xs(n):
    step = min(260, 840 / (n - 1)) if n > 1 else 0
    return [W / 2 + (i - (n - 1) / 2) * step for i in range(n)]

# ---------------------------------------------------------------- elements
def el_figures(n):
    a = Art(W, 346)
    a.line([40, 330, W - 40, 330], 4)
    for x in range(70, W - 60, 110):
        a.line([x, 341, x + 16, 341], 3)
    for i, cx in enumerate(row_xs(n)):
        top = 22
        a.d.ellipse(a.s([cx - 62, 316, cx + 62, 331]), fill=(60, 45, 30, 40))
        a.poly([cx - 30, top + 78, cx + 30, top + 78, cx + 48, 322, cx - 48, 322])
        a.line([cx - 30, top + 80, cx - 42, top + 188]); a.line([cx + 30, top + 80, cx + 42, top + 188])
        a.ell(cx - 49, top + 186, cx - 35, top + 200, w=3); a.ell(cx + 35, top + 186, cx + 49, top + 200, w=3)
        a.line([cx, top + 135, cx, 322], 3); a.line([cx - 46, 310, cx + 46, 310], 3)
        a.ell(cx - 28, top + 14, cx + 28, top + 70)
        if i % 2 == 0:   # skull cap
            a.d.chord(a.s([cx - 31, top + 4, cx + 31, top + 60]), 180, 360, fill=PAPER2)
            a.arc([cx - 31, top + 4, cx + 31, top + 60], 180, 360); a.line([cx - 31, top + 32, cx + 31, top + 32], 3)
        else:            # turban
            a.ell(cx - 37, top + 2, cx + 37, top + 44, fill=PAPER2)
            a.line([cx - 30, top + 30, cx + 26, top + 12], 3); a.line([cx - 22, top + 38, cx + 34, top + 20], 3)
    return a.done(), (0, GROUND_Y - 330)

def el_arches(n):
    a = Art(W, 230)
    for cx in row_xs(n):
        a.pie([cx - 72, 4, cx + 72, 148], 180, 360); a.rect(cx - 72, 76, cx + 72, 196, w=0)
        a.line([cx - 72, 76, cx - 72, 196]); a.line([cx + 72, 76, cx + 72, 196]); a.arc([cx - 72, 4, cx + 72, 148], 180, 360)
        a.pie([cx - 54, 34, cx + 54, 142], 180, 360, PAPER2); a.rect(cx - 54, 88, cx + 54, 196, PAPER2, 0)
        a.line([cx - 54, 88, cx - 54, 196], 3); a.line([cx + 54, 88, cx + 54, 196], 3); a.arc([cx - 54, 34, cx + 54, 142], 180, 360, 3)
        a.rect(cx - 90, 196, cx + 90, 212)
    return a.done(), (0, 610)

def el_scale():
    a = Art(W, 130); cx = W / 2
    a.line([cx, 20, cx, 112]); a.poly([cx - 42, 120, cx + 42, 120, cx + 24, 104, cx - 24, 104])
    a.line([cx - 150, 34, cx + 150, 34])
    for ex in (cx - 150, cx + 150):
        a.line([ex, 34, ex - 34, 92], 3); a.line([ex, 34, ex + 34, 92], 3)
        a.d.chord(a.s([ex - 40, 80, ex + 40, 104]), 0, 180, fill=PAPER2); a.arc([ex - 40, 80, ex + 40, 104], 0, 180)
        a.line([ex - 40, 92, ex + 40, 92])
    a.ell(cx - 8, 10, cx + 8, 26, fill=GOLDL)
    return a.done(), (0, 470)

def piece_crescent():
    a = Art(400, 400); S = SS
    m = Image.new("L", a.img.size, 0); md = ImageDraw.Draw(m)
    md.ellipse([70 * S, 70 * S, 330 * S, 330 * S], fill=255)
    md.ellipse([135 * S, 40 * S, 355 * S, 300 * S], fill=0)
    a.mask_shape(m, GOLDL)
    a.poly(star_pts(292, 150, 30, 13), fill=GOLDL, w=3)
    return a.done()

def piece_sun():
    a = Art(400, 400)
    for i in range(12):
        t = i * math.pi / 6
        a.line([200 + 112 * math.cos(t), 200 + 112 * math.sin(t), 200 + 160 * math.cos(t), 200 + 160 * math.sin(t)], 6)
    a.ell(110, 110, 290, 290, fill=SUN)
    return a.done()

def piece_book():
    a = Art(400, 400)
    a.poly([55, 292, 200, 328, 345, 292, 345, 316, 200, 352, 55, 316], fill=GOLDL)
    a.poly([200, 135, 70, 115, 70, 290, 200, 312]); a.poly([200, 135, 330, 115, 330, 290, 200, 312])
    for k in range(5):
        y = 160 + k * 28
        a.line([92, y - 8 + k * 3, 178, y + 10 + k * 1], 3, (150, 135, 115)); a.line([222, y + 10 + k * 1, 308, y - 8 + k * 3], 3, (150, 135, 115))
    return a.done()

def piece_mosque():
    a = Art(400, 400)
    a.line([20, 330, 380, 330])
    for x0 in (38, 316):
        a.rect(x0, 130, x0 + 46, 330); a.poly([x0 - 6, 130, x0 + 23, 62, x0 + 52, 130], fill=PAPER2)
        a.line([x0 + 23, 62, x0 + 23, 38], 3); a.ell(x0 + 18, 30, x0 + 28, 40, fill=GOLDL, w=3)
        a.rect(x0 - 5, 175, x0 + 51, 185, PAPER2, 3); a.rect(x0 + 15, 210, x0 + 31, 250, PAPER2, 3)
    a.rect(105, 190, 295, 330); a.pie([105, 70, 295, 310], 180, 360); a.line([105, 190, 105, 190]); a.arc([105, 70, 295, 310], 180, 360)
    a.line([200, 70, 200, 40], 3); a.ell(193, 28, 207, 42, fill=GOLDL, w=3)
    a.rect(170, 240, 230, 330, PAPER2); a.pie([170, 210, 230, 270], 180, 360, PAPER2); a.arc([170, 210, 230, 270], 180, 360)
    return a.done()

def piece_kaaba():
    a = Art(400, 400); DK, DK2 = (66, 56, 52), (48, 40, 38)
    a.poly([80, 130, 140, 100, 350, 100, 300, 130], fill=(92, 80, 74))
    a.poly([300, 130, 350, 100, 350, 288, 300, 322], fill=DK2)
    a.poly([80, 130, 300, 130, 300, 322, 80, 322], fill=DK)
    a.poly([80, 172, 300, 172, 300, 198, 80, 198], fill=GOLDL, w=3); a.poly([300, 172, 350, 144, 350, 170, 300, 198], fill=GOLD, w=3)
    a.rect(212, 232, 262, 322, GOLDL, 3)
    return a.done()

def piece_calendar():
    a = Art(400, 400)
    a.rect(70, 90, 330, 335); a.rect(70, 90, 330, 160, GOLDL)
    for x in (140, 260): a.line([x, 68, x, 112], 8)
    for r in range(3):
        for c in range(4):
            x, y = 95 + c * 58, 182 + r * 48
            a.rect(x, y, x + 40, y + 32, PAPER2, 3)
    a.ell(212, 267, 256, 307, fill=GOLDL, w=3)
    return a.done()

def piece_question():
    a = Art(400, 400); a.ell(80, 80, 320, 320, fill=PAPER2, w=5)
    f = font(230 * SS, True); d = ImageDraw.Draw(a.img)
    d.text((200 * SS, 200 * SS), "?", font=f, fill=GOLD + (255,), anchor="mm")
    return a.done()

def piece_text(arg, maxw):
    lines = (arg or "").split("|"); sizes = [170] + [66] * 8
    imgs, th = [], 0
    for i, ln in enumerate(lines[:3]):
        sz = sizes[i]
        while sz > 30 and ImageDraw.Draw(Image.new("L", (1, 1))).textlength(ln, font=font(sz, True)) > maxw: sz -= 4
        f = font(sz, True); bb = f.getbbox(ln)
        im = Image.new("RGBA", (int(bb[2]) + 10, int(bb[3]) + 10), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((0, 0), ln, font=f, fill=(GOLD if i == 0 else INK) + (255,))
        imgs.append(im); th += im.height + 8
    out = Image.new("RGBA", (maxw + 20, th), (0, 0, 0, 0)); y = 0
    for im in imgs:
        out.paste(im, ((out.width - im.width) // 2, y), im); y += im.height + 8
    return out

SLOT_X = {"left": 290, "center": 540, "right": 790}
SPEC = re.compile(r"^([a-z]+)(?::(.*?))?(?:@(left|center|right))?$")

def parse_spec(spec):
    m = SPEC.match(spec.strip())
    if not m or m.group(1) not in ELEMENTS: raise ValueError(f"unknown element '{spec}'. Allowed: {sorted(ELEMENTS)}")
    return m.group(1), m.group(2), m.group(3) or "center"

def make_element(spec):
    name, arg, slot = parse_spec(spec)
    if name == "figures": img, pos = el_figures(max(1, min(int(arg or 3), 6)))
    elif name == "arches": img, pos = el_arches(max(1, min(int(arg or 3), 6)))
    elif name == "scale": img, pos = el_scale()
    else:
        cx = SLOT_X[slot]
        if name == "text": img = piece_text(arg, 900 if slot == "center" else 440)
        else: img = {"crescent": piece_crescent, "sun": piece_sun, "book": piece_book, "mosque": piece_mosque,
                     "kaaba": piece_kaaba, "calendar": piece_calendar, "question": piece_question}[name]()
        pos = (cx - img.width // 2, STAGE_CY - img.height // 2)
    return img, pos

# ---------------------------------------------------------------- background / title
def make_base(script):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    t = yy / H
    top, bot = np.array([246, 237, 224], np.float32), np.array([222, 198, 172], np.float32)
    arr = top[None, None, :] * (1 - t[..., None]) + bot[None, None, :] * t[..., None]
    glow = np.exp(-(((xx - W / 2) / 520) ** 2 + ((yy - 120) / 520) ** 2))[..., None] * 18
    vig = (((xx - W / 2) / (W * 0.9)) ** 2 + ((yy - H / 2) / (H * 0.75)) ** 2)[..., None] * 22
    img = Image.fromarray(np.clip(arr + glow - vig, 0, 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(img)
    lines = script["title"][:2]; ys = [300, 395] if len(lines) == 2 else [330]
    for i, (ln, y) in enumerate(zip(lines, ys)):
        sz = 100 if i == 0 else 66
        while sz > 28 and d.textlength(ln, font=font(sz, True)) > 940: sz -= 4
        d.text((W / 2, y), ln, font=font(sz, True), fill=GOLD if i == 0 else INK, anchor="mm")
    dy = ys[-1] + 62
    d.line([W / 2 - 230, dy, W / 2 - 18, dy], fill=GOLD, width=3); d.line([W / 2 + 18, dy, W / 2 + 230, dy], fill=GOLD, width=3)
    d.polygon([(W / 2, dy - 9), (W / 2 + 9, dy), (W / 2, dy + 9), (W / 2 - 9, dy)], fill=GOLD)
    wm = (script.get("watermark") or "").upper()
    if wm:
        f = font(30); total = sum(d.textlength(c, font=f) + 7 for c in wm) - 7; x = (W - total) / 2
        for c in wm:
            d.text((x, 1575), c, font=f, fill=(160, 138, 118), anchor="lm"); x += d.textlength(c, font=f) + 7
    return img

# ---------------------------------------------------------------- TTS
def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())

async def _edge(text, voice, rate, out):
    import edge_tts
    try: com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    except TypeError: com = edge_tts.Communicate(text, voice, rate=rate)
    words = []
    with open(out, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio": f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7; words.append((s, s + ch["duration"] / 1e7))
    return words

def synth(text, voice, rate, out_base, provider):
    """returns (audio_path, [(start,end) per word] or None)"""
    if provider == "edge":
        for attempt in range(3):
            try:
                out = f"{out_base}.mp3"; w = asyncio.run(_edge(text, voice, rate, out))
                if os.path.getsize(out) > 1000: return out, w
            except Exception as e:
                print(f"  edge-tts attempt {attempt + 1} failed: {e}", file=sys.stderr); time.sleep(2)
        if not shutil.which("espeak-ng"): raise RuntimeError("edge-tts failed and espeak-ng is not installed")
        print("  falling back to espeak-ng (robotic voice)", file=sys.stderr); provider = "espeak"
    if provider == "espeak":
        out = f"{out_base}.wav"; subprocess.run(["espeak-ng", "-v", "en-us", "-s", "150", "-w", out, text], check=True)
        return out, None
    out = f"{out_base}.wav"      # silent (dry run)
    dur = 0.38 * len(text.split()) + 0.3
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(dur), out], check=True)
    return out, None

def word_times(words, bounds, dur):
    if bounds and len(bounds) == len(words): return bounds
    wt = [len(w) + 2 for w in words]; tot = sum(wt); t = 0.0; out = []
    lead, span = 0.05, max(dur - 0.15, 0.5)
    for w in wt:
        out.append((lead + span * t / tot, lead + span * (t + w) / tot)); t += w
    return out

# ---------------------------------------------------------------- render
def ease(x): x = min(max(x, 0.0), 1.0); return 1 - (1 - x) ** 3

def make_chunks(words, scene_start, scene_end):
    chunks, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        end = w[0].rstrip('"”\')').endswith((".", "?", "!", ":")) or (len(cur) >= 3 and w[0].endswith((",", ";"))) or len(cur) >= 6
        if end or i == len(words) - 1: chunks.append(cur); cur = []
    out = []
    for i, ch in enumerate(chunks):
        out.append({"words": ch, "show": scene_start if i == 0 else chunks[i - 1][-1][2],
                    "hide": scene_end if i == len(chunks) - 1 else ch[-1][2]})
    for i in range(len(out) - 1): out[i]["hide"] = out[i + 1]["show"]
    return out

def layout_chunk(ch, d, f, maxw=900, lh=84, cy=1335):
    space = d.textlength(" ", font=f); lines, cur, cw = [], [], 0
    for wi, (txt, s, e) in enumerate(ch["words"]):
        w = d.textlength(txt, font=f)
        if cur and cw + space + w > maxw: lines.append(cur); cur, cw = [], 0
        cw += (space if cur else 0) + w; cur.append((wi, txt, w))
    lines.append(cur); top = cy - len(lines) * lh / 2; placed = []
    for li, ln in enumerate(lines):
        tw = sum(w for _, _, w in ln) + space * (len(ln) - 1); x = (W - tw) / 2
        for wi, txt, w in ln:
            placed.append((wi, txt, x, top + li * lh + lh / 2)); x += w + space
    ch["placed"] = placed

def render(script_path, out_path, provider):
    script = json.loads(Path(script_path).read_text(encoding="utf-8")); validate(script)
    voice, rate = script.get("voice", "en-US-GuyNeural"), script.get("rate", "-5%")
    work = Path(tempfile.mkdtemp()); scenes = script["scenes"]; timeline = []; wavs = []; t0 = 0.0
    for i, sc in enumerate(scenes):
        words = sc["narration"].split(); print(f"[{i + 1}/{len(scenes)}] {sc['narration'][:70]}")
        audio, bounds = synth(sc["narration"], voice, rate, str(work / f"raw{i}"), provider)
        dur = probe(audio); pad = END_GAP if i == len(scenes) - 1 else GAP; total = dur + pad
        wav = work / f"s{i}.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", audio, "-af", "apad", "-t", f"{total:.3f}",
                        "-ar", "44100", "-ac", "1", str(wav)], check=True)
        wavs.append(wav); wt = word_times(words, bounds, dur)
        timeline.append({"t0": t0, "t1": t0 + total, "words": [(w, t0 + s, t0 + e) for w, (s, e) in zip(words, wt)]}); t0 += total
    lst = work / "list.txt"; lst.write_text("".join(f"file '{p}'\n" for p in wavs))
    audio_all = work / "all.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(audio_all)], check=True)

    base = make_base(script); elems, live = [], []
    for sc, tl in zip(scenes, timeline):
        clearing = bool(sc.get("clear")) and live
        if sc.get("clear"):
            for e in live: e["die"] = tl["t0"]
            live = []
        for spec in sc.get("show", []):
            img, (x, y) = make_element(spec)
            e = {"rgb": img.convert("RGB"), "a": img.getchannel("A"), "x": x, "y": y,
                 "appear": tl["t0"] + (0.45 if clearing else 0.1), "die": None}
            elems.append(e); live.append(e)
    d0 = ImageDraw.Draw(base); cf = font(62); chunks = []
    for tl in timeline:
        for ch in make_chunks(tl["words"], tl["t0"], tl["t1"]): layout_chunk(ch, d0, cf); chunks.append(ch)

    n_frames = math.ceil(t0 * FPS); Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-i", str(audio_all), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out_path)], stdin=subprocess.PIPE)
    ci = 0; print(f"rendering {n_frames} frames ({t0:.1f}s)...")
    for k in range(n_frames):
        t = k / FPS; fr = base.copy()
        for e in elems:
            f = ease((t - e["appear"]) / 0.7)
            if e["die"] is not None: f *= 1 - min(max((t - e["die"]) / 0.35, 0), 1)
            if f < 0.01: continue
            dy = int((1 - ease((t - e["appear"]) / 0.7)) * 36)
            mask = e["a"] if f > 0.995 else e["a"].point(lambda v, f=f: int(v * f))
            fr.paste(e["rgb"], (int(e["x"]), int(e["y"]) + dy), mask)
        while ci < len(chunks) - 1 and t >= chunks[ci]["hide"]: ci += 1
        ch = chunks[ci]
        if ch["show"] <= t:
            hl = max([i for i, w in enumerate(ch["words"]) if w[1] <= t], default=-1); d = ImageDraw.Draw(fr)
            for wi, txt, x, y in ch["placed"]: d.text((x, y), txt, font=cf, fill=GOLD if wi == hl else INK, anchor="lm")
        ff.stdin.write(fr.tobytes())
    ff.stdin.close()
    if ff.wait() != 0: sys.exit("ffmpeg failed")
    notes = [f"# {' '.join(script['title'])}", ""] + ["Claims to verify before posting:"] + [f"- {c}" for c in script.get("claims_to_verify", ["(none listed)"])]
    (Path(out_path).parent / "notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    print(f"done -> {out_path} ({t0:.1f}s)")

def validate(s):
    if not (isinstance(s.get("title"), list) and 1 <= len(s["title"]) <= 2): raise ValueError("'title' must be a list of 1-2 lines")
    if not s.get("scenes"): raise ValueError("'scenes' is empty")
    for i, sc in enumerate(s["scenes"]):
        if not sc.get("narration"): raise ValueError(f"scene {i + 1}: missing narration")
        for sp in sc.get("show", []): parse_spec(sp)

# ---------------------------------------------------------------- script generation (Gemini free tier)
PROMPT = """Write a script for a 35-60 second faint-minimal animated explainer video about: {topic}

Return ONLY JSON with this shape:
{{"title": ["Short gold hook.", "Optional second line."], "watermark": "", "voice": "en-US-GuyNeural",
 "claims_to_verify": ["every factual claim made in the narration, one per item"],
 "scenes": [{{"narration": "One or two short spoken sentences.", "clear": false, "show": ["crescent"]}}]}}

Rules:
- 6 to 9 scenes. Short, plain sentences. Spell numbers as words in narration.
- "show" lists visuals to ADD in that scene; set "clear": true to fade out earlier visuals first.
- Allowed visuals: figures:N (1-6 robed people on a ground line), arches:N (1-6), scale, crescent, sun, book, mosque, kaaba, calendar, question, text:BIG|small line.
  Add @left / @center / @right to place a centre-piece (e.g. "sun@right"). Use at most 2 centre-pieces at once (left+right).
- Only widely agreed, verifiable facts. No religious rulings, no sectarian or political claims, no quoting scripture. If unsure, leave it out.
"""

def generate(topic, out):
    key = os.environ["GEMINI_API_KEY"]; model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    body = {"contents": [{"parts": [{"text": PROMPT.format(topic=topic)}]}], "generationConfig": {"responseMimeType": "application/json"}}
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                 json.dumps(body).encode(), {"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=120) as r: resp = json.load(r)
    data = json.loads(resp["candidates"][0]["content"]["parts"][0]["text"]); validate(data)
    Path(out).parent.mkdir(parents=True, exist_ok=True); Path(out).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"script written -> {out}")

if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "render":
        prov = a[a.index("--tts") + 1] if "--tts" in a else "edge"; render(a[1], a[2], prov)
    elif len(a) >= 3 and a[0] == "generate": generate(a[1], a[2])
    else: print(__doc__)
