"""Zone overlap analysis + save debug renders."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from build_oplyra_symbol import CX, CY, RI, RO, blue_path, polar
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


def masks(rd: str, bd: str):
    scale = 480 / 48
    cn = np.zeros((480, 480), np.uint8)
    cb = np.zeros((480, 480), np.uint8)
    na = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(rd)], np.int32)
    ba = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(bd)], np.int32)
    cv2.fillPoly(cn, [na], 255)
    cv2.fillPoly(cb, [ba], 255)
    return cn, cb


def zone_overlap(cn, cb, y0, y1, x0, x1):
    s = 10
    z = cv2.bitwise_and(cn[y0 * s : y1 * s, x0 * s : x1 * s], cb[y0 * s : y1 * s, x0 * s : x1 * s])
    return int(cv2.countNonZero(z))


def save_combo(cn, cb, name):
    combo = np.ones((480, 480, 3), np.uint8) * 255
    combo[cn > 0] = [10, 22, 41]
    combo[cb > 0] = [59, 130, 246]
    combo[cn & cb > 0] = [255, 0, 255]
    OUT.mkdir(exist_ok=True)
    Image.fromarray(combo).save(OUT / name)


def report(label, oe, ie, os_, is_, bd):
    rd = ring_d(oe, ie, os_, is_)
    cn, cb = masks(rd, bd)
    ov = cv2.bitwise_and(cn, cb)
    total = int(cv2.countNonZero(ov))
    shoulder = zone_overlap(cn, cb, 14, 24, 30, 48)
    bottom = zone_overlap(cn, cb, 30, 48, 20, 48)
    mid = zone_overlap(cn, cb, 20, 35, 25, 45)
    print(f"{label}: total={total} shoulder={shoulder} mid={mid} bottom={bottom}")
    print(f"  OE={oe} IE={ie} OS={os_} IS={is_}")
    print(f"  outer end {polar(RO, oe)}")
    return cn, cb, total


def main() -> None:
    cur = blue_path()
    ro_blue = blue_on_ro(348.1)

    report("CURRENT long inner", 330, 323.5, 58, 62, cur)
    cn, cb, _ = report("FIX chord+short", 340, 328, 52, 52, cur)
    save_combo(cn, cb, "fix_chord_short.png")

    cn, cb, _ = report("FIX chord+short+RO348", 340, 328, 52, 52, ro_blue)
    save_combo(cn, cb, "fix_chord_ro348.png")

    report("FIX radial+short", 343, 343, 55, 55, cur)
    cn, cb, _ = report("FIX radial+short+RO348", 343, 343, 55, 55, ro_blue)
    save_combo(cn, cb, "fix_radial_ro348.png")

    # Fine tune around best
    best = (99999, None)
    for oe in np.arange(336, 346, 0.25):
        for ie in np.arange(oe - 14, oe - 6, 0.25):
            for os_ in np.arange(50, 58, 0.25):
                bd = ro_blue
                rd = ring_d(oe, ie, os_, os_)
                cn, cb = masks(rd, bd)
                n = int(cv2.countNonZero(cv2.bitwise_and(cn, cb)))
                if n < best[0]:
                    best = (n, (oe, ie, os_, bd))
    print(f"\nFine best RO348: {best[0]} params={best[1][:3]}")
    oe, ie, os_, bd = best[1]
    cn, cb, _ = report("FINE BEST", oe, ie, os_, os_, bd)
    save_combo(cn, cb, "fix_fine_best.png")


if __name__ == "__main__":
    main()
