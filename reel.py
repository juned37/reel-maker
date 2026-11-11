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
