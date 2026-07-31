"""Compare full symbol SVG against reference — with proper arc sampling."""
from __future__ import annotations

import math
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REF = Path(
    r"C:\Users\Akshay\.cursor\projects\c-Users-Akshay-genny-ai\assets"
    r"\c__Users_Akshay_AppData_Roaming_Cursor_User_workspaceStorage_f7337cc95f5ba528b69c3b79148b1fa9"
    r"_images_Screenshot_2026-07-12_200141-983c3cfd-1692-484d-b17a-5a34acd23775.png"
)
OUT = ROOT / "app" / "static" / "img" / "_compare"


def ref_mask(size: int = 480) -> np.ndarray:
    img = cv2.imread(str(REF))
    gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    x, y, w, h = cv2.boundingRect(cv2.findNonZero(th))
    crop = img[y : y + h, x : x + w]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    scale = size / max(w, h)
    m = cv2.resize(th, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_NEAREST)
    canvas = np.zeros((size, size), np.uint8)
    ox, oy = (size - m.shape[1]) // 2, (size - m.shape[0]) // 2
    canvas[oy : oy + m.shape[0], ox : ox + m.shape[1]] = m
    return canvas


def _arc_points(x0, y0, rx, ry, phi, large, sweep, x1, y1, n=48):
    """Sample SVG elliptical arc per W3C implementation notes."""
    if rx == 0 or ry == 0:
        return [(x1, y1)]
    phi_r = math.radians(phi)
    cos_p, sin_p = math.cos(phi_r), math.sin(phi_r)

    def rot(x, y):
        return cos_p * x + sin_p * y, -sin_p * x + cos_p * y

    def derot(x, y):
        return cos_p * x - sin_p * y, sin_p * x + cos_p * y

    x1p, y1p = rot((x0 - x1) / 2, (y0 - y1) / 2)
    rx, ry = abs(rx), abs(ry)
    lam = (x1p / rx) ** 2 + (y1p / ry) ** 2
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    sign = 1 if large == sweep else -1
    num = max((rx * ry) ** 2 - (rx * y1p) ** 2 - (ry * x1p) ** 2, 0)
    den = (rx * y1p) ** 2 + (ry * x1p) ** 2
    coef = sign * math.sqrt(num / den) if den else 0
    cxp = coef * (rx * y1p / ry)
    cyp = coef * (-ry * x1p / rx)
    cx, cy = derot(cxp, cyp)
    cx += (x0 + x1) / 2
    cy += (y0 + y1) / 2

    def angle(u, v):
        return math.atan2(u, v)

    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    a0 = angle(ux, uy)
    da = angle(ux * vy - uy * vx, ux * vx + uy * vy)
    if sweep == 0 and da > 0:
        da -= 2 * math.pi
    if sweep == 1 and da < 0:
        da += 2 * math.pi

    pts = []
    for t in np.linspace(0, 1, n)[1:]:
        a = a0 + da * t
        px, py = rx * math.cos(a), ry * math.sin(a)
        ox, oy = derot(px, py)
        pts.append((ox + cx, oy + cy))
    return pts


def parse_path(d: str) -> list[tuple[float, float]]:
    tokens = re.sub(r"([MLACZ])", r" \1 ", d).split()
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
            for t in np.linspace(0, 1, 16)[1:]:
                t1 = 1 - t
                x = t1**3 * pts[-1][0] + 3 * t1**2 * t * x1 + 3 * t1 * t**2 * x2 + t**3 * cx
                y = t1**3 * pts[-1][1] + 3 * t1**2 * t * y1 + 3 * t1 * t**2 * y2 + t**3 * cy
                pts.append((x, y))
            i += 6
        elif cmd == "A":
            rx, ry = float(tokens[i]), float(tokens[i + 1])
            rot = float(tokens[i + 2])
            large = int(float(tokens[i + 3]))
            sweep = int(float(tokens[i + 4]))
            ex, ey = float(tokens[i + 5]), float(tokens[i + 6])
            i += 7
            sx, sy = cx, cy
            for px, py in _arc_points(sx, sy, rx, ry, rot, large, sweep, ex, ey):
                pts.append((px, py))
            cx, cy = ex, ey
        elif cmd == "Z":
            pass
    return pts


def render_paths(navy: str, blue: str, size: int = 480) -> np.ndarray:
    """Render symbol; navy ring uses polar arc sampling for accuracy."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from build_oplyra_symbol import (
        CX,
        CY,
        RI,
        RING_INNER_END,
        RING_INNER_START,
        RING_OUTER_END,
        RING_OUTER_START,
        RO,
    )
    from tune_full_symbol import ring_pts

    scale = size / 48.0
    canvas = np.zeros((size, size), np.uint8)
    polys = [
        ring_pts(CX, CY, RO, RI, RING_OUTER_START, RING_OUTER_END, RING_INNER_START, RING_INNER_END),
        parse_path(blue),
    ]
    for poly in polys:
        arr = np.array([[int(x * scale), int(y * scale)] for x, y in poly], np.int32)
        if len(arr) >= 3:
            cv2.fillPoly(canvas, [arr], 255)
    return canvas


def align_mse(ref: np.ndarray, built: np.ndarray) -> float:
    rb = cv2.moments(ref)
    bb = cv2.moments(built)
    if rb["m00"] and bb["m00"]:
        dx = int(rb["m10"] / rb["m00"] - bb["m10"] / bb["m00"])
        dy = int(rb["m01"] / rb["m00"] - bb["m01"] / bb["m00"])
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        built = cv2.warpAffine(built, M, built.shape[::-1])
    mask = (ref > 0) | (built > 0)
    if not mask.any():
        return 9999.0
    return float(np.mean((ref.astype(float) - built.astype(float))[mask] ** 2))


def main() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from build_oplyra_symbol import paths

    OUT.mkdir(exist_ok=True)
    p = paths()
    for zoom, label in [(1, "100"), (2, "200"), (4, "400"), (8, "800")]:
        size = 48 * zoom
        ref = ref_mask(size)
        built = render_paths(p["navy"], p["blue"], size)
        mse = align_mse(ref, built)
        combo = np.zeros((size, size * 2 + 16, 3), np.uint8)
        combo[:, :size, 1] = ref
        combo[:, size + 16 :, 0] = built // 3
        combo[:, size + 16 :, 2] = built
        Image.fromarray(combo).save(OUT / f"symbol_{label}pct.png")
        print(f"{label}%  MSE={mse:.1f}")


if __name__ == "__main__":
    main()
