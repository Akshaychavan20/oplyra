"""Visualize navy/blue overlap region."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from build_oplyra_symbol import paths, ring_path, blue_path, CX, CY, RO, RI
from compare_symbol_full import parse_path

OUT = Path(__file__).resolve().parents[1] / "app" / "static" / "img" / "_compare"


def render_path(d: str, size: int = 480) -> np.ndarray:
    scale = size / 48
    canvas = np.zeros((size, size), np.uint8)
    poly = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(d)], np.int32)
    if len(poly) >= 3:
        cv2.fillPoly(canvas, [poly], 255)
    return canvas


def main() -> None:
    OUT.mkdir(exist_ok=True)
    p = paths()
    navy = render_path(p["navy"])
    blue = render_path(p["blue"])
    overlap = cv2.bitwise_and(navy, blue)

    combo = np.zeros((480, 480, 3), np.uint8)
    combo[:, :, 1] = navy
    combo[:, :, 2] = blue
    combo[:, :, 0] = overlap
    combo[overlap > 0] = [255, 0, 255]

    Image.fromarray(combo).save(OUT / "overlap_debug.png")
    print("overlap pixels:", cv2.countNonZero(overlap))

    # Sample ring end points
    from build_oplyra_symbol import polar, RING_OUTER_START, RING_OUTER_END, RING_INNER_START, RING_INNER_END

    print("outer start", polar(RO, RING_OUTER_START))
    print("outer end", polar(RO, RING_OUTER_END))
    print("inner end", polar(RI, RING_INNER_END))
    print("inner start", polar(RI, RING_INNER_START))

    # Blue shoulder zone
    bp = parse_path(blue_path())
    top = min(bp, key=lambda p: p[1])
    print("blue top", top)


if __name__ == "__main__":
    main()
