"""Debug ring polygon fill."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from build_oplyra_symbol import RI, RO, polar
from compare_symbol_full import parse_path

OUT = Path(__file__).resolve().parents[1] / "app/static/img/_compare"


def ring(oe, ie, os_, is_, inner="0 1 0"):
    ox0, oy0 = polar(RO, os_)
    ox1, oy1 = polar(RO, oe)
    ix1, iy1 = polar(RI, ie)
    ix0, iy0 = polar(RI, is_)
    return (
        f"M {ox0:.2f} {oy0:.2f} A {RO:.2f} {RO:.2f} 0 1 1 {ox1:.2f} {oy1:.2f}"
        f" L {ix1:.2f} {iy1:.2f} A {RI:.2f} {RI:.2f} {inner} {ix0:.2f} {iy0:.2f}"
        f" L {ox0:.2f} {oy0:.2f} Z"
    )


def render(name, rd, pts):
    s = 480 / 48
    img = np.ones((480, 480, 3), np.uint8) * 255
    na = np.array([[int(x * s), int(y * s)] for x, y in parse_path(rd)], np.int32)
    cv2.fillPoly(img, [na], (10, 22, 41))
    cv2.polylines(img, [na], True, (200, 0, 0), 1)
    cn = np.zeros((480, 480), np.uint8)
    cv2.fillPoly(cn, [na], 255)
    for x, y, label in pts:
        inside = cn[int(y * s), int(x * s)] > 0
        color = (255, 0, 255) if inside else (0, 180, 0)
        cv2.circle(img, (int(x * s), int(y * s)), 4, color, -1)
        cv2.putText(img, label, (int(x * s) + 6, int(y * s)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
    OUT.mkdir(exist_ok=True)
    Image.fromarray(img).save(OUT / name)


pts = [
    (35, 25, "diag"),
    (41.85, 18.72, "sh"),
    (42.06, 17.56, "RO"),
    (45, 30, "leg"),
    (30, 35, "mid"),
]

render("ring_long_inner.png", ring(330, 323.5, 58, 62, "0 1 0"), pts)
render("ring_short_inner.png", ring(330, 323.5, 58, 62, "0 0 1"), pts)

# Try pulling OE earlier to open shoulder gap
for oe, ie in [(318, 310), (325, 318), (335, 325)]:
    render(f"ring_oe{oe}.png", ring(oe, ie, 58, 62, "0 1 0"), pts)

print("saved ring debug images")
