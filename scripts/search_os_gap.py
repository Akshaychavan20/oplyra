"""Search OS/OE to eliminate bottom + shoulder overlap."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from build_oplyra_symbol import RI, RO, blue_path, polar
from compare_symbol_full import parse_path

OUT = Path(__file__).resolve().parents[1] / "app/static/img/_compare"


def ring_d(oe, ie, os_, is_):
    ox0, oy0 = polar(RO, os_)
    ox1, oy1 = polar(RO, oe)
    ix1, iy1 = polar(RI, ie)
    ix0, iy0 = polar(RI, is_)
    return (
        f"M {ox0:.2f} {oy0:.2f}"
        f" A {RO:.2f} {RO:.2f} 0 1 1 {ox1:.2f} {oy1:.2f}"
        f" L {ix1:.2f} {iy1:.2f}"
        f" A {RI:.2f} {RI:.2f} 0 0 1 {ix0:.2f} {iy0:.2f}"
        f" L {ox0:.2f} {oy0:.2f} Z"
    )


def blue_on_ro(shoulder_ang: float) -> str:
    sx, sy = polar(RO, shoulder_ang)
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


def overlap_zones(rd, bd):
    scale = 480 / 48
    cn = np.zeros((480, 480), np.uint8)
    cb = np.zeros((480, 480), np.uint8)
    na = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(rd)], np.int32)
    ba = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(bd)], np.int32)
    cv2.fillPoly(cn, [na], 255)
    cv2.fillPoly(cb, [ba], 255)
    ov = cv2.bitwise_and(cn, cb)
    total = int(cv2.countNonZero(ov))
    s = 10
    shoulder = int(cv2.countNonZero(ov[140:240, 300:480]))
    bottom = int(cv2.countNonZero(ov[300:480, 200:480]))
    return total, shoulder, bottom


def save(cn_path, bd, name):
    scale = 480 / 48
    cn = np.zeros((480, 480), np.uint8)
    cb = np.zeros((480, 480), np.uint8)
    na = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(cn_path)], np.int32)
    ba = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(bd)], np.int32)
    cv2.fillPoly(cn, [na], 255)
    cv2.fillPoly(cb, [ba], 255)
    combo = np.ones((480, 480, 3), np.uint8) * 255
    combo[cn > 0] = [10, 22, 41]
    combo[cb > 0] = [59, 130, 246]
    combo[cn & cb > 0] = [255, 0, 255]
    OUT.mkdir(exist_ok=True)
    Image.fromarray(combo).save(OUT / name)


def main() -> None:
    cur = blue_path()
    ro348 = blue_on_ro(348.1)

    print("=== Current blue, short inner, OS 55-65 ===")
    best = (99999, None)
    for oe in np.arange(332, 346, 0.5):
        for ie in np.arange(oe - 14, oe - 4, 0.5):
            for os_ in np.arange(55, 66, 0.5):
                for is_ in [os_, os_ + 2, os_ + 4]:
                    rd = ring_d(oe, ie, os_, is_)
                    t, sh, bt = overlap_zones(rd, cur)
                    if t < best[0]:
                        best = (t, (oe, ie, os_, is_, "cur"))

    print(f"Best: total={best[0]} {best[1]}")
    oe, ie, os_, is_, _ = best[1]
    rd = ring_d(oe, ie, os_, is_)
    save(rd, cur, "best_cur_blue.png")

    print("\n=== RO348 shoulder, short inner, OS 55-65 ===")
    best2 = (99999, None)
    for oe in np.arange(332, 346, 0.5):
        for ie in np.arange(oe - 14, oe - 4, 0.5):
            for os_ in np.arange(55, 66, 0.5):
                for is_ in [os_, os_ + 2, os_ + 4]:
                    rd = ring_d(oe, ie, os_, is_)
                    t, sh, bt = overlap_zones(rd, ro348)
                    if t < best2[0]:
                        best2 = (t, (oe, ie, os_, is_, t, sh, bt))

    print(f"Best: {best2}")
    oe, ie, os_, is_, t, sh, bt = best2[1]
    rd = ring_d(oe, ie, os_, is_)
    save(rd, ro348, "best_ro348.png")

    # Try original OS=58,62 with short inner and tuned OE/IE
    print("\n=== Near-original OS=58,62 ===")
    best3 = (99999, None)
    for oe in np.arange(332, 348, 0.25):
        for ie in np.arange(oe - 14, oe - 2, 0.25):
            for bd_name, bd in [("cur", cur), ("ro348", ro348)]:
                rd = ring_d(oe, ie, 58, 62)
                t, sh, bt = overlap_zones(rd, bd)
                if t < best3[0]:
                    best3 = (t, (oe, ie, 58, 62, bd_name, sh, bt))
    print(f"Best: {best3}")


if __name__ == "__main__":
    main()
