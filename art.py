"""art.py - the look of the videos: colours, fonts, background, title and all the drawn visuals.
Edit this file to change styling or add new visuals. reel.py does the voice, timing and video."""
import math, re
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, SS = 1080, 1920, 2                    # canvas size, line-art supersampling
INK, GOLD = (59, 49, 40), (176, 128, 36)
PAPER, PAPER2 = (250, 245, 235), (238, 229, 214)
SUN, GOLDL = (240, 196, 92), (222, 178, 80)
GROUND_Y, STAGE_CY = 1180, 800
FIXED = {"figures", "arches", "scale"}      # elements with a fixed position
ELEMENTS = FIXED | {"crescent", "sun", "book", "mosque", "kaaba", "calendar", "question",
                    "hourglass", "heart", "lantern", "globe", "text"}

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

def piece_hourglass():
    a = Art(400, 400)
    a.poly([125, 86, 275, 86, 200, 200]); a.poly([200, 200, 275, 314, 125, 314])
    a.poly([152, 118, 248, 118, 200, 186], fill=SUN, w=0); a.poly([200, 262, 242, 312, 158, 312], fill=SUN, w=0)
    a.line([200, 200, 200, 264], 3, GOLD)
    a.rect(105, 66, 295, 88, GOLDL); a.rect(105, 312, 295, 334, GOLDL)
    return a.done()

def piece_heart():
    a = Art(400, 400)
    pts = []
    for k in range(90):
        t = k * 2 * math.pi / 90
        pts += [200 + 9.2 * 16 * math.sin(t) ** 3,
                195 - 9.2 * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))]
    a.poly(pts, fill=(214, 138, 112))
    return a.done()

def piece_lantern():
    a = Art(400, 400)
    a.line([200, 62, 200, 100], 4); a.ell(188, 42, 212, 66, fill=GOLDL, w=4)
    a.poly([150, 100, 250, 100, 236, 132, 164, 132], fill=GOLDL)
    a.ell(138, 124, 262, 296, fill=PAPER2); a.ell(160, 150, 240, 270, fill=SUN, w=3)
    a.arc([160, 124, 240, 296], 270, 90, 3); a.arc([160, 124, 240, 296], 90, 270, 3)
    a.poly([158, 292, 242, 292, 230, 322, 170, 322], fill=GOLDL); a.line([200, 322, 200, 346], 4)
    return a.done()

def piece_globe():
    a = Art(400, 400)
    a.ell(100, 100, 300, 300, fill=PAPER2, w=5)
    a.ell(150, 100, 250, 300, fill=None, w=3); a.line([200, 100, 200, 300], 3)
    a.line([100, 200, 300, 200], 3); a.line([113, 150, 287, 150], 3); a.line([113, 250, 287, 250], 3)
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
                     "kaaba": piece_kaaba, "calendar": piece_calendar, "question": piece_question,
                     "hourglass": piece_hourglass, "heart": piece_heart, "lantern": piece_lantern, "globe": piece_globe}[name]()
        pos = (cx - img.width // 2, STAGE_CY - img.height // 2)
    return img, pos

# ---------------------------------------------------------------- background / title
def make_background():
    """Warm parchment background shared by title and illustrated scene cards."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    t = yy / H
    top, bot = np.array([246, 237, 224], np.float32), np.array([222, 198, 172], np.float32)
    arr = top[None, None, :] * (1 - t[..., None]) + bot[None, None, :] * t[..., None]
    glow = np.exp(-(((xx - W / 2) / 520) ** 2 + ((yy - 120) / 520) ** 2))[..., None] * 18
    vig = (((xx - W / 2) / (W * 0.9)) ** 2 + ((yy - H / 2) / (H * 0.75)) ** 2)[..., None] * 22
    return Image.fromarray(np.clip(arr + glow - vig, 0, 255).astype(np.uint8), "RGB")


def make_base(script):
    img = make_background()
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
