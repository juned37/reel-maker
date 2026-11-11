 #!/usr/bin/env python3
"""reel.py - turn a script JSON into an animated explainer video (1080x1920 MP4).

  python reel.py render scripts/ramadan.json out/video.mp4 [--tts edge|espeak|silent]
  python reel.py generate "your topic" scripts/generated.json     (needs GEMINI_API_KEY)
Needs art.py (the visuals) in the same folder.
"""
import asyncio, json, math, os, re, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

from art import *   # colours, fonts, drawn visuals, make_base, parse_spec, make_element, FIXED, W, H

FPS = 30
GAP, END_GAP, LEAD = 0.3, 1.0, 0.7          # pause after each scene / after the last / before the first

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
def ease(x): x = min(max(x, 0.0), 1.0); return 1 - (1 - x) ** 4        # smooth ease-out

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
    script = sanitize(json.loads(Path(script_path).read_text(encoding="utf-8"))); validate(script)
    voice, rate = script.get("voice", "en-US-GuyNeural"), script.get("rate", "-3%")
    work = Path(tempfile.mkdtemp()); scenes = script["scenes"]; timeline = []; wavs = []
    lead = work / "lead.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(LEAD),
                    "-ar", "44100", "-ac", "1", str(lead)], check=True)
    wavs.append(lead); t0 = LEAD
    for i, sc in enumerate(scenes):
        words = sc["narration"].split(); print(f"[{i + 1}/{len(scenes)}] {sc['narration'][:70]}")
        audio, bounds = synth(sc["narration"], voice, rate, str(work / f"raw{i}"), provider)
        dur = probe(audio); pad = END_GAP if i == len(scenes) - 1 else GAP; total = dur + pad
        wav = work / f"s{i}.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", audio, "-af", "afade=t=in:d=0.03,apad", "-t", f"{total:.3f}",
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
            e = {"rgb": img.convert("RGB"), "a": img.getchannel("A"), "x": x, "y": y, "float": parse_spec(spec)[0] not in FIXED,
                 "appear": tl["t0"] + (0.2 if clearing else 0.1), "die": None}
            elems.append(e); live.append(e)
    d0 = ImageDraw.Draw(base); cf = font(62); chunks = []
    for tl in timeline:
        for ch in make_chunks(tl["words"], tl["t0"], tl["t1"]): layout_chunk(ch, d0, cf); chunks.append(ch)

    CY0, CH = 1155, 360                                   # caption overlay region
    ink_img, gold_img = Image.new("RGB", (W, CH), INK), Image.new("RGB", (W, CH), GOLD)
    n_frames = math.ceil(t0 * FPS); Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    bg = "0xe8dcc8"
    vf = f"fade=t=in:st=0:d=0.35:color={bg},fade=t=out:st={t0 - 0.6:.2f}:d=0.6:color={bg}"
    af = f"afade=t=out:st={t0 - 0.8:.2f}:d=0.8"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-i", str(audio_all), "-vf", vf, "-af", af, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out_path)],
                          stdin=subprocess.PIPE)
    ci = 0; print(f"rendering {n_frames} frames ({t0:.1f}s)...")
    for k in range(n_frames):
        t = k / FPS; fr = base.copy()
        for e in elems:
            ap = ease((t - e["appear"]) / 0.9); f = ap
            if e["die"] is not None: f *= 1 - min(max((t - e["die"]) / 0.5, 0), 1)
            if f < 0.01: continue
            dy = int((1 - ap) * 44 + (5 * math.sin((t - e["appear"]) * 1.5) * ap if e["float"] else 0))
            mask = e["a"] if f > 0.995 else e["a"].point(lambda v, f=f: int(v * f))
            fr.paste(e["rgb"], (int(e["x"]), int(e["y"]) + dy), mask)
        while ci < len(chunks) - 1 and t >= chunks[ci]["hide"]: ci += 1
        ch = chunks[ci]
        if ch["show"] <= t:
            fa = min(1.0, (t - ch["show"]) / 0.16, max(0.0, (ch["hide"] - t) / 0.10 + 0.0) if ci < len(chunks) - 1 else 1.0)
            rise = int((1 - min(1.0, (t - ch["show"]) / 0.16)) * 12)
            hl = max([i for i, w in enumerate(ch["words"]) if w[1] <= t], default=-1)
            m_ink, m_gold = Image.new("L", (W, CH), 0), Image.new("L", (W, CH), 0)
            di, dg = ImageDraw.Draw(m_ink), ImageDraw.Draw(m_gold)
            for wi, txt, x, y in ch["placed"]:
                (dg if wi == hl else di).text((x, y - CY0 + rise), txt, font=cf, fill=255, anchor="lm")
            lut = lambda v, fa=fa: int(v * fa)
            fr.paste(ink_img, (0, CY0), m_ink.point(lut)); fr.paste(gold_img, (0, CY0), m_gold.point(lut))
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

def sanitize(s):
    """Fix common mistakes (unknown visuals, overlapping pieces) instead of failing."""
    s = dict(s); s["title"] = [" ".join(str(t).split()) for t in (s.get("title") or []) if str(t).strip()][:2]
    out, live_fixed, live_cen = [], set(), 0
    for sc in (s.get("scenes") or [])[:14]:
        nar = " ".join(str(sc.get("narration", "")).split())
        if not nar: continue
        specs = []
        for sp in (sc.get("show") or []):
            try: parse_spec(sp); specs.append(str(sp).strip())
            except ValueError as e: print(f"  warning: dropped visual: {e}")
        fix = [p for p in specs if parse_spec(p)[0] in FIXED]; cen = [p for p in specs if parse_spec(p)[0] not in FIXED][:2]
        used = {parse_spec(p)[2] for p in cen if "@" in p}; order = ["center"] if len(cen) == 1 else ["left", "right"]
        cen = [p if "@" in p else p + "@" + next((o for o in order if o not in used and not used.add(o)), "center") for p in cen]
        names = {parse_spec(p)[0] for p in fix}; grid = {"figures", "arches"}
        if names & grid and cen: print("  warning: centre visual dropped (it would overlap the figures)"); cen = []
        clear = bool(sc.get("clear")) or bool(names & live_fixed) or bool(cen and live_cen) \
            or bool(cen and live_fixed & grid) or bool(names & grid and live_cen)
        if clear: live_fixed, live_cen = set(), 0
        live_fixed |= names; live_cen += len(cen)
        out.append({"narration": nar, "clear": clear, "show": fix + cen})
    s["scenes"] = out
    return s

# ---------------------------------------------------------------- script generation (Gemini free tier)
PROMPT = """Write a script for a 35-60 second faint-minimal animated explainer video about: {topic}

Return ONLY JSON with this shape:
{{"title": ["Short gold hook.", "Optional second line."], "watermark": "", "voice": "en-US-GuyNeural",
 "claims_to_verify": ["every factual claim made in the narration, one per item"],
 "scenes": [{{"narration": "One or two short spoken sentences.", "clear": false, "show": ["crescent"]}}]}}

Rules:
- 6 to 9 scenes, about 90 to 130 spoken words in total. Short, plain, calm sentences. Spell numbers as words in narration.
- The first scene is a hook that restates the question. The last scene is a short, memorable closing line.
- "show" lists visuals to ADD in that scene; set "clear": true to fade out earlier visuals first.
- Allowed visuals: figures:N (1-6 robed people on a ground line), arches:N (1-6), scale, crescent, sun, book, mosque, kaaba, calendar, question, hourglass, heart, lantern, globe, text:BIG|small line.
  Add @left / @center / @right to place a centre-piece (e.g. "sun@right"). Use at most 2 centre-pieces at once (left+right).
- Only widely agreed, verifiable facts. No religious rulings, no sectarian or political claims, no quoting scripture. If unsure, leave it out.
"""

def _gemini(prompt, key):
    models = [m for m in (os.environ.get("GEMINI_MODEL"), "gemini-2.5-flash", "gemini-flash-latest") if m]; last = "no response"
    for m in models:
        for attempt in range(3):
            try:
                body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
                req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                                             json.dumps(body).encode(), {"Content-Type": "application/json", "x-goog-api-key": key})
                with urllib.request.urlopen(req, timeout=120) as r: resp = json.load(r)
                return resp["candidates"][0]["content"]["parts"][0]["text"]
            except urllib.error.HTTPError as e:
                last = f"{m}: HTTP {e.code} {e.read().decode(errors='ignore')[:300]}"; print("  " + last, file=sys.stderr)
                if e.code in (429, 500, 503): time.sleep(10 * (attempt + 1)); continue
                break
            except Exception as e:
                last = f"{m}: {e}"; print("  " + last, file=sys.stderr); time.sleep(4)
    raise RuntimeError(f"Gemini request failed: {last}")

def generate(topic, out):
    key = os.environ.get("GEMINI_API_KEY") or sys.exit("GEMINI_API_KEY is not set (add it as a repo secret)")
    for attempt in range(2):
        try:
            text = re.sub(r"^```(?:json)?|```$", "", _gemini(PROMPT.format(topic=topic), key).strip()).strip()
            data = sanitize(json.loads(text)); validate(data); break
        except (ValueError, KeyError) as e:
            print(f"  script invalid ({e}); retrying", file=sys.stderr)
    else: sys.exit("Gemini did not return a usable script")
    data["voice"] = os.environ.get("VOICE") or data.get("voice") or "en-US-GuyNeural"
    data["watermark"] = os.environ.get("WATERMARK", data.get("watermark", ""))
    Path(out).parent.mkdir(parents=True, exist_ok=True); Path(out).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"script written -> {out}")

if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "render":
        prov = a[a.index("--tts") + 1] if "--tts" in a else "edge"; render(a[1], a[2], prov)
    elif len(a) >= 3 and a[0] == "generate": generate(a[1], a[2])
    else: print(__doc__)
