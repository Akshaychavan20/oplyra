"""Locate overlap regions and sweep all four gap termini."""
from __future__ import annotations

import cv2
import numpy as np

from build_oplyra_symbol import CX, CY, RI, RO, blue_path, polar
from compare_symbol_full import parse_path


def ring_d(os_: float, oe: float, is_: float, ie: float) -> str:
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


def render(d: str, size: int = 480) -> np.ndarray:
    scale = size / 48
    c = np.zeros((size, size), np.uint8)
    poly = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(d)], np.int32)
    if len(poly) >= 3:
        import cv2

        cv2.fillPoly(c, [poly], 255)
    return c


def overlap(os_, oe, is_, ie):
    n = render(ring_d(os_, oe, is_, ie))
    b = render(blue_path())
    return int(np.count_nonzero(n & b)), n & b


def main() -> None:
    import cv2
    from PIL import Image
    from pathlib import Path

    n, inter = overlap(58, 330, 62, 323.5)
    print("current overlap", n)

    # Where is overlap?
    ys, xs = np.where(inter > 0)
    if len(xs):
        print(f"overlap x [{xs.min()/10:.1f},{xs.max()/10:.1f}] y [{ys.min()/10:.1f},{ys.max()/10:.1f}] vb")

    best = []
    for oe in np.arange(308, 342, 1):
        for ie in np.arange(oe - 8, oe - 3, 1):
            for os_ in np.arange(54, 64, 1):
                for is_ in np.arange(os_ + 2, os_ + 8, 1):
                    n, _ = overlap(os_, oe, is_, ie)
                    best.append((n, os_, oe, is_, ie))
    best.sort()
    print("\nTop 10 configs:")
    for row in best[:10]:
        print(row)

    # Save best visual
    _, os_, oe, is_, ie = best[0]
    n = render(ring_d(os_, oe, is_, ie))
    b = render(blue_path())
    combo = np.zeros((480, 480, 3), np.uint8)
    combo[:, :, 1] = n
    combo[:, :, 2] = b
    combo[n & b > 0] = [255, 0, 255]
    out = Path(__file__).resolve().parents[1] / "app/static/img/_compare"
    Image.fromarray(combo).save(out / "overlap_best.png")
    print(f"\nBest: OE={oe} IE={ie} OS={os_} IS={is_} overlap={best[0][0]}")


if __name__ == "__main__":
    main()
