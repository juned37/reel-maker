
"""art.py - illustration library and visual styling for Reel Maker."""

import math
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, SS = 1080, 1920, 2
INK, GOLD = (59, 49, 40), (176, 128, 36)
PAPER, PAPER2 = (250, 245, 235), (238, 229, 214)
SUN, GOLDL = (240, 196, 92), (222, 178, 80)
GROUND_Y, STAGE_CY = 1180, 800

FIXED = {"figures", "arches", "scale"}

ELEMENTS = FIXED | {
    "crescent", "sun", "book", "mosque", "kaaba", "calendar",
    "question", "hourglass", "heart", "lantern", "globe", "text",
    "prayer_mat", "beads", "coins", "water_vessel", "dates",
    "minaret", "dome", "caravan", "tent", "scroll", "ship",
    "palace", "city_gate", "map", "compass", "mountain", "river",
    "atom", "microscope", "telescope", "lightbulb", "gears",
    "computer", "ledger", "marketplace", "inkwell",
}

SERIF = [
    "fonts/regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
]
SERIF_B = [
    "fonts/bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
]


@lru_cache(None)
def font(size, bold=False):
    for path in (SERIF_B if bold else SERIF):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


class Art:
    """Supersampled transparent line-art drawing helper."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = Image.new(
            "RGBA", (w * SS, h * SS), (0, 0, 0, 0)
        )
        self.d = ImageDraw.Draw(self.img)

    def s(self, values):
        return [value * SS for value in values]

    def line(self, pts, w=4, fill=INK):
        self.d.line(
            self.s(pts), fill=fill, width=w * SS, joint="curve"
        )

    def poly(self, pts, fill=PAPER, w=4):
        self.d.polygon(self.s(pts), fill=fill)
        if w:
            self.line(pts + pts[:2], w)

    def rect(self, x0, y0, x1, y1, fill=PAPER, w=4):
        self.d.rectangle(
            self.s([x0, y0, x1, y1]),
            fill=fill,
            outline=INK if w else None,
            width=w * SS,
        )

    def ell(self, x0, y0, x1, y1, fill=PAPER, w=4):
        self.d.ellipse(
            self.s([x0, y0, x1, y1]),
            fill=fill,
            outline=INK if w else None,
            width=w * SS,
        )

    def arc(self, box, a0, a1, w=4):
        self.d.arc(self.s(box), a0, a1, fill=INK, width=w * SS)

    def pie(self, box, a0, a1, fill=PAPER):
        self.d.pieslice(self.s(box), a0, a1, fill=fill)

    def mask_shape(self, mask, fill, ow=3):
        dil = mask.filter(
            ImageFilter.MaxFilter(2 * ow * SS + 1)
        )
        self.img.paste(
            Image.new("RGBA", self.img.size, INK + (255,)),
            (0, 0),
            dil,
        )
        self.img.paste(
            Image.new("RGBA", self.img.size, fill + (255,)),
            (0, 0),
            mask,
        )

    def done(self):
        return self.img.resize(
            (self.w, self.h), Image.Resampling.LANCZOS
        )


def star_pts(cx, cy, ro, ri):
    return [
        coordinate
        for i in range(10)
        for coordinate in (
            cx + (ro if i % 2 == 0 else ri)
            * math.sin(i * math.pi / 5),
            cy - (ro if i % 2 == 0 else ri)
            * math.cos(i * math.pi / 5),
        )
    ]


def row_xs(n):
    step = min(260, 840 / (n - 1)) if n > 1 else 0
    return [
        W / 2 + (i - (n - 1) / 2) * step
        for i in range(n)
    ]


# ---------------------------------------------------------------------
# Original fixed-position elements
# ---------------------------------------------------------------------

def el_figures(n):
    a = Art(W, 346)
    a.line([40, 330, W - 40, 330], 4)

    for x in range(70, W - 60, 110):
        a.line([x, 341, x + 16, 341], 3)

    for i, cx in enumerate(row_xs(n)):
        top = 22
        a.d.ellipse(
            a.s([cx - 62, 316, cx + 62, 331]),
            fill=(60, 45, 30, 40),
        )
        a.poly([
            cx - 30, top + 78, cx + 30, top + 78,
            cx + 48, 322, cx - 48, 322,
        ])
        a.line([cx - 30, top + 80, cx - 42, top + 188])
        a.line([cx + 30, top + 80, cx + 42, top + 188])
        a.ell(cx - 49, top + 186, cx - 35, top + 200, w=3)
        a.ell(cx + 35, top + 186, cx + 49, top + 200, w=3)
        a.line([cx, top + 135, cx, 322], 3)
        a.line([cx - 46, 310, cx + 46, 310], 3)
        a.ell(cx - 28, top + 14, cx + 28, top + 70)

        if i % 2 == 0:
            a.d.chord(
                a.s([cx - 31, top + 4, cx + 31, top + 60]),
                180, 360, fill=PAPER2,
            )
            a.arc(
                [cx - 31, top + 4, cx + 31, top + 60],
                180, 360,
            )
            a.line(
                [cx - 31, top + 32, cx + 31, top + 32], 3
            )
        else:
            a.ell(
                cx - 37, top + 2, cx + 37, top + 44,
                fill=PAPER2,
            )
            a.line(
                [cx - 30, top + 30, cx + 26, top + 12], 3
            )
            a.line(
                [cx - 22, top + 38, cx + 34, top + 20], 3
            )

    return a.done(), (0, GROUND_Y - 330)


def el_arches(n):
    a = Art(W, 230)

    for cx in row_xs(n):
        a.pie(
            [cx - 72, 4, cx + 72, 148], 180, 360
        )
        a.rect(cx - 72, 76, cx + 72, 196, w=0)
        a.line([cx - 72, 76, cx - 72, 196])
        a.line([cx + 72, 76, cx + 72, 196])
        a.arc([cx - 72, 4, cx + 72, 148], 180, 360)

        a.pie(
            [cx - 54, 34, cx + 54, 142],
            180, 360, PAPER2,
        )
        a.rect(
            cx - 54, 88, cx + 54, 196, PAPER2, 0
        )
        a.line([cx - 54, 88, cx - 54, 196], 3)
        a.line([cx + 54, 88, cx + 54, 196], 3)
        a.arc(
            [cx - 54, 34, cx + 54, 142], 180, 360, 3
        )
        a.rect(cx - 90, 196, cx + 90, 212)

    return a.done(), (0, 610)


def el_scale():
    a = Art(W, 130)
    cx = W / 2

    a.line([cx, 20, cx, 112])
    a.poly([
        cx - 42, 120, cx + 42, 120,
        cx + 24, 104, cx - 24, 104,
    ])
    a.line([cx - 150, 34, cx + 150, 34])

    for ex in (cx - 150, cx + 150):
        a.line([ex, 34, ex - 34, 92], 3)
        a.line([ex, 34, ex + 34, 92], 3)
        a.d.chord(
            a.s([ex - 40, 80, ex + 40, 104]),
            0, 180, fill=PAPER2,
        )
        a.arc([ex - 40, 80, ex + 40, 104], 0, 180)
        a.line([ex - 40, 92, ex + 40, 92])

    a.ell(cx - 8, 10, cx + 8, 26, fill=GOLDL)
    return a.done(), (0, 470)


# ---------------------------------------------------------------------
# Original reusable illustrations
# ---------------------------------------------------------------------

def piece_crescent():
    a = Art(400, 400)
    m = Image.new("L", a.img.size, 0)
    md = ImageDraw.Draw(m)
    md.ellipse(
        [70 * SS, 70 * SS, 330 * SS, 330 * SS],
        fill=255,
    )
    md.ellipse(
        [135 * SS, 40 * SS, 355 * SS, 300 * SS],
        fill=0,
    )
    a.mask_shape(m, GOLDL)
    a.poly(star_pts(292, 150, 30, 13), fill=GOLDL, w=3)
    return a.done()


def piece_sun():
    a = Art(400, 400)

    for i in range(12):
        t = i * math.pi / 6
        a.line([
            200 + 112 * math.cos(t),
            200 + 112 * math.sin(t),
            200 + 160 * math.cos(t),
            200 + 160 * math.sin(t),
        ], 6)

    a.ell(110, 110, 290, 290, fill=SUN)
    return a.done()


def piece_book():
    a = Art(400, 400)
    a.poly([
        55, 292, 200, 328, 345, 292,
        345, 316, 200, 352, 55, 316,
    ], fill=GOLDL)
    a.poly([200, 135, 70, 115, 70, 290, 200, 312])
    a.poly([200, 135, 330, 115, 330, 290, 200, 312])

    for k in range(5):
        y = 160 + k * 28
        a.line(
            [92, y - 8 + k * 3, 178, y + 10 + k],
            3, (150, 135, 115),
        )
        a.line(
            [222, y + 10 + k, 308, y - 8 + k * 3],
            3, (150, 135, 115),
        )

    return a.done()


def piece_mosque():
    a = Art(400, 400)
    a.line([20, 330, 380, 330])

    for x0 in (38, 316):
        a.rect(x0, 130, x0 + 46, 330)
        a.poly([
            x0 - 6, 130, x0 + 23, 62, x0 + 52, 130,
        ], fill=PAPER2)
        a.line([x0 + 23, 62, x0 + 23, 38], 3)
        a.ell(
            x0 + 18, 30, x0 + 28, 40,
            fill=GOLDL, w=3,
        )
        a.rect(x0 - 5, 175, x0 + 51, 185, PAPER2, 3)
        a.rect(x0 + 15, 210, x0 + 31, 250, PAPER2, 3)

    a.rect(105, 190, 295, 330)
    a.pie([105, 70, 295, 310], 180, 360)
    a.arc([105, 70, 295, 310], 180, 360)
    a.line([200, 70, 200, 40], 3)
    a.ell(193, 28, 207, 42, fill=GOLDL, w=3)
    a.rect(170, 240, 230, 330, PAPER2)
    a.pie([170, 210, 230, 270], 180, 360, PAPER2)
    a.arc([170, 210, 230, 270], 180, 360)
    return a.done()


def piece_kaaba():
    a = Art(400, 400)
    dk, dk2 = (66, 56, 52), (48, 40, 38)

    a.poly([80, 130, 140, 100, 350, 100, 300, 130],
           fill=(92, 80, 74))
    a.poly([300, 130, 350, 100, 350, 288, 300, 322],
           fill=dk2)
    a.poly([80, 130, 300, 130, 300, 322, 80, 322],
           fill=dk)
    a.poly(
        [80, 172, 300, 172, 300, 198, 80, 198],
        fill=GOLDL, w=3,
    )
    a.poly(
        [300, 172, 350, 144, 350, 170, 300, 198],
        fill=GOLD, w=3,
    )
    a.rect(212, 232, 262, 322, GOLDL, 3)
    return a.done()


def piece_calendar():
    a = Art(400, 400)
    a.rect(70, 90, 330, 335)
    a.rect(70, 90, 330, 160, GOLDL)

    for x in (140, 260):
        a.line([x, 68, x, 112], 8)

    for r in range(3):
        for c in range(4):
            x, y = 95 + c * 58, 182 + r * 48
            a.rect(x, y, x + 40, y + 32, PAPER2, 3)

    a.ell(212, 267, 256, 307, fill=GOLDL, w=3)
    return a.done()


def piece_question():
    a = Art(400, 400)
    a.ell(80, 80, 320, 320, fill=PAPER2, w=5)
    f = font(230 * SS, True)
    ImageDraw.Draw(a.img).text(
        (200 * SS, 200 * SS),
        "?",
        font=f,
        fill=GOLD + (255,),
        anchor="mm",
    )
    return a.done()


def piece_hourglass():
    a = Art(400, 400)
    a.poly([125, 86, 275, 86, 200, 200])
    a.poly([200, 200, 275, 314, 125, 314])
    a.poly(
        [152, 118, 248, 118, 200, 186],
        fill=SUN, w=0,
    )
    a.poly(
        [200, 262, 242, 312, 158, 312],
        fill=SUN, w=0,
    )
    a.line([200, 200, 200, 264], 3, GOLD)
    a.rect(105, 66, 295, 88, GOLDL)
    a.rect(105, 312, 295, 334, GOLDL)
    return a.done()


def piece_heart():
    a = Art(400, 400)
    pts = []

    for k in range(90):
        t = k * 2 * math.pi / 90
        pts.extend([
            200 + 9.2 * 16 * math.sin(t) ** 3,
            195 - 9.2 * (
                13 * math.cos(t)
                - 5 * math.cos(2 * t)
                - 2 * math.cos(3 * t)
                - math.cos(4 * t)
            ),
        ])

    a.poly(pts, fill=(214, 138, 112))
    return a.done()


def piece_lantern():
    a = Art(400, 400)
    a.line([200, 62, 200, 100], 4)
    a.ell(188, 42, 212, 66, fill=GOLDL, w=4)
    a.poly([150, 100, 250, 100, 236, 132, 164, 132],
           fill=GOLDL)
    a.ell(138, 124, 262, 296, fill=PAPER2)
    a.ell(160, 150, 240, 270, fill=SUN, w=3)
    a.arc([160, 124, 240, 296], 270, 90, 3)
    a.arc([160, 124, 240, 296], 90, 270, 3)
    a.poly(
        [158, 292, 242, 292, 230, 322, 170, 322],
        fill=GOLDL,
    )
    a.line([200, 322, 200, 346], 4)
    return a.done()


def piece_globe():
    a = Art(400, 400)
    a.ell(100, 100, 300, 300, fill=PAPER2, w=5)
    a.ell(150, 100, 250, 300, fill=None, w=3)
    a.line([200, 100, 200, 300], 3)
    a.line([100, 200, 300, 200], 3)
    a.line([113, 150, 287, 150], 3)
    a.line([113, 250, 287, 250], 3)
    return a.done()


# ---------------------------------------------------------------------
# New worship, daily-life and Islamic architecture illustrations
# ---------------------------------------------------------------------

def piece_prayer_mat():
    a = Art(400, 400)
    a.rect(76, 70, 324, 340, PAPER2, 5)
    a.rect(96, 90, 304, 320, GOLDL, 3)
    a.poly(
        [200, 95, 270, 155, 200, 215, 130, 155],
        fill=PAPER, w=3,
    )
    a.line([120, 235, 280, 235], 3)
    a.line([120, 260, 280, 260], 3)

    for x in range(125, 281, 25):
        a.line([x, 285, x, 305], 2, GOLD)

    return a.done()


def piece_beads():
    a = Art(400, 400)

    for i in range(30):
        t = math.pi * 2 * i / 30
        x = 200 + 112 * math.cos(t)
        y = 190 + 112 * math.sin(t)
        a.ell(x - 10, y - 10, x + 10, y + 10, GOLDL, 3)

    a.line([200, 302, 200, 340], 4)
    a.poly([185, 340, 215, 340, 200, 375], GOLDL, 3)
    return a.done()


def piece_coins():
    a = Art(400, 400)

    for x, y, r in [
        (145, 245, 62),
        (235, 245, 62),
        (190, 165, 62),
    ]:
        a.ell(x-r, y-r, x+r, y+r, GOLDL, 5)
        a.ell(
            x-r+13, y-r+13, x+r-13, y+r-13,
            SUN, 3,
        )
        a.ell(x-12, y-12, x+12, y+12, PAPER2, 2)

    return a.done()


def piece_water_vessel():
    a = Art(400, 400)
    a.ell(145, 105, 255, 155, GOLDL, 4)
    a.poly(
        [145, 135, 255, 135, 275, 270,
         245, 330, 155, 330, 125, 270],
        PAPER2, 5,
    )
    a.rect(165, 85, 235, 120, GOLDL, 4)
    a.line([155, 205, 245, 205], 3)
    a.line([145, 260, 255, 260], 3)
    return a.done()


def piece_dates():
    a = Art(400, 400)

    for x, y in [
        (145, 205), (205, 165), (260, 220),
        (180, 265), (240, 285),
    ]:
        a.ell(
            x-28, y-48, x+28, y+48,
            (139, 82, 48), 4,
        )
        a.arc([x-16, y-35, x+16, y+35], 260, 80, 2)

    a.ell(105, 290, 295, 335, GOLDL, 4)
    return a.done()


def piece_minaret():
    a = Art(400, 400)
    a.rect(145, 105, 255, 340, PAPER2, 5)
    a.rect(125, 150, 275, 165, GOLDL, 3)
    a.rect(125, 250, 275, 265, GOLDL, 3)
    a.rect(165, 195, 235, 225, PAPER, 3)
    a.poly([130, 105, 200, 45, 270, 105], GOLDL, 4)
    a.line([200, 45, 200, 20], 3)
    a.ell(192, 12, 208, 28, GOLDL, 3)
    a.line([115, 340, 285, 340], 5)
    return a.done()


def piece_dome():
    a = Art(400, 400)
    a.rect(75, 225, 325, 330, PAPER2, 5)
    a.pie([75, 65, 325, 300], 180, 360, GOLDL)
    a.arc([75, 65, 325, 300], 180, 360, 5)
    a.line([200, 65, 200, 30], 4)
    a.ell(190, 18, 210, 38, GOLDL, 3)
    a.rect(175, 255, 225, 330, PAPER, 3)
    a.pie([175, 225, 225, 285], 180, 360, PAPER)
    a.arc([175, 225, 225, 285], 180, 360, 3)
    return a.done()


# ---------------------------------------------------------------------
# New history and civilisation illustrations
# ---------------------------------------------------------------------

def piece_caravan():
    a = Art(400, 400)

    # Symbolic caravan; not a depiction of a named historical person.
    for x in (100, 230):
        a.ell(x, 230, x+105, 290, PAPER2, 4)
        a.line([x+25, 275, x+15, 345], 6)
        a.line([x+78, 275, x+88, 345], 6)
        a.line([x+75, 240, x+95, 180], 6)
        a.line([x+95, 180, x+125, 190], 6)
        a.ell(x+115, 178, x+137, 198, PAPER2, 3)
        a.arc([x+20, 175, x+85, 260], 180, 350, 5)

    a.line([45, 350, 355, 350], 4, GOLD)
    return a.done()


def piece_tent():
    a = Art(400, 400)
    a.poly(
        [55, 315, 200, 75, 345, 315],
        PAPER2, 5,
    )
    a.line([200, 75, 200, 315], 4)
    a.poly(
        [200, 315, 200, 220, 260, 315],
        GOLDL, 3,
    )
    a.line([55, 315, 345, 315], 5)
    a.line([95, 315, 95, 350], 3)
    a.line([305, 315, 305, 350], 3)
    return a.done()


def piece_scroll():
    a = Art(400, 400)
    a.rect(95, 100, 305, 300, PAPER2, 4)
    a.ell(75, 90, 125, 140, GOLDL, 4)
    a.ell(275, 260, 325, 310, GOLDL, 4)

    for y in (150, 185, 220, 255):
        a.line([135, y, 265, y], 3, (150, 135, 115))

    return a.done()


def piece_ship():
    a = Art(400, 400)
    a.poly(
        [55, 265, 345, 265, 295, 330, 110, 330],
        PAPER2, 5,
    )
    a.line([200, 75, 200, 265], 5)
    a.poly([190, 95, 85, 235, 190, 235], GOLDL, 4)
    a.poly([210, 115, 310, 235, 210, 235], PAPER, 4)
    a.line([45, 350, 355, 350], 4, GOLD)
    a.arc([70, 315, 180, 365], 0, 180, 3)
    a.arc([220, 315, 330, 365], 0, 180, 3)
    return a.done()


def piece_palace():
    a = Art(400, 400)
    a.rect(55, 175, 345, 330, PAPER2, 5)
    a.rect(35, 145, 365, 175, GOLDL, 4)

    for x in (85, 160, 240, 315):
        a.rect(x-18, 220, x+18, 275, PAPER, 3)
        a.pie([x-18, 195, x+18, 235], 180, 360, PAPER)
        a.arc([x-18, 195, x+18, 235], 180, 360, 3)

    a.rect(170, 260, 230, 330, GOLDL, 3)
    a.pie([170, 225, 230, 285], 180, 360, GOLDL)
    a.arc([170, 225, 230, 285], 180, 360, 3)
    return a.done()


def piece_city_gate():
    a = Art(400, 400)
    a.rect(65, 100, 335, 340, PAPER2, 5)
    a.rect(145, 205, 255, 340, PAPER, 4)
    a.pie([145, 145, 255, 265], 180, 360, PAPER)
    a.arc([145, 145, 255, 265], 180, 360, 4)
    a.rect(45, 75, 115, 340, GOLDL, 4)
    a.rect(285, 75, 355, 340, GOLDL, 4)
    a.line([80, 75, 80, 35], 3)
    a.line([320, 75, 320, 35], 3)
    return a.done()


def piece_inkwell():
    a = Art(400, 400)
    a.poly(
        [130, 180, 270, 180, 250, 310, 150, 310],
        INK, 4,
    )
    a.ell(125, 145, 275, 205, GOLDL, 4)
    a.ell(170, 165, 230, 185, PAPER2, 3)
    a.line([230, 165, 315, 65], 8, GOLD)
    a.poly([305, 55, 330, 35, 320, 75], INK, 2)
    return a.done()


# ---------------------------------------------------------------------
# New geography and exploration illustrations
# ---------------------------------------------------------------------

def piece_map():
    a = Art(400, 400)
    a.rect(55, 85, 345, 315, PAPER2, 4)
    a.poly(
        [
            95, 145, 145, 115, 185, 155, 225, 125,
            305, 155, 285, 260, 220, 280, 165, 245,
            105, 270,
        ],
        (220, 210, 185), 3,
    )
    a.line(
        [110, 230, 155, 190, 205, 215, 260, 165, 305, 190],
        4, GOLD,
    )
    a.ell(250, 150, 270, 170, (180, 85, 65), 3)
    return a.done()


def piece_compass():
    a = Art(400, 400)
    a.ell(75, 75, 325, 325, PAPER2, 5)
    a.ell(100, 100, 300, 300, GOLDL, 3)
    a.poly(
        [200, 105, 230, 205, 200, 185, 170, 205],
        GOLD, 3,
    )
    a.poly(
        [200, 295, 230, 195, 200, 215, 170, 195],
        INK, 3,
    )
    a.ell(190, 190, 210, 210, PAPER, 3)
    return a.done()


def piece_mountain():
    a = Art(400, 400)
    a.poly(
        [35, 325, 150, 100, 205, 205, 255, 125, 365, 325],
        PAPER2, 5,
    )
    a.poly([115, 170, 150, 100, 185, 170, 155, 155], PAPER, 3)
    a.poly([220, 190, 255, 125, 290, 190, 255, 175], PAPER, 3)
    a.line([45, 330, 355, 330], 4, GOLD)
    return a.done()


def piece_river():
    a = Art(400, 400)
    a.poly(
        [
            65, 75, 145, 75, 185, 145, 145, 205,
            230, 260, 195, 325, 110, 325, 145, 265,
            85, 205, 120, 145,
        ],
        (185, 205, 205), 4,
    )

    for y in (125, 205, 285):
        a.line([155, y, 245, y+12], 3, GOLD)

    return a.done()


# ---------------------------------------------------------------------
# New science and technology illustrations
# ---------------------------------------------------------------------

def piece_atom():
    a = Art(400, 400)
    a.ell(175, 175, 225, 225, GOLDL, 4)
    a.ell(70, 150, 330, 250, None, 4)
    a.arc([70, 70, 330, 330], 0, 360, 4)
    a.ell(105, 105, 295, 295, None, 4)
    a.ell(305, 190, 325, 210, GOLD, 3)
    a.ell(185, 70, 205, 90, GOLD, 3)
    a.ell(85, 190, 105, 210, GOLD, 3)
    return a.done()


def piece_microscope():
    a = Art(400, 400)
    a.line([145, 80, 215, 150], 18, INK)
    a.ell(120, 55, 165, 100, GOLDL, 4)
    a.line([205, 145, 245, 185], 14, INK)
    a.arc([130, 145, 270, 285], 180, 350, 12)
    a.line([200, 245, 200, 315], 10)
    a.line([115, 330, 285, 330], 10, GOLD)
    a.line([165, 285, 235, 285], 8)
    return a.done()


def piece_telescope():
    a = Art(400, 400)
    a.poly(
        [85, 145, 270, 95, 300, 175, 115, 225],
        PAPER2, 5,
    )
    a.ell(265, 90, 315, 180, GOLDL, 4)
    a.line([190, 205, 155, 325], 7)
    a.line([190, 205, 250, 325], 7)
    a.line([155, 325, 250, 325], 5)
    a.ell(65, 65, 85, 85, GOLDL, 2)
    a.ell(320, 55, 340, 75, GOLDL, 2)
    return a.done()


def piece_lightbulb():
    a = Art(400, 400)
    a.ell(115, 55, 285, 250, SUN, 5)
    a.poly(
        [150, 220, 250, 220, 235, 285, 165, 285],
        PAPER2, 4,
    )

    for y in (290, 310, 330):
        a.line([165, y, 235, y], 5, GOLD)

    a.line([200, 20, 200, 0], 4, GOLD)
    a.line([95, 75, 65, 50], 4, GOLD)
    a.line([305, 75, 335, 50], 4, GOLD)
    a.line([80, 175, 45, 175], 4, GOLD)
    a.line([320, 175, 355, 175], 4, GOLD)
    return a.done()


def piece_gears():
    a = Art(400, 400)
    a.ell(75, 105, 245, 275, GOLDL, 5)
    a.ell(130, 160, 190, 220, PAPER2, 4)
    a.ell(205, 190, 335, 320, PAPER2, 5)
    a.ell(245, 230, 295, 280, GOLDL, 4)

    for x, y in [
        (160, 80), (160, 300), (50, 190),
        (270, 150), (270, 340), (350, 255),
    ]:
        a.rect(x-12, y-12, x+12, y+12, GOLDL, 2)

    return a.done()


def piece_computer():
    a = Art(400, 400)
    a.rect(65, 65, 335, 265, PAPER2, 5)
    a.rect(85, 85, 315, 245, (218, 225, 220), 3)
    a.line([200, 265, 200, 315], 8)
    a.line([135, 320, 265, 320], 8, GOLD)
    a.line([125, 145, 275, 145], 3, GOLD)
    a.line([125, 175, 235, 175], 3)
    a.line([125, 205, 255, 205], 3)
    return a.done()


# ---------------------------------------------------------------------
# New society and economics illustrations
# ---------------------------------------------------------------------

def piece_ledger():
    a = Art(400, 400)
    a.rect(85, 65, 315, 335, PAPER2, 5)
    a.rect(85, 65, 315, 115, GOLDL, 3)

    for y in (155, 200, 245, 290):
        a.line([115, y, 285, y], 3)
        a.ell(105, y-7, 119, y+7, GOLDL, 2)

    a.line([200, 115, 200, 320], 2, GOLD)
    return a.done()


def piece_marketplace():
    a = Art(400, 400)
    a.poly([55, 155, 200, 65, 345, 155], GOLDL, 4)
    a.rect(75, 155, 325, 315, PAPER2, 5)
    a.rect(95, 190, 180, 315, PAPER, 3)
    a.rect(220, 190, 305, 255, PAPER, 3)
    a.line([200, 65, 200, 315], 3, GOLD)
    a.line([55, 315, 345, 315], 5)
    return a.done()


# ---------------------------------------------------------------------
# Text and object positioning
# ---------------------------------------------------------------------

def piece_text(arg, maxw):
    lines = (arg or "").split("|")
    sizes = [170, 66, 66]
    imgs, total_height = [], 0

    for i, line in enumerate(lines[:3]):
        size = sizes[i]

        while size > 30:
            measure = ImageDraw.Draw(
                Image.new("L", (1, 1))
            )
            if measure.textlength(
                line, font=font(size, True)
            ) <= maxw:
                break
            size -= 4

        selected_font = font(size, True)
        bounds = selected_font.getbbox(line)

        image = Image.new(
            "RGBA",
            (int(bounds[2]) + 10, int(bounds[3]) + 10),
            (0, 0, 0, 0),
        )

        ImageDraw.Draw(image).text(
            (0, 0),
            line,
            font=selected_font,
            fill=(GOLD if i == 0 else INK) + (255,),
        )

        imgs.append(image)
        total_height += image.height + 8

    output = Image.new(
        "RGBA", (maxw + 20, total_height), (0, 0, 0, 0)
    )

    y = 0
    for image in imgs:
        output.paste(
            image,
            ((output.width - image.width) // 2, y),
            image,
        )
        y += image.height + 8

    return output


SLOT_X = {
    "left": 290,
    "center": 540,
    "right": 790,
}

SPEC = re.compile(
    r"^([a-z]+)(?::(.*?))?(?:@(left|center|right))?$"
)


def parse_spec(spec):
    if not isinstance(spec, str):
        raise ValueError("Illustration specification must be a string.")

    match = SPEC.match(spec.strip())

    if not match or match.group(1) not in ELEMENTS:
        raise ValueError(
            f"Unknown element '{spec}'. Allowed: {sorted(ELEMENTS)}"
        )

    return (
        match.group(1),
        match.group(2),
        match.group(3) or "center",
    )


BUILDERS = {
    "crescent": piece_crescent,
    "sun": piece_sun,
    "book": piece_book,
    "mosque": piece_mosque,
    "kaaba": piece_kaaba,
    "calendar": piece_calendar,
    "question": piece_question,
    "hourglass": piece_hourglass,
    "heart": piece_heart,
    "lantern": piece_lantern,
    "globe": piece_globe,
    "prayer_mat": piece_prayer_mat,
    "beads": piece_beads,
    "coins": piece_coins,
    "water_vessel": piece_water_vessel,
    "dates": piece_dates,
    "minaret": piece_minaret,
    "dome": piece_dome,
    "caravan": piece_caravan,
    "tent": piece_tent,
    "scroll": piece_scroll,
    "ship": piece_ship,
    "palace": piece_palace,
    "city_gate": piece_city_gate,
    "map": piece_map,
    "compass": piece_compass,
    "mountain": piece_mountain,
    "river": piece_river,
    "atom": piece_atom,
    "microscope": piece_microscope,
    "telescope": piece_telescope,
    "lightbulb": piece_lightbulb,
    "gears": piece_gears,
    "computer": piece_computer,
    "ledger": piece_ledger,
    "marketplace": piece_marketplace,
    "inkwell": piece_inkwell,
}


def make_element(spec):
    name, arg, slot = parse_spec(spec)

    if name == "figures":
        count = max(1, min(int(arg or 3), 6))
        return el_figures(count)

    if name == "arches":
        count = max(1, min(int(arg or 3), 6))
        return el_arches(count)

    if name == "scale":
        return el_scale()

    if name == "text":
        image = piece_text(
            arg,
            900 if slot == "center" else 440,
        )
    else:
        image = BUILDERS[name]()

    cx = SLOT_X[slot]
    position = (
        cx - image.width // 2,
        STAGE_CY - image.height // 2,
    )

    return image, position


# ---------------------------------------------------------------------
# Background and title card
# ---------------------------------------------------------------------

def make_background():
    """Warm parchment background shared by title and scene cards."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    t = yy / H

    top = np.array([246, 237, 224], np.float32)
    bottom = np.array([222, 198, 172], np.float32)

    arr = (
        top[None, None, :] * (1 - t[..., None])
        + bottom[None, None, :] * t[..., None]
    )

    glow = np.exp(
        -(
            ((xx - W / 2) / 520) ** 2
            + ((yy - 120) / 520) ** 2
        )
    )[..., None] * 18

    vignette = (
        ((xx - W / 2) / (W * 0.9)) ** 2
        + ((yy - H / 2) / (H * 0.75)) ** 2
    )[..., None] * 22

    return Image.fromarray(
        np.clip(arr + glow - vignette, 0, 255).astype(np.uint8),
        "RGB",
    )


def make_base(script):
    image = make_background()
    draw = ImageDraw.Draw(image)

    lines = script["title"][:2]
    ys = [300, 395] if len(lines) == 2 else [330]

    for i, (line, y) in enumerate(zip(lines, ys)):
        size = 100 if i == 0 else 66

        while size > 28:
            if draw.textlength(
                line, font=font(size, True)
            ) <= 940:
                break
            size -= 4

        draw.text(
            (W / 2, y),
            line,
            font=font(size, True),
            fill=GOLD if i == 0 else INK,
            anchor="mm",
        )

    divider_y = ys[-1] + 62

    draw.line(
        [W / 2 - 230, divider_y, W / 2 - 18, divider_y],
        fill=GOLD,
        width=3,
    )
    draw.line(
        [W / 2 + 18, divider_y, W / 2 + 230, divider_y],
        fill=GOLD,
        width=3,
    )
    draw.polygon(
        [
            (W / 2, divider_y - 9),
            (W / 2 + 9, divider_y),
            (W / 2, divider_y + 9),
            (W / 2 - 9, divider_y),
        ],
        fill=GOLD,
    )

    watermark = (script.get("watermark") or "").upper()

    if watermark:
        selected_font = font(30)
        total = sum(
            draw.textlength(char, font=selected_font) + 7
            for char in watermark
        ) - 7

        x = (W - total) / 2

        for char in watermark:
            draw.text(
                (x, 1575),
                char,
                font=selected_font,
                fill=(160, 138, 118),
                anchor="lm",
            )
            x += draw.textlength(
                char, font=selected_font
            ) + 7

    return image
