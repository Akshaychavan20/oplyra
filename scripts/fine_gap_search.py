"""Fine search + save best overlap visual."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from build_oplyra_symbol import blue_path, polar, RI, RO
from compare_symbol_full import parse_path
from test_shoulder_fix import overlap_px, BLUE_OLD

OUT = Path(__file__).resolve().parents[1] / "app/static/img/_compare"


def render(oe, ie, blue=BLUE_OLD, os_=58.0, is_=62.0):
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
    return cn, cb


def main() -> None:
    best = (99999, 330.0, 323.5)
    for oe in np.arange(324, 334, 0.25):
        for ie in np.arange(338, 348, 0.25):
            n = overlap_px(oe, ie, BLUE_OLD)
            if n < best[0]:
                best = (n, oe, ie)

    n, oe, ie = best
    print(f"Best overlap={n} OE={oe:.2f} IE={ie:.2f}")
    print(f"  outer end {polar(RO, oe)}")
    print(f"  inner end {polar(RI, ie)}")

    cn, cb = render(oe, ie)
    combo = np.zeros((480, 480, 3), np.uint8)
    combo[:, :, 1] = cn
    combo[:, :, 2] = cb
    combo[cn & cb > 0] = [255, 0, 255]
    OUT.mkdir(exist_ok=True)
    Image.fromarray(combo).save(OUT / "overlap_fixed.png")


if __name__ == "__main__":
    main()
