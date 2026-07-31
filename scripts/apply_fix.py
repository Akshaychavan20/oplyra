"""Apply and validate production overlap fix."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from build_oplyra_symbol import CX, CY, RI, RO, polar
from compare_symbol_full import parse_path

OUT = Path(__file__).resolve().parents[1] / "app/static/img/_compare"

# Reference-aligned shoulder on outer ring circle (~348.1 deg per extract_gap.py)
SHOULDER_ANG = 348.1


def ring_path(oe: float, ie: float, os_: float, is_: float) -> str:
    ox0, oy0 = polar(RO, os_)
    ox1, oy1 = polar(RO, oe)
    ix1, iy1 = polar(RI, ie)
    ix0, iy0 = polar(RI, is_)
    return (
        f"M {ox0:.2f} {oy0:.2f}"
        f" A {RO:.2f} {RO:.2f} 0 1 1 {ox1:.2f} {oy1:.2f}"
        f" L {ix1:.2f} {iy1:.2f}"
        f" A {RI:.2f} {RI:.2f} 0 1 0 {ix0:.2f} {iy0:.2f}"
        f" L {ox0:.2f} {oy0:.2f} Z"
    )


def blue_path(sx: float, sy: float, d2x: float, d2y: float) -> str:
    return (
        f"M 13.92 46.55"
        f" C 18.35 42.75 {d2x:.2f} {d2y:.2f} {sx:.2f} {sy:.2f}"
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


def overlap(navy: str, blue: str) -> int:
    s = 480 / 48
    cn = np.zeros((480, 480), np.uint8)
    cb = np.zeros((480, 480), np.uint8)
    na = np.array([[int(x * s), int(y * s)] for x, y in parse_path(navy)], np.int32)
    ba = np.array([[int(x * s), int(y * s)] for x, y in parse_path(blue)], np.int32)
    cv2.fillPoly(cn, [na], 255)
    cv2.fillPoly(cb, [ba], 255)
    return int(cv2.countNonZero(cv2.bitwise_and(cn, cb)))


def save(name: str, navy: str, blue: str) -> None:
    s = 480 / 48
    cn = np.zeros((480, 480), np.uint8)
    cb = np.zeros((480, 480), np.uint8)
    na = np.array([[int(x * s), int(y * s)] for x, y in parse_path(navy)], np.int32)
    ba = np.array([[int(x * s), int(y * s)] for x, y in parse_path(blue)], np.int32)
    cv2.fillPoly(cn, [na], 255)
    cv2.fillPoly(cb, [ba], 255)
    img = np.ones((480, 480, 3), np.uint8) * 255
    img[cn > 0] = [10, 22, 41]
    img[cb > 0] = [59, 130, 246]
    img[cn & cb > 0] = [255, 0, 255]
    OUT.mkdir(exist_ok=True)
    Image.fromarray(img).save(OUT / name)


def main() -> None:
    sx, sy = polar(RO, SHOULDER_ANG)
    print(f"Shoulder RO@{SHOULDER_ANG}: ({sx:.2f}, {sy:.2f})")

    best = (99999, None)
    for oe in np.arange(333, 346, 0.5):
        for ie in np.arange(oe - 16, oe - 8, 0.5):
            for os_ in [58.0]:
                for is_ in [62.0]:
                    for d2x in np.arange(30.0, 33.5, 0.25):
                        for d2y in np.arange(26.0, 29.5, 0.25):
                            n = ring_path(oe, ie, os_, is_)
                            b = blue_path(sx, sy, d2x, d2y)
                            o = overlap(n, b)
                            if o < best[0]:
                                best = (o, (oe, ie, os_, is_, d2x, d2y, n, b))

    o, params = best
    oe, ie, os_, is_, d2x, d2y, n, b = params
    print(f"Best overlap={o}")
    print(f"  OE={oe} IE={ie} OS={os_} IS={is_}")
    print(f"  d2=({d2x},{d2y}) shoulder=({sx:.2f},{sy:.2f})")
    save("production_fix.png", n, b)

    # Current baseline
    from build_oplyra_symbol import paths

    p = paths()
    print(f"Current overlap={overlap(p['navy'], p['blue'])}")


if __name__ == "__main__":
    main()
