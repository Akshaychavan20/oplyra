"""Test shoulder fix combinations."""
from __future__ import annotations

import cv2
import numpy as np

from build_oplyra_symbol import RI, RO, polar
from compare_symbol_full import parse_path

BLUE_OLD = (
    "M 13.92 46.55 C 18.35 42.75 29.65 27.15 41.85 18.72"
    " C 43.45 17.72 45.05 17.18 46.82 17.88"
    " C 47.05 18.08 47.26 18.35 47.47 18.62"
    " L 47.47 44.38"
    " C 47.47 46.12 45.64 46.52 43.54 46.52"
    " C 41.44 46.52 39.40 45.78 39.40 44.38"
    " L 39.40 32.38"
    " C 39.40 30.18 34.62 36.82 28.68 40.82"
    " C 24.99 43.22 20.52 46.02 19.90 47.28"
    " C 17.82 47.12 15.62 46.78 13.92 46.55 Z"
)

BLUE_NEW = (
    "M 13.92 46.55 C 18.35 42.75 29.65 27.15 42.06 17.53"
    " C 43.30 17.55 45.05 17.18 46.82 17.88"
    " C 47.05 18.08 47.26 18.35 47.47 18.62"
    " L 47.47 44.38"
    " C 47.47 46.12 45.64 46.52 43.54 46.52"
    " C 41.44 46.52 39.40 45.78 39.40 44.38"
    " L 39.40 32.38"
    " C 39.40 30.18 34.62 36.82 28.68 40.82"
    " C 24.99 43.22 20.52 46.02 19.90 47.28"
    " C 17.82 47.12 15.62 46.78 13.92 46.55 Z"
)


def overlap_px(oe: float, ie: float, blue: str, os_: float = 58.0, is_: float = 62.0) -> int:
    scale = 480 / 48
    ox0, oy0 = polar(RO, os_)
    ox1, oy1 = polar(RO, oe)
    ix1, iy1 = polar(RI, ie)
    ix0, iy0 = polar(RI, is_)
    d = (
        f"M {ox0:.2f} {oy0:.2f}"
        f" A {RO:.2f} {RO:.2f} 0 1 1 {ox1:.2f} {oy1:.2f}"
        f" L {ix1:.2f} {iy1:.2f}"
        f" A {RI:.2f} {RI:.2f} 0 1 0 {ix0:.2f} {iy0:.2f}"
        f" L {ox0:.2f} {oy0:.2f} Z"
    )
    cn = np.zeros((480, 480), np.uint8)
    cb = np.zeros((480, 480), np.uint8)
    na = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(d)], np.int32)
    ba = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(blue)], np.int32)
    cv2.fillPoly(cn, [na], 255)
    cv2.fillPoly(cb, [ba], 255)
    return int(cv2.countNonZero(cv2.bitwise_and(cn, cb)))


def main() -> None:
    print("Current:", overlap_px(330, 323.5, BLUE_OLD))
    for oe, ie in [(330, 323.5), (341, 337), (341.5, 337.5), (342, 338), (343, 339)]:
        print(f"OE={oe} IE={ie}  old={overlap_px(oe, ie, BLUE_OLD)}  new={overlap_px(oe, ie, BLUE_NEW)}")


if __name__ == "__main__":
    main()
