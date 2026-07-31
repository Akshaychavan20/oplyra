"""Optimize ring gap against reference blue mask (zero overlap target)."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from build_oplyra_symbol import CX, CY, RI, RO, blue_path, polar
from compare_symbol_full import parse_path

REF = Path(
    r"C:\Users\Akshay\.cursor\projects\c-Users-Akshay-genny-ai\assets"
    r"\c__Users_Akshay_AppData_Roaming_Cursor_User_workspaceStorage_f7337cc95f5ba528b69c3b79148b1fa9"
    r"_images_Screenshot_2026-07-12_200141-aeee1779-a7b1-418d-b0cc-6b8c3bbba119.png"
)
OUT = Path(__file__).resolve().parents[1] / "app/static/img/_compare"


def ref_blue_480() -> np.ndarray:
    img = cv2.imread(str(REF))
    gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    x, y, w, h = cv2.boundingRect(cv2.findNonZero(th))
    crop = img[y : y + h, x : x + w]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    blue = cv2.inRange(hsv, (90, 100, 80), (130, 255, 255))
    navy = cv2.inRange(hsv, (90, 80, 20), (130, 255, 80))
    blue = cv2.bitwise_and(blue, cv2.bitwise_not(navy))
    scale = 480 / max(w, h)
    m = cv2.resize(blue, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_NEAREST)
    canvas = np.zeros((480, 480), np.uint8)
    ox, oy = (480 - m.shape[1]) // 2, (480 - m.shape[0]) // 2
    canvas[oy : oy + m.shape[0], ox : ox + m.shape[1]] = m
    return canvas


def ring(oe, ie, os_, is_, inner="0 1 0"):
    ox0, oy0 = polar(RO, os_)
    ox1, oy1 = polar(RO, oe)
    ix1, iy1 = polar(RI, ie)
    ix0, iy0 = polar(RI, is_)
    return (
        f"M {ox0:.2f} {oy0:.2f} A {RO:.2f} {RO:.2f} 0 1 1 {ox1:.2f} {oy1:.2f}"
        f" L {ix1:.2f} {iy1:.2f} A {RI:.2f} {RI:.2f} {inner} {ix0:.2f} {iy0:.2f}"
        f" L {ox0:.2f} {oy0:.2f} Z"
    )


def render(rd: str) -> np.ndarray:
    s = 480 / 48
    cn = np.zeros((480, 480), np.uint8)
    na = np.array([[int(x * s), int(y * s)] for x, y in parse_path(rd)], np.int32)
    cv2.fillPoly(cn, [na], 255)
    return cn


def overlap_with_blue(rd: str, blue_mask: np.ndarray) -> int:
    return int(cv2.countNonZero(cv2.bitwise_and(render(rd), blue_mask)))


def overlap_svg_blue(rd: str) -> int:
    s = 480 / 48
    cb = np.zeros((480, 480), np.uint8)
    ba = np.array([[int(x * s), int(y * s)] for x, y in parse_path(blue_path())], np.int32)
    cv2.fillPoly(cb, [ba], 255)
    return int(cv2.countNonZero(cv2.bitwise_and(render(rd), cb)))


def main() -> None:
    ref_blue = ref_blue_480()
    print("Reference blue px:", int(cv2.countNonZero(ref_blue)))

    best = (99999, None)
    for oe in np.arange(300, 345, 0.5):
        for ie in np.arange(oe - 20, oe - 2, 0.5):
            for os_ in np.arange(55, 72, 0.5):
                for is_ in [os_, os_ + 2, os_ + 4, os_ + 6]:
                    rd = ring(oe, ie, os_, is_, "0 1 0")
                    n = overlap_with_blue(rd, ref_blue)
                    if n < best[0]:
                        best = (n, (oe, ie, os_, is_))

    print("Best vs ref blue (long inner):", best)

    oe, ie, os_, is_ = best[1]
    rd = ring(oe, ie, os_, is_, "0 1 0")
    n_svg = overlap_svg_blue(rd)
    print(f"Same config vs SVG blue: {n_svg}")
    print(f"OE={oe} IE={ie} OS={os_} IS={is_}")
    print(f"outer end {polar(RO, oe)}")
    print(f"outer start {polar(RO, os_)}")

    combo = np.ones((480, 480, 3), np.uint8) * 255
    cn = render(rd)
    combo[cn > 0] = [10, 22, 41]
    combo[ref_blue > 0] = np.minimum(combo[ref_blue > 0], [180, 210, 255])
    combo[cn & ref_blue > 0] = [255, 0, 255]
    OUT.mkdir(exist_ok=True)
    Image.fromarray(combo).save(OUT / "ring_vs_ref_blue.png")

    # Also test short inner
    best2 = (99999, None)
    for oe in np.arange(300, 345, 0.5):
        for ie in np.arange(oe - 20, oe - 2, 0.5):
            for os_ in np.arange(55, 72, 0.5):
                for is_ in [os_, os_ + 2, os_ + 4]:
                    rd = ring(oe, ie, os_, is_, "0 0 1")
                    n = overlap_with_blue(rd, ref_blue)
                    if n < best2[0]:
                        best2 = (n, (oe, ie, os_, is_))
    print("Best vs ref blue (short inner):", best2)


if __name__ == "__main__":
    main()
