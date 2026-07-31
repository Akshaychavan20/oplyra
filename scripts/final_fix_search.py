"""Final overlap fix search — shoulder + bottom."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from build_oplyra_symbol import RI, RO, polar
from compare_symbol_full import parse_path

OUT = Path(__file__).resolve().parents[1] / "app/static/img/_compare"
SX, SY = polar(RO, 348.1)


def ring(oe, ie, os_, is_, inner: str) -> str:
    ox0, oy0 = polar(RO, os_)
    ox1, oy1 = polar(RO, oe)
    ix1, iy1 = polar(RI, ie)
    ix0, iy0 = polar(RI, is_)
    return (
        f"M {ox0:.2f} {oy0:.2f} A {RO:.2f} {RO:.2f} 0 1 1 {ox1:.2f} {oy1:.2f}"
        f" L {ix1:.2f} {iy1:.2f} A {RI:.2f} {RI:.2f} {inner} {ix0:.2f} {iy0:.2f}"
        f" L {ox0:.2f} {oy0:.2f} Z"
    )


def blue(d2x: float = 31.5, d2y: float = 28.0) -> str:
    return (
        f"M 13.92 46.55 C 18.35 42.75 {d2x:.2f} {d2y:.2f} {SX:.2f} {SY:.2f}"
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


def overlap(n: str, b: str) -> tuple[int, int, int]:
    s = 480 / 48
    cn = np.zeros((480, 480), np.uint8)
    cb = np.zeros((480, 480), np.uint8)
    na = np.array([[int(x * s), int(y * s)] for x, y in parse_path(n)], np.int32)
    ba = np.array([[int(x * s), int(y * s)] for x, y in parse_path(b)], np.int32)
    cv2.fillPoly(cn, [na], 255)
    cv2.fillPoly(cb, [ba], 255)
    o = cv2.bitwise_and(cn, cb)
    t = int(cv2.countNonZero(o))
    sh = int(cv2.countNonZero(o[130:240, 290:480]))
    bot = int(cv2.countNonZero(o[250:480, 200:480]))
    return t, sh, bot


def save(name: str, n: str, b: str) -> None:
    s = 480 / 48
    cn = np.zeros((480, 480), np.uint8)
    cb = np.zeros((480, 480), np.uint8)
    na = np.array([[int(x * s), int(y * s)] for x, y in parse_path(n)], np.int32)
    ba = np.array([[int(x * s), int(y * s)] for x, y in parse_path(b)], np.int32)
    cv2.fillPoly(cn, [na], 255)
    cv2.fillPoly(cb, [ba], 255)
    img = np.ones((480, 480, 3), np.uint8) * 255
    img[cn > 0] = [10, 22, 41]
    img[cb > 0] = [59, 130, 246]
    img[cn & cb > 0] = [255, 0, 255]
    OUT.mkdir(exist_ok=True)
    Image.fromarray(img).save(OUT / name)


def main() -> None:
    best = (99999, None)
    for inner in ("0 0 1", "0 1 0"):
        for oe in np.arange(340, 348, 0.5):
            if inner == "0 0 1":
                ie_vals = [oe]
                is_offsets = [0, 2, 4]
            else:
                ie_vals = np.arange(oe - 14, oe - 6, 0.5)
                is_offsets = [4]
            for ie in ie_vals:
                for os_ in np.arange(58, 72, 0.5):
                    for off in is_offsets:
                        is_ = os_ + off
                        for d2x in [29.65, 31.0, 31.5, 32.5]:
                            for d2y in [27.15, 28.0, 28.5, 29.5]:
                                n = ring(oe, ie, os_, is_, inner)
                                b = blue(d2x, d2y)
                                t, sh, bot = overlap(n, b)
                                if t < best[0]:
                                    best = (t, (oe, ie, os_, is_, inner, d2x, d2y, sh, bot))

    t, p = best
    oe, ie, os_, is_, inner, d2x, d2y, sh, bot = p
    print(f"Best total={t} shoulder={sh} bottom={bot}")
    print(f"  OE={oe} IE={ie} OS={os_} IS={is_} inner={inner}")
    print(f"  d2=({d2x},{d2y}) shoulder=({SX:.2f},{SY:.2f})")
    n = ring(oe, ie, os_, is_, inner)
    b = blue(d2x, d2y)
    save("best_overlap_fix.png", n, b)


if __name__ == "__main__":
    main()
