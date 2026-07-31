"""Grid search blue shoulder endpoint with fixed ring gap."""
from __future__ import annotations

import cv2
import numpy as np

from build_oplyra_symbol import polar, RI, RO
from compare_symbol_full import parse_path


def blue_at(ex: float, ey: float) -> str:
    return (
        f"M 13.92 46.55"
        f" C 18.35 42.75 29.65 27.15 {ex:.2f} {ey:.2f}"
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


def overlap(oe, ie, os_, is_, blue):
    scale = 480 / 48
    ox0, oy0 = polar(RO, os_)
    ox1, oy1 = polar(RO, oe)
    ix1, iy1 = polar(RI, ie)
    ix0, iy0 = polar(RI, is_)
    rd = (
        f"M {ox0:.2f} {oy0:.2f}"
        f" A {RO:.2f} {RO:.2f} 0 1 1 {ox1:.2f} {oy1:.2f}"
        f" L {ix1:.2f} {iy1:.2f}"
        f" A {RI:.2f} {RI:.2f} 0 1 0 {ix0:.2f} {iy0:.2f}"
        f" L {ox0:.2f} {oy0:.2f} Z"
    )
    cn = np.zeros((480, 480), np.uint8)
    cb = np.zeros((480, 480), np.uint8)
    na = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(rd)], np.int32)
    ba = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(blue)], np.int32)
    cv2.fillPoly(cn, [na], 255)
    cv2.fillPoly(cb, [ba], 255)
    return int(cv2.countNonZero(cv2.bitwise_and(cn, cb)))


def main() -> None:
    oe, ie, os_, is_ = 323.0, 347.5, 56.0, 58.0
    best = (99999, 0.0, 0.0)
    for ex in np.arange(41.5, 43.0, 0.05):
        for ey in np.arange(17.0, 19.5, 0.05):
            n = overlap(oe, ie, os_, is_, blue_at(ex, ey))
            if n < best[0]:
                best = (n, ex, ey)
    print("Best:", best)


if __name__ == "__main__":
    main()
