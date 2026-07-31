"""Compare handcrafted SVG against reference at multiple zoom levels."""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "app/static/img/oplyra-symbol-reference.png"
SVG_PATHS = ROOT / "app/static/img/oplyra-symbol-paths.json"
OUT = ROOT / "app/static/img/_compare"

# Import geometry from build script
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from build_oplyra_symbol import paths, CX, CY


def render_paths_to_rgba(size: int = 480) -> np.ndarray:
    """Rasterize SVG paths manually via OpenCV fill."""
    import json
    p = json.loads(SVG_PATHS.read_text()) if SVG_PATHS.exists() else paths()
    scale = size / 48.0
    canvas = np.zeros((size, size, 4), dtype=np.uint8)

    def parse_simple_path(d: str) -> list[tuple[float, float]]:
        """Parse M/L/H/V/C/A/Z path into polygon approximation."""
        pts: list[tuple[float, float]] = []
        tokens = d.replace(",", " ").split()
        i = 0
        cx, cy = 0.0, 0.0

        def num() -> float:
            nonlocal i
            v = float(tokens[i])
            i += 1
            return v

        while i < len(tokens):
            cmd = tokens[i]
            i += 1
            if cmd == "M":
                cx, cy = num(), num()
                pts.append((cx, cy))
            elif cmd == "L":
                cx, cy = num(), num()
                pts.append((cx, cy))
            elif cmd == "H":
                cx = num()
                pts.append((cx, cy))
            elif cmd == "V":
                cy = num()
                pts.append((cx, cy))
            elif cmd == "C":
                x1, y1, x2, y2, cx, cy = num(), num(), num(), num(), num(), num()
                for t in np.linspace(0, 1, 12)[1:]:
                    t1 = 1 - t
                    x = t1**3 * pts[-1][0] + 3 * t1**2 * t * x1 + 3 * t1 * t**2 * x2 + t**3 * cx
                    y = t1**3 * pts[-1][1] + 3 * t1**2 * t * y1 + 3 * t1 * t**2 * y2 + t**3 * cy
                    pts.append((x, y))
            elif cmd == "A":
                rx, ry = num(), num()
                rot = num()
                large = int(num())
                sweep = int(num())
                ex, ey = num(), num()
                # approximate arc with segments
                sx, sy = cx, cy
                for t in np.linspace(0, 1, 24)[1:]:
                    ang0 = math.atan2(sy - CY, sx - CX)
                    ang1 = math.atan2(ey - CY, ex - CX)
                    if sweep:
                        if ang1 < ang0:
                            ang1 += 2 * math.pi
                    else:
                        if ang1 > ang0:
                            ang1 -= 2 * math.pi
                    a = ang0 + t * (ang1 - ang0)
                    r = math.hypot(sx - CX, sy - CY)
                    cx, cy = CX + r * math.cos(a), CY + r * math.sin(a)
                    pts.append((cx, cy))
                cx, cy = ex, ey
            elif cmd == "Z":
                pass
        return pts

    def fill_path(d: str, color: tuple[int, int, int, int]):
        poly = np.array([[int(x * scale), int(y * scale)] for x, y in parse_simple_path(d)], np.int32)
        if len(poly) >= 3:
            overlay = canvas.copy()
            cv2.fillPoly(overlay, [poly], color)
            alpha = overlay[:, :, 3:4] / 255.0
            canvas[:, :, :3] = (overlay[:, :, :3] * alpha + canvas[:, :, :3] * (1 - alpha)).astype(np.uint8)
            canvas[:, :, 3] = np.maximum(canvas[:, :, 3], overlay[:, :, 3])

    fill_path(p["navy"], (10, 22, 41, 255))
    fill_path(p["blue"], (59, 130, 246, 255))
    return canvas


def load_ref_rgba(size: int = 480) -> np.ndarray:
    img = cv2.imread(str(REF), cv2.IMREAD_UNCHANGED)
    gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    coords = cv2.findNonZero(th)
    x, y, w, h = cv2.boundingRect(coords)
    crop = img[y : y + h, x : x + w]
    pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGBA))
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    scaled = pil.copy()
    scaled.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas.paste(scaled, ((size - scaled.width) // 2, (size - scaled.height) // 2), scaled)
    return np.array(canvas)


def mse(a: np.ndarray, b: np.ndarray) -> float:
    mask = (a[:, :, 3] > 32) | (b[:, :, 3] > 32)
    diff = (a[:, :, :3].astype(float) - b[:, :, :3].astype(float))
    return float(np.mean(diff[mask] ** 2))


def main():
    OUT.mkdir(exist_ok=True)
    ref_base = load_ref_rgba(480)
    for zoom, label in [(1, "100"), (2, "200"), (4, "400"), (8, "800")]:
        size = 48 * zoom
        ref = np.array(Image.fromarray(ref_base).resize((size, size), Image.Resampling.LANCZOS))
        built = render_paths_to_rgba(size)
        # align canvases
        score = mse(ref, built)
        combo = np.zeros((size, size * 2 + 20, 4), dtype=np.uint8)
        combo[:, :size] = ref
        combo[:, size + 20 :] = built
        Image.fromarray(combo).save(OUT / f"compare_{label}pct.png")
        print(f"{label}%  size={size}px  MSE={score:.1f}")

    print(f"Saved comparisons to {OUT}")


if __name__ == "__main__":
    main()
