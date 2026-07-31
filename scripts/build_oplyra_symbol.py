"""
Hand-crafted Oplyra symbol + premium lockup geometry.

Symbol paths are production vectors calibrated against oplyra-symbol-reference.png.
Lockup spacing is optically tuned — symbol and wordmark never overlap.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "static" / "img"

# ── Symbol geometry (48 × 48) — calibrated to official lockup reference ───
CX, CY = 22.20, 21.75
RO = 20.30
RI = 12.4336
RING_OUTER_START = 109.0
RING_OUTER_END = 343.0
RING_INNER_END = 343.0
RING_INNER_START = 109.0
BLUE_SHOULDER_ANG = 348.1

RESTORED_NAVY = "M 24.26 1.27 L 22.22 1.27 L 22.07 1.43 L 20.50 1.43 L 20.34 1.59 L 19.56 1.59 L 19.40 1.74 L 17.99 1.90 L 17.36 2.21 L 16.89 2.21 L 16.73 2.37 L 15.95 2.53 L 14.69 3.16 L 14.38 3.16 L 13.12 3.78 L 12.81 4.10 L 12.02 4.41 L 11.71 4.73 L 10.61 5.35 L 9.35 6.45 L 9.20 6.45 L 6.69 8.96 L 6.69 9.12 L 6.06 9.75 L 6.06 9.91 L 5.59 10.38 L 5.59 10.53 L 4.64 11.79 L 4.02 13.20 L 3.70 13.52 L 3.70 13.83 L 2.92 15.40 L 2.92 15.71 L 2.45 16.81 L 2.13 18.54 L 1.98 18.69 L 1.98 19.32 L 1.82 19.48 L 1.82 20.42 L 1.66 20.58 L 1.66 24.97 L 1.82 25.13 L 1.82 26.07 L 1.98 26.23 L 2.13 27.64 L 2.29 27.80 L 2.29 28.27 L 2.45 28.43 L 3.08 30.62 L 4.02 32.35 L 4.02 32.66 L 4.33 32.98 L 4.64 33.76 L 4.96 34.08 L 5.59 35.18 L 6.06 35.65 L 6.53 36.43 L 9.35 39.26 L 9.51 39.26 L 11.08 40.51 L 11.71 40.83 L 15.63 36.90 L 15.79 36.90 L 15.79 36.74 L 16.10 36.59 L 16.10 36.43 L 16.57 35.96 L 16.73 35.96 L 17.67 35.02 L 17.52 35.02 L 17.20 34.70 L 16.89 34.70 L 16.57 34.39 L 15.32 33.76 L 12.65 31.25 L 11.86 30.00 L 11.39 29.52 L 10.61 27.96 L 10.61 27.64 L 10.30 27.17 L 10.30 26.86 L 9.98 26.23 L 9.98 25.76 L 9.82 25.60 L 9.82 24.82 L 9.67 24.66 L 9.67 23.40 L 9.51 23.25 L 9.67 20.89 L 9.82 20.74 L 9.82 20.11 L 9.98 19.95 L 10.14 18.85 L 10.45 18.38 L 10.45 18.07 L 10.77 17.60 L 10.77 17.28 L 11.39 16.03 L 12.49 14.61 L 12.49 14.46 L 14.69 12.26 L 14.85 12.26 L 15.32 11.79 L 16.26 11.32 L 16.57 11.00 L 17.83 10.38 L 18.14 10.38 L 18.61 10.06 L 18.93 10.06 L 19.56 9.75 L 20.03 9.75 L 20.18 9.59 L 20.65 9.59 L 20.81 9.43 L 21.91 9.43 L 22.07 9.28 L 24.42 9.28 L 24.58 9.43 L 25.52 9.43 L 25.68 9.59 L 26.30 9.59 L 26.46 9.75 L 26.93 9.75 L 27.09 9.91 L 27.87 10.06 L 28.35 10.38 L 28.66 10.38 L 28.97 10.69 L 29.29 10.69 L 29.60 11.00 L 30.86 11.63 L 32.27 12.89 L 32.43 12.89 L 32.58 13.20 L 32.90 13.36 L 32.90 13.52 L 33.21 13.67 L 33.21 13.83 L 34.47 15.24 L 34.94 16.18 L 35.25 16.50 L 35.57 17.44 L 35.72 17.44 L 38.39 14.77 L 38.55 14.77 L 39.02 14.30 L 39.96 13.83 L 40.43 13.83 L 40.59 13.67 L 41.06 13.67 L 41.22 13.52 L 42.47 13.52 L 41.53 11.63 L 41.22 11.32 L 40.27 9.75 L 39.65 9.12 L 39.65 8.96 L 37.13 6.45 L 36.98 6.45 L 36.19 5.67 L 36.04 5.67 L 34.31 4.41 L 31.96 3.16 L 31.64 3.16 L 30.39 2.53 L 30.07 2.53 L 29.44 2.21 L 28.97 2.21 L 28.35 1.90 L 27.09 1.74 L 26.93 1.59 L 25.99 1.59 L 25.83 1.43 L 24.42 1.43 Z"
RESTORED_BLUE = "M 13.28 42.40 L 13.28 42.87 L 13.43 43.02 L 13.91 43.02 L 14.06 43.18 L 14.38 43.18 L 14.53 43.34 L 15.16 43.34 L 15.32 43.49 L 20.34 43.49 L 20.50 43.34 L 21.28 43.34 L 21.44 43.18 L 21.91 43.18 L 22.22 42.87 L 22.69 42.87 L 23.17 42.55 L 23.48 42.55 L 23.64 42.24 L 23.79 42.24 L 24.11 41.92 L 25.21 41.30 L 25.36 40.98 L 25.83 40.83 L 25.99 40.51 L 26.78 39.73 L 26.78 39.57 L 27.09 39.41 L 28.19 38.31 L 28.35 38.31 L 28.50 38.00 L 30.70 35.80 L 31.01 35.65 L 31.17 35.18 L 31.48 35.02 L 31.64 34.70 L 32.11 34.23 L 32.27 34.23 L 32.27 34.08 L 33.05 33.29 L 33.37 33.29 L 33.52 33.13 L 33.68 32.66 L 34.00 32.51 L 34.00 32.35 L 34.31 32.04 L 34.47 32.04 L 34.47 31.88 L 34.94 31.41 L 35.41 31.25 L 35.57 30.94 L 36.19 30.78 L 36.35 30.94 L 36.35 41.61 L 36.66 42.24 L 36.66 42.71 L 37.45 43.49 L 42.94 43.49 L 43.10 43.34 L 43.41 43.34 L 43.41 43.18 L 43.73 43.02 L 44.04 42.55 L 44.04 41.30 L 44.20 41.14 L 44.20 37.69 L 44.04 37.53 L 44.04 37.22 L 44.20 37.06 L 44.20 19.01 L 44.04 18.85 L 44.04 17.28 L 43.41 16.50 L 43.41 16.34 L 42.94 16.03 L 41.37 15.87 L 41.22 16.03 L 40.74 16.03 L 40.27 16.34 L 39.49 16.50 L 39.49 16.81 L 37.76 18.38 L 37.61 18.38 L 37.13 19.17 L 36.19 19.64 L 36.19 20.11 L 35.88 20.26 L 35.72 20.58 L 35.41 20.74 L 34.94 20.74 L 34.94 21.21 L 34.62 21.36 L 34.62 21.52 L 34.15 21.99 L 34.00 21.99 L 32.90 23.25 L 32.58 23.25 L 32.43 23.09 L 32.43 23.72 L 31.96 24.19 L 31.80 24.19 L 31.64 24.50 L 31.33 24.66 L 30.86 24.66 L 30.86 25.13 L 30.54 25.44 L 30.54 25.60 L 30.39 25.76 L 30.07 25.76 L 29.76 26.39 L 29.44 26.54 L 29.13 27.01 L 28.50 27.17 L 28.35 27.64 L 27.87 28.11 L 27.56 28.11 L 27.40 28.27 L 27.25 28.90 L 26.62 29.21 L 26.62 29.37 L 26.30 29.68 L 25.99 29.68 L 25.83 29.84 L 25.83 30.15 L 25.52 30.31 L 25.52 30.47 L 25.21 30.62 L 25.05 30.94 L 24.58 31.41 L 24.42 31.41 L 24.42 31.57 L 24.11 31.72 L 23.95 32.04 L 23.64 32.19 L 23.17 32.82 L 23.01 32.82 L 22.54 33.29 L 22.38 33.29 L 22.38 33.61 L 21.75 34.23 L 21.60 34.23 L 21.44 34.55 L 21.13 34.70 L 20.65 34.70 L 20.81 34.86 L 20.81 35.18 L 20.18 35.65 L 20.03 35.65 L 19.71 36.27 L 19.40 36.43 L 19.40 36.59 L 19.08 36.74 L 18.93 37.06 L 18.61 37.22 L 18.14 37.22 L 18.14 37.69 L 17.67 38.16 L 17.52 38.16 L 17.36 38.47 L 15.95 39.88 L 15.79 39.88 L 15.79 40.04 L 15.47 40.20 L 15.47 40.35 L 15.16 40.67 L 15.00 40.67 L 15.00 40.83 L 14.38 41.45 L 14.22 41.45 L 13.59 42.24 Z"

# Symbol rightmost extent (blue vertical leg outer edge)
SYMBOL_RIGHT = 44.20
SYMBOL_HEIGHT = 48.00

# ── Lockup layout (optical spacing — tighter than equal bbox gap) ────────────
# Symbol's right edge is a solid stem; optical gap ≈ 0.16em of wordmark size
# so "Oplyra" reads as one word (was 5.75 mechanical; now optically balanced).
LOCKUP_GAP = 3.75
TEXT_X = SYMBOL_RIGHT + LOCKUP_GAP          # 47.95
TEXT_Y = 31.50                             # shared optical baseline (unchanged)
TEXT_SIZE = 24.0
TEXT_TRACKING = -0.04
TEXT_WIDTH = 50.0
LOCKUP_PAD_RIGHT = 2.0
LOCKUP_WIDTH = TEXT_X + TEXT_WIDTH + LOCKUP_PAD_RIGHT  # 99.95 → 100
LOCKUP_HEIGHT = 48.0


def ring_path() -> str:
    return RESTORED_NAVY


def blue_path() -> str:
    return RESTORED_BLUE


def paths() -> dict[str, str]:
    return {"navy": ring_path(), "blue": blue_path()}


GRADIENT = """
    <linearGradient id="oplyra-blue" x1="13.5" y1="47" x2="47" y2="17" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#2563EB"/>
      <stop offset="40%" stop-color="#3B82F6"/>
      <stop offset="100%" stop-color="#60A5FA"/>
    </linearGradient>"""

GRADIENT_INLINE = """
    <linearGradient id="oplyra-accent-gradient" x1="13.5" y1="47" x2="47" y2="17" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#2563EB"/>
      <stop offset="40%" stop-color="#3B82F6"/>
      <stop offset="100%" stop-color="#60A5FA"/>
    </linearGradient>"""


def lockup_inner_svg(use_current_color: bool = False) -> str:
    """Unified lockup markup — symbol + wordmark in one coordinate system."""
    p = paths()
    navy_fill = "currentColor" if use_current_color else "#0A1629"
    blue_fill = "url(#oplyra-accent-gradient)" if use_current_color else "url(#oplyra-blue)"
    text_fill = "currentColor" if use_current_color else "#0A1629"
    vb = f"0 0 {LOCKUP_WIDTH:.0f} {LOCKUP_HEIGHT:.0f}"
    return (
        f'<svg class="oplyra-logo__svg oplyra-logo__svg--lockup" viewBox="{vb}" fill="none" '
        f'xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">\n'
        f"  <g class=\"oplyra-logo__lockup\">\n"
        f'    <path fill="{navy_fill}" d="{p["navy"]}"/>\n'
        f'    <path fill="{blue_fill}" d="{p["blue"]}"/>\n'
        f'    <text class="oplyra-logo__wordmark" x="{TEXT_X:.2f}" y="{TEXT_Y:.2f}" '
        f'fill="{text_fill}" font-family="\'Inter\',\'Plus Jakarta Sans\',system-ui,sans-serif" '
        f'font-size="{TEXT_SIZE:.0f}" font-weight="600" letter-spacing="{TEXT_TRACKING}em">plyra</text>\n'
        f"  </g>\n"
        f"</svg>"
    )


def lockup_file_svg() -> str:
    p = paths()
    vb = f"0 0 {LOCKUP_WIDTH:.0f} {LOCKUP_HEIGHT:.0f}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" fill="none" role="img" aria-label="Oplyra">\n'
        f"  <defs>{GRADIENT}\n  </defs>\n"
        f"  <g>\n"
        f'    <path fill="#0A1629" d="{p["navy"]}"/>\n'
        f'    <path fill="url(#oplyra-blue)" d="{p["blue"]}"/>\n'
        f'    <text x="{TEXT_X:.2f}" y="{TEXT_Y:.2f}" fill="#0A1629" '
        f'font-family="\'Inter\',\'Plus Jakarta Sans\',system-ui,sans-serif" '
        f'font-size="{TEXT_SIZE:.0f}" font-weight="600" letter-spacing="{TEXT_TRACKING}em">plyra</text>\n'
        f"  </g>\n</svg>\n"
    )


def lockup_meta() -> dict:
    return {
        "width": LOCKUP_WIDTH,
        "height": LOCKUP_HEIGHT,
        "gap": LOCKUP_GAP,
        "text_x": TEXT_X,
        "text_y": TEXT_Y,
        "aspect_ratio": f"{LOCKUP_WIDTH:.0f} / {LOCKUP_HEIGHT:.0f}",
    }


def rasterize_pngs() -> None:
    import cv2
    from PIL import Image

    ref = OUT / "oplyra-symbol-reference.png"
    if not ref.exists():
        return
    img = cv2.imread(str(ref), cv2.IMREAD_UNCHANGED)
    gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    coords = cv2.findNonZero(th)
    x, y, w, h = cv2.boundingRect(coords)
    crop = img[y : y + h, x : x + w]
    if crop.shape[2] == 3:
        crop = cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
    pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGRA2RGBA))
    for size, name in [
        (32, "favicon-32x32.png"),
        (180, "apple-touch-icon.png"),
        (192, "pwa-192x192.png"),
        (512, "pwa-512x512.png"),
    ]:
        canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        scaled = pil.copy()
        scaled.thumbnail((size, size), Image.Resampling.LANCZOS)
        offset = ((size - scaled.width) // 2, (size - scaled.height) // 2)
        canvas.paste(scaled, offset, scaled)
        canvas.save(OUT / name, format="PNG")


def sync_logo_template() -> None:
    logo_html = ROOT / "app" / "templates" / "partials" / "_logo.html"
    text = logo_html.read_text(encoding="utf-8")
    p = paths()

    symbol_block = (
        "{% macro _oplyra_symbol_paths() %}\n"
        f'  <path fill="currentColor" d="{p["navy"]}"/>\n'
        f'  <path fill="url(#oplyra-accent-gradient)" d="{p["blue"]}"/>\n'
        "{% endmacro %}"
    )
    text = re.sub(
        r"\{% macro _oplyra_symbol_paths\(\) %\}.*?\{% endmacro %\}",
        symbol_block,
        text,
        count=1,
        flags=re.DOTALL,
    )

    lockup_block = (
        "{% macro _logo_svg_lockup() %}\n"
        "{# Unified lockup — symbol (O) + plyra, single coordinate system, no overlap #}\n"
        + lockup_inner_svg(use_current_color=True)
        + "\n{% endmacro %}"
    )
    text = re.sub(
        r"\{% macro _logo_svg_lockup\(\) %\}.*?\{% endmacro %\}",
        lockup_block,
        text,
        count=1,
        flags=re.DOTALL,
    )
    logo_html.write_text(text, encoding="utf-8")


def sync_css_aspect_ratio() -> None:
    css_path = ROOT / "app" / "static" / "css" / "oplyra-brand.css"
    css = css_path.read_text(encoding="utf-8")
    ratio = f"{LOCKUP_WIDTH:.0f} / {LOCKUP_HEIGHT:.0f}"
    css = re.sub(
        r"aspect-ratio:\s*[\d.]+\s*/\s*[\d.]+;",
        f"aspect-ratio: {ratio};",
        css,
        count=1,
    )
    css_path.write_text(css, encoding="utf-8")


def write_assets() -> None:
    p = paths()
    symbol = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" fill="none" role="img" aria-label="Oplyra">\n'
        f"  <defs>{GRADIENT}\n  </defs>\n"
        f'  <path fill="#0A1629" d="{p["navy"]}"/>\n'
        f'  <path fill="url(#oplyra-blue)" d="{p["blue"]}"/>\n'
        f"</svg>\n"
    )
    (OUT / "oplyra-symbol.svg").write_text(symbol, encoding="utf-8")
    (OUT / "oplyra-logo.svg").write_text(lockup_file_svg(), encoding="utf-8")
    (OUT / "oplyra-symbol-paths.json").write_text(
        json.dumps({**p, "lockup": lockup_meta()}, indent=2),
        encoding="utf-8",
    )
    sync_logo_template()
    sync_css_aspect_ratio()
    rasterize_pngs()
    meta = lockup_meta()
    print("Wrote production SVG + unified lockup")
    print(f"  lockup viewBox: 0 0 {meta['width']:.0f} {meta['height']:.0f}")
    print(f"  symbol-to-wordmark gap: {meta['gap']:.1f}u (~{meta['gap']:.0f}px at 48px height)")


if __name__ == "__main__":
    write_assets()
