"""Optimize symbol geometry against reference using polar ring sampling."""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
from compare_symbol_full import align_mse, parse_path, ref_mask

REF_CX, REF_CY = 22.88, 22.58


def polar(cx, cy, r, deg):
    rad = math.radians(deg)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def ring_pts(cx, cy, ro, ri, os_, oe, is_, ie, n=64):
    outer = [polar(cx, cy, ro, a) for a in np.linspace(os_, oe, n)]
    inner = [polar(cx, cy, ri, a) for a in np.linspace(ie, is_, n)]
    return outer + inner


def blue_pts(d: str):
    return parse_path(d)


def render_polys(polys, size=480):
    scale = size / 48.0
    canvas = np.zeros((size, size), np.uint8)
    for poly in polys:
        arr = np.array([[int(x * scale), int(y * scale)] for x, y in poly], np.int32)
        if len(arr) >= 3:
            cv2.fillPoly(canvas, [arr], 255)
    return canvas


def ring_path(cx, cy, ro, ri, os_, oe, is_, ie):
    ox0, oy0 = polar(cx, cy, ro, os_)
    ox1, oy1 = polar(cx, cy, ro, oe)
    ix1, iy1 = polar(cx, cy, ri, ie)
    ix0, iy0 = polar(cx, cy, ri, is_)
    return (
        f"M {ox0:.2f} {oy0:.2f}"
        f" A {ro:.2f} {ro:.2f} 0 1 1 {ox1:.2f} {oy1:.2f}"
        f" L {ix1:.2f} {iy1:.2f}"
        f" A {ri:.2f} {ri:.2f} 0 1 0 {ix0:.2f} {iy0:.2f}"
        f" L {ox0:.2f} {oy0:.2f} Z"
    )


def score(cx, cy, ro, ri, os_, oe, is_, ie, blue_d, ref):
    polys = [ring_pts(cx, cy, ro, ri, os_, oe, is_, ie), blue_pts(blue_d)]
    return align_mse(ref, render_polys(polys, ref.shape[0]))


def main():
    ref = ref_mask(480)
    blue = (
        "M 13.89 46.59"
        " C 18.40 42.80 29.80 27.20 42.02 18.81"
        " C 43.60 17.75 45.30 17.15 46.95 17.93"
        " C 47.15 18.15 47.30 18.45 47.47 18.64"
        " L 47.47 44.40"
        " C 47.47 46.15 45.62 46.55 43.52 46.55"
        " C 41.42 46.55 39.38 45.80 39.38 44.40"
        " L 39.38 32.35"
        " C 39.38 30.15 34.60 36.80 28.66 40.80"
        " C 24.97 43.20 20.50 46.00 19.87 47.30"
        " C 17.80 47.15 15.60 46.80 13.89 46.59 Z"
    )
    best = (1e9, None)
    for cx in np.arange(21.8, 23.2, 0.2):
        for cy in np.arange(21.8, 23.2, 0.2):
            for ro in np.arange(19.2, 20.0, 0.2):
                ri = ro * (12.65 / 20.25)
                for oe in [326, 328, 330]:
                    s = score(cx, cy, ro, ri, 58, oe, 62, 323.5, blue, ref)
                    if s < best[0]:
                        cfg = (cx, cy, ro, ri, oe)
                        best = (s, cfg)
    print("best", best)
    cx, cy, ro, ri, oe = best[1]
    print(ring_path(cx, cy, ro, ri, 58, oe, 62, 323.5))


if __name__ == "__main__":
    main()
