"""Locate overlap pixel centroids."""
from __future__ import annotations

import cv2
import numpy as np

from build_oplyra_symbol import RI, RO, polar
from compare_symbol_full import parse_path

OE, IE, OS, IS = 340.5, 324.5, 58.0, 62.0
SHOULDER = 348.1


def ring_d(oe, ie, os_, is_):
    ox0, oy0 = polar(RO, os_)
    ox1, oy1 = polar(RO, oe)
    ix1, iy1 = polar(RI, ie)
    ix0, iy0 = polar(RI, is_)
    return (
        f"M {ox0:.2f} {oy0:.2f} A {RO:.2f} {RO:.2f} 0 1 1 {ox1:.2f} {oy1:.2f}"
        f" L {ix1:.2f} {iy1:.2f} A {RI:.2f} {RI:.2f} 0 0 1 {ix0:.2f} {iy0:.2f}"
        f" L {ox0:.2f} {oy0:.2f} Z"
    )


def blue_d():
    sx, sy = polar(RO, SHOULDER)
    return (
        f"M 13.92 46.55 C 18.35 42.75 29.65 27.15 {sx:.2f} {sy:.2f}"
        f" C 43.45 17.72 45.05 17.18 46.82 17.88"
        f" C 47.05 18.08 47.26 18.35 47.47 18.62 L 47.47 44.38"
        f" C 47.47 46.12 45.64 46.52 43.54 46.52"
        f" C 41.44 46.52 39.40 45.78 39.40 44.38 L 39.40 32.38"
        f" C 39.40 30.18 34.62 36.82 28.68 40.82"
        f" C 24.99 43.22 20.52 46.02 19.90 47.28"
        f" C 17.82 47.12 15.62 46.78 13.92 46.55 Z"
    )


scale = 480 / 48
rd = ring_d(OE, IE, OS, IS)
bd = blue_d()
cn = np.zeros((480, 480), np.uint8)
cb = np.zeros((480, 480), np.uint8)
na = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(rd)], np.int32)
ba = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(bd)], np.int32)
cv2.fillPoly(cn, [na], 255)
cv2.fillPoly(cb, [ba], 255)
ov = cn & cb
ys, xs = np.where(ov > 0)
print(f"overlap pixels: {len(xs)}")
print(f"x range vb: {xs.min()/scale:.1f}-{xs.max()/scale:.1f}")
print(f"y range vb: {ys.min()/scale:.1f}-{ys.max()/scale:.1f}")

# Cluster by y bands
for y0, y1, label in [(14, 22, "shoulder"), (22, 32, "mid"), (32, 48, "bottom")]:
    m = (ys >= y0 * scale) & (ys < y1 * scale)
    if m.any():
        print(f"  {label}: x {xs[m].min()/scale:.1f}-{xs[m].max()/scale:.1f} count={m.sum()}")

# Test increasing OS (wider bottom gap)
print("\nOS sweep (OE=340.5 IE=324.5):")
for os_ in range(58, 68):
    rd = ring_d(OE, IE, os_, os_ + 4)
    cn2 = np.zeros((480, 480), np.uint8)
    na2 = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(rd)], np.int32)
    cv2.fillPoly(cn2, [na2], 255)
    n = int(cv2.countNonZero(cn2 & cb))
    print(f"  OS={os_} IS={os_+4}: {n}")
