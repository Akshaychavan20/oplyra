"""Fast targeted overlap search."""
from __future__ import annotations

import math

import cv2
import numpy as np

from build_oplyra_symbol import CX, CY, RI, RO, blue_path, polar
from compare_symbol_full import parse_path


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


def overlap_px(rd: str, bd: str) -> int:
    scale = 480 / 48
    cn = np.zeros((480, 480), np.uint8)
    cb = np.zeros((480, 480), np.uint8)
    na = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(rd)], np.int32)
    ba = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(bd)], np.int32)
    cv2.fillPoly(cn, [na], 255)
    cv2.fillPoly(cb, [ba], 255)
    return int(cv2.countNonZero(cv2.bitwise_and(cn, cb)))


def main() -> None:
    cur = blue_path()
    print("baseline long inner:", overlap_px(
        "M 39.98 38.95 A 20.30 20.30 0 1 1 19.88 8.62 L 11.35 10.15 A 12.68 12.68 0 1 0 28.35 38.35 L 39.98 38.95 Z", cur))

    # Phase 1: radial cuts + short inner
    print("\n=== Radial (OE=IE, OS=IS) + current blue ===")
    best = (99999, 0, 0)
    for oe in np.arange(340, 348, 0.5):
        for os_ in np.arange(52, 62, 0.5):
            n = overlap_px(ring_d(oe, oe, os_, os_), cur)
            if n < best[0]:
                best = (n, oe, os_)
    print("best:", best)

    # Phase 2: chord top + short inner
    print("\n=== Chord top + current blue ===")
    best2 = (99999, 0, 0, 0, 0)
    for oe in np.arange(340, 348, 0.5):
        for ie in np.arange(oe - 12, oe - 2, 0.5):
            for os_ in np.arange(52, 62, 0.5):
                for is_ in [os_, os_ + 2, os_ + 4]:
                    n = overlap_px(ring_d(oe, ie, os_, is_), cur)
                    if n < best2[0]:
                        best2 = (n, oe, ie, os_, is_)
    print("best:", best2)

    # Phase 3: radial + RO shoulder at oe+gap
    print("\n=== Radial + RO shoulder ===")
    best3 = (99999, 0, 0, 0)
    for oe in np.arange(340, 348, 0.5):
        for gap in np.arange(2.5, 6.0, 0.5):
            for os_ in np.arange(52, 62, 0.5):
                n = overlap_px(ring_d(oe, oe, os_, os_), blue_on_ro(oe + gap))
                if n < best3[0]:
                    best3 = (n, oe, os_, oe + gap)
    print("best:", best3)

    # Phase 4: chord + RO shoulder
    print("\n=== Chord + RO shoulder ===")
    best4 = (99999, 0, 0, 0, 0, 0)
    for oe in np.arange(340, 348, 0.5):
        ie = oe - 8
        for gap in np.arange(3.0, 6.0, 0.5):
            for os_ in np.arange(52, 62, 0.5):
                n = overlap_px(ring_d(oe, ie, os_, os_), blue_on_ro(oe + gap))
                if n < best4[0]:
                    best4 = (n, oe, ie, os_, oe + gap)
    print("best:", best4)

    # Show shoulder point for 348.1 reference
    sx, sy = polar(RO, 348.1)
    print(f"\nRO @348.1° = ({sx:.2f}, {sy:.2f}) r={math.hypot(sx-CX, sy-CY):.2f}")
    print(f"Current blue shoulder (41.85, 18.72) r={math.hypot(41.85-CX, 18.72-CY):.2f}")


if __name__ == "__main__":
    main()
