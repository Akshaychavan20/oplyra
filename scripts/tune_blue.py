"""Tune blue path control points against reference mask."""
from __future__ import annotations

import math
import re
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REF = Path(
    r"C:\Users\Akshay\.cursor\projects\c-Users-Akshay-genny-ai\assets"
    r"\c__Users_Akshay_AppData_Roaming_Cursor_User_workspaceStorage_f7337cc95f5ba528b69c3b79148b1fa9"
    r"_images_Screenshot_2026-07-12_200141-70b73472-e54b-4ca9-8999-8534a69964d7.png"
)


def ref_blue_mask(size: int = 480) -> np.ndarray:
    img = cv2.imread(str(REF))
    gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    x, y, w, h = cv2.boundingRect(cv2.findNonZero(th))
    crop = img[y : y + h, x : x + w]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    navy = cv2.inRange(hsv, (90, 80, 20), (130, 255, 80))
    blue = cv2.inRange(hsv, (90, 100, 80), (130, 255, 255))
    blue = cv2.bitwise_and(blue, cv2.bitwise_not(navy))
    scale = size / max(w, h)
    m = cv2.resize(blue, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_NEAREST)
    canvas = np.zeros((size, size), np.uint8)
    ox, oy = (size - m.shape[1]) // 2, (size - m.shape[0]) // 2
    canvas[oy : oy + m.shape[0], ox : ox + m.shape[1]] = m
    return canvas


def parse_path(d: str) -> list[tuple[float, float]]:
    tokens = re.sub(r"([MLCZ])", r" \1 ", d).split()
    pts: list[tuple[float, float]] = []
    i = 0
    cx = cy = 0.0
    while i < len(tokens):
        cmd = tokens[i]
        i += 1
        if cmd == "M":
            cx, cy = float(tokens[i]), float(tokens[i + 1])
            pts.append((cx, cy))
            i += 2
        elif cmd == "L":
            cx, cy = float(tokens[i]), float(tokens[i + 1])
            pts.append((cx, cy))
            i += 2
        elif cmd == "C":
            x1, y1 = float(tokens[i]), float(tokens[i + 1])
            x2, y2 = float(tokens[i + 2]), float(tokens[i + 3])
            cx, cy = float(tokens[i + 4]), float(tokens[i + 5])
            for t in np.linspace(0, 1, 20)[1:]:
                t1 = 1 - t
                x = t1**3 * pts[-1][0] + 3 * t1**2 * t * x1 + 3 * t1 * t**2 * x2 + t**3 * cx
                y = t1**3 * pts[-1][1] + 3 * t1**2 * t * y1 + 3 * t1 * t**2 * y2 + t**3 * cy
                pts.append((x, y))
            i += 6
        elif cmd == "Z":
            pass
    return pts


def render(d: str, size: int = 480) -> np.ndarray:
    scale = size / 48.0
    poly = np.array([[int(x * scale), int(y * scale)] for x, y in parse_path(d)], np.int32)
    canvas = np.zeros((size, size), np.uint8)
    if len(poly) >= 3:
        cv2.fillPoly(canvas, [poly], 255)
    return canvas


def score(d: str, ref: np.ndarray) -> float:
    built = render(d, ref.shape[0])
    # align: ref is centered, our paths use 48vb from origin
    # shift built to match ref centroid
    rb = cv2.moments(ref)
    bb = cv2.moments(built)
    if rb["m00"] and bb["m00"]:
        rcx = rb["m10"] / rb["m00"]
        rcy = rb["m01"] / rb["m00"]
        bcx = bb["m10"] / bb["m00"]
        bcy = bb["m01"] / bb["m00"]
        dx, dy = int(rcx - bcx), int(rcy - bcy)
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        built = cv2.warpAffine(built, M, (built.shape[1], built.shape[0]))
    mask = (ref > 0) | (built > 0)
    if not mask.any():
        return 9999.0
    return float(np.mean((ref.astype(float) - built.astype(float))[mask] ** 2))


def build_path(
    tip_x: float,
    tip_y: float,
    d1x: float,
    d1y: float,
    d2x: float,
    d2y: float,
    sh_x: float,
    sh_y: float,
    in_y: float,
    ic1y: float,
    ic2x: float,
    ic2y: float,
    ic3x: float,
    ic3y: float,
) -> str:
    return (
        f"M {tip_x:.2f} {tip_y:.2f}"
        f" C {d1x:.2f} {d1y:.2f} {d2x:.2f} {d2y:.2f} {sh_x:.2f} {sh_y:.2f}"
        f" C 43.50 17.85 45.05 17.85 46.00 17.85"
        f" L 46.00 44.35"
        f" C 46.00 46.10 44.15 46.50 42.05 46.50"
        f" C 39.95 46.50 38.40 45.75 38.40 44.35"
        f" L 38.40 {in_y:.2f}"
        f" C 38.40 {ic1y:.2f} {ic2x:.2f} {ic2y:.2f} {ic3x:.2f} {ic3y:.2f}"
        f" C 20.50 46.20 16.00 47.05 {tip_x:.2f} {tip_y:.2f}"
        f" Z"
    )


def main() -> None:
    ref = ref_blue_mask(480)
    best = (9999.0, "")
    # grid search around calibrated values
    for tip_x in np.arange(12.8, 14.2, 0.15):
        for tip_y in np.arange(46.5, 47.2, 0.15):
            for d2x in np.arange(30.0, 36.0, 1.0):
                for d2y in np.arange(22.0, 28.0, 1.0):
                    for ic1y in np.arange(29.5, 32.0, 0.5):
                        d = build_path(
                            tip_x, tip_y, 17.5, 43.0, d2x, d2y, 41.0, 18.05,
                            33.6, ic1y, 33.5, 38.0, 26.0, 41.5,
                        )
                        s = score(d, ref)
                        if s < best[0]:
                            best = (s, d)
    print(f"best MSE={best[0]:.1f}")
    print(best[1])


if __name__ == "__main__":
    main()
