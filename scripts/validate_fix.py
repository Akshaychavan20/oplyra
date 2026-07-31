"""Validate production fix candidate."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from build_oplyra_symbol import RI, RO, polar
from compare_symbol_full import parse_path

OUT = Path(__file__).resolve().parents[1] / "app/static/img/_compare"

# Production candidate
OE, IE, OS, IS = 343.0, 330.0, 58.0, 62.0
SHOULDER_ANG = 348.1


def ring_d():
    ox0, oy0 = polar(RO, OS)
    ox1, oy1 = polar(RO, OE)
    ix1, iy1 = polar(RI, IE)
    ix0, iy0 = polar(RI, IS)
    return (
        f"M {ox0:.2f} {oy0:.2f}"
        f" A {RO:.2f} {RO:.2f} 0 1 1 {ox1:.2f} {oy1:.2f}"
        f" L {ix1:.2f} {iy1:.2f}"
        f" A {RI:.2f} {RI:.2f} 0 0 1 {ix0:.2f} {iy0:.2f}"
        f" L {ox0:.2f} {oy0:.2f} Z"
    )


def blue_d():
    sx, sy = polar(RO, SHOULDER_ANG)
    return (
        f"M 13.92 46.55"
        f" C 18.35 42.75 29.65 27.15 {sx:.2f} {sy:.2f}"
        f" C 43.45 17.72 45.05 17.18 46.82 17.88"
        f" C 47.05 18.08 47.26 18.35 47.47 18.62"
        f" L 47.47 44.38"
        f" C 47.47 46.12 45.64 46.52 43.54 46.52"
        f" C 41.44 46.52 39.40 45.78 39.40 44.38"
        f" L 39.40 32.38"
        f" C 39.40 30.18 34.62 36.82 28.68 40.82"
        f" C 24.99 43.22 20.52 46.02 19.90 47.28"
        f" C 17.82 47.12 15.62 46.78 13.92 46.55 Z"
    )


def main() -> None:
    scale = 480 / 48
    rd, bd = ring_d(), blue_d()
    cn = np.zeros((480, 480), np.uint8)
    cb = np.zeros((480, 480), np.uint8)
    na = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(rd)], np.int32)
    ba = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(bd)], np.int32)
    cv2.fillPoly(cn, [na], 255)
    cv2.fillPoly(cb, [ba], 255)
    ov = cv2.bitwise_and(cn, cb)
    total = int(cv2.countNonZero(ov))
    shoulder = int(cv2.countNonZero(ov[140:240, 300:480]))
    bottom = int(cv2.countNonZero(ov[300:480, 200:480]))
    print(f"total={total} shoulder={shoulder} bottom={bottom}")
    print(f"ring outer end {polar(RO, OE)}")
    print(f"blue shoulder {polar(RO, SHOULDER_ANG)}")

    combo = np.ones((480, 480, 3), np.uint8) * 255
    combo[cn > 0] = [10, 22, 41]
    combo[cb > 0] = [59, 130, 246]
    combo[cn & cb > 0] = [255, 0, 255]
    OUT.mkdir(exist_ok=True)
    Image.fromarray(combo).save(OUT / "production_candidate.png")

    # Sweep OE/IE
    best = (99999, OE, IE)
    for oe in np.arange(340, 346, 0.25):
        for ie in np.arange(oe - 16, oe - 8, 0.25):
            ox0, oy0 = polar(RO, OS)
            ox1, oy1 = polar(RO, oe)
            ix1, iy1 = polar(RI, ie)
            ix0, iy0 = polar(RI, IS)
            rd = (
                f"M {ox0:.2f} {oy0:.2f} A {RO:.2f} {RO:.2f} 0 1 1 {ox1:.2f} {oy1:.2f}"
                f" L {ix1:.2f} {iy1:.2f} A {RI:.2f} {RI:.2f} 0 0 1 {ix0:.2f} {iy0:.2f}"
                f" L {ox0:.2f} {oy0:.2f} Z"
            )
            cn2 = np.zeros((480, 480), np.uint8)
            na2 = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(rd)], np.int32)
            cv2.fillPoly(cn2, [na2], 255)
            n = int(cv2.countNonZero(cv2.bitwise_and(cn2, cb)))
            if n < best[0]:
                best = (n, oe, ie)
    print(f"best OE/IE with RO shoulder: total={best[0]} OE={best[1]} IE={best[2]}")


if __name__ == "__main__":
    main()
