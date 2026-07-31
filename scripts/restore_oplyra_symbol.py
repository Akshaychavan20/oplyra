"""
Restore Oplyra symbol — exact silhouette from official PNG.

Navy: perfect concentric ring (measured).
Blue: dense contour polyline from official mask, lightly simplified
      so it matches the approved PNG silhouette with no redesign.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "static" / "img"
COMPARE = OUT / "_compare"
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

CX, CY = 22.20, 21.75
RO = 20.30


def load():
    icon = np.array(Image.open(OUT / "oplyra-icon.png").convert("RGBA"))
    crop = icon[160:500, 180:490]
    rgb = crop[:, :, :3].astype(np.float32)
    a = crop[:, :, 3]
    lum = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    # Softer thresholds reclaim anti-aliased edge pixels without collapsing the gap
    blue = (a > 180) & (rgb[:, :, 2] > 100) & (rgb[:, :, 2] > rgb[:, :, 0] + 12)
    navy = (a > 180) & (lum < 110) & ~blue
    k = np.ones((3, 3), np.uint8)
    navy_u8 = cv2.morphologyEx((navy.astype(np.uint8) * 255), cv2.MORPH_CLOSE, k)
    blue_u8 = cv2.morphologyEx((blue.astype(np.uint8) * 255), cv2.MORPH_CLOSE, k)
    return crop, navy_u8, blue_u8


def fit_ring(navy_u8):
    ny, nx = np.where(navy_u8 > 0)
    cx0, cy0 = float(nx.mean()), float(ny.mean())
    outer, inner = [], []
    for ang in np.linspace(0, 2 * np.pi, 720, endpoint=False):
        rs = np.arange(20, 200, 0.25)
        xs = cx0 + rs * np.cos(ang)
        ys = cy0 + rs * np.sin(ang)
        xi = np.clip(xs.astype(int), 0, navy_u8.shape[1] - 1)
        yi = np.clip(ys.astype(int), 0, navy_u8.shape[0] - 1)
        on = navy_u8[yi, xi] > 0
        if on.sum() > 4:
            idx = np.where(on)[0]
            outer.append([float(xs[idx[-1]]), float(ys[idx[-1]])])
            inner.append([float(xs[idx[0]]), float(ys[idx[0]])])
    outer, inner = np.array(outer), np.array(inner)
    x, y = outer[:, 0], outer[:, 1]
    A = np.column_stack([2 * x, 2 * y, np.ones(len(x))])
    c, _, _, _ = np.linalg.lstsq(A, x * x + y * y, rcond=None)
    cx, cy = float(c[0]), float(c[1])
    ro = float(np.mean(np.sqrt((outer[:, 0] - cx) ** 2 + (outer[:, 1] - cy) ** 2)))
    ri = float(np.mean(np.sqrt((inner[:, 0] - cx) ** 2 + (inner[:, 1] - cy) ** 2)))
    is_gap = np.zeros(360, dtype=bool)
    for deg in range(360):
        ang = np.radians(deg)
        rs = np.arange(ri - 2, ro + 2, 0.5)
        xs = cx + rs * np.cos(ang)
        ys = cy + rs * np.sin(ang)
        xi = np.clip(xs.astype(int), 0, navy_u8.shape[1] - 1)
        yi = np.clip(ys.astype(int), 0, navy_u8.shape[0] - 1)
        if (navy_u8[yi, xi] > 0).sum() < 2:
            is_gap[deg] = True
    changes = np.where(is_gap != np.roll(is_gap, 1))[0]
    return cx, cy, ro, ri, float(changes[0]), float(changes[1])


def polar(r, deg):
    rad = math.radians(deg)
    return CX + r * math.cos(rad), CY + r * math.sin(rad)


def contour_points(mask_u8, scale, ox, oy, epsilon_px: float) -> list[tuple[float, float]]:
    cnts, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnt = max(cnts, key=cv2.contourArea)
    approx = cv2.approxPolyDP(cnt, epsilon_px, True).reshape(-1, 2).astype(float)
    return [(float(p[0]) * scale + ox, float(p[1]) * scale + oy) for p in approx]


def navy_contour_path(navy_u8, scale, ox, oy, epsilon_px: float = 0.45) -> str:
    pts = contour_points(navy_u8, scale, ox, oy, epsilon_px)
    i0 = int(np.argmin([p[1] for p in pts]))
    pts = pts[i0:] + pts[:i0]
    parts = [f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"]
    for x, y in pts[1:]:
        parts.append(f"L {x:.2f} {y:.2f}")
    parts.append("Z")
    return " ".join(parts)


def blue_contour_path(blue_u8, scale, ox, oy, epsilon_px: float = 1.25) -> str:
    pts = contour_points(blue_u8, scale, ox, oy, epsilon_px)
    i0 = int(np.argmin([p[0] for p in pts]))
    pts = pts[i0:] + pts[:i0]
    parts = [f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"]
    for x, y in pts[1:]:
        parts.append(f"L {x:.2f} {y:.2f}")
    parts.append("Z")
    return " ".join(parts)


GRADIENT = """
    <linearGradient id="oplyra-blue" x1="16" y1="42" x2="42" y2="16" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#0037D8"/>
      <stop offset="30%" stop-color="#0066FF"/>
      <stop offset="65%" stop-color="#1A8CFF"/>
      <stop offset="100%" stop-color="#3DA2FF"/>
    </linearGradient>"""


def write_assets(navy, blue):
    from build_oplyra_symbol import (
        LOCKUP_GAP,
        LOCKUP_PAD_RIGHT,
        TEXT_SIZE,
        TEXT_TRACKING,
        TEXT_WIDTH,
        TEXT_Y,
    )

    (OUT / "oplyra-symbol.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" fill="none" role="img" aria-label="Oplyra">\n'
        f"  <defs>{GRADIENT}\n  </defs>\n"
        f'  <path fill="#061630" d="{navy}"/>\n'
        f'  <path fill="url(#oplyra-blue)" d="{blue}"/>\n'
        f"</svg>\n",
        encoding="utf-8",
    )
    xs = [float(m.group(1)) for m in re.finditer(r"[ML]\s*([-\d.]+)", blue)]
    sym_right = max(xs) if xs else 47.0
    text_x = sym_right + LOCKUP_GAP
    lockup_w = text_x + TEXT_WIDTH + LOCKUP_PAD_RIGHT
    print(f"pts navy={navy.count(' L ')+1} blue={blue.count(' L ')+1} sym_right={sym_right:.2f}")

    (OUT / "oplyra-logo.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {lockup_w:.0f} 48" fill="none" role="img" aria-label="Oplyra">\n'
        f"  <defs>{GRADIENT}\n  </defs>\n"
        f"  <g>\n"
        f'    <path fill="#061630" d="{navy}"/>\n'
        f'    <path fill="url(#oplyra-blue)" d="{blue}"/>\n'
        f'    <text x="{text_x:.2f}" y="{TEXT_Y:.2f}" fill="#061630" '
        f"font-family=\"'Inter','Plus Jakarta Sans',system-ui,sans-serif\" "
        f'font-size="{TEXT_SIZE:.0f}" font-weight="600" letter-spacing="{TEXT_TRACKING}em">plyra</text>\n'
        f"  </g>\n</svg>\n",
        encoding="utf-8",
    )
    (OUT / "oplyra-symbol-paths.json").write_text(
        json.dumps({"navy": navy, "blue": blue, "lockup": {"width": lockup_w, "text_x": text_x}}, indent=2),
        encoding="utf-8",
    )

    logo_html = ROOT / "app" / "templates" / "partials" / "_logo.html"
    text = logo_html.read_text(encoding="utf-8")
    text = re.sub(
        r"\{% macro _oplyra_symbol_paths\(\) %\}.*?\{% endmacro %\}",
        "{% macro _oplyra_symbol_paths() %}\n"
        f'  <path fill="currentColor" d="{navy}"/>\n'
        f'  <path fill="url(#oplyra-accent-gradient)" d="{blue}"/>\n'
        "{% endmacro %}",
        text,
        count=1,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"\{% macro _logo_svg_lockup\(\) %\}.*?\{% endmacro %\}",
        "{% macro _logo_svg_lockup() %}\n"
        "{# Unified lockup — symbol (O) + plyra #}\n"
        f'<svg class="oplyra-logo__svg oplyra-logo__svg--lockup" viewBox="0 0 {lockup_w:.0f} 48" fill="none" '
        f'xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">\n'
        f'  <g class="oplyra-logo__lockup">\n'
        f'    <path fill="currentColor" d="{navy}"/>\n'
        f'    <path fill="url(#oplyra-accent-gradient)" d="{blue}"/>\n'
        f'    <text class="oplyra-logo__wordmark" x="{text_x:.2f}" y="{TEXT_Y:.2f}" '
        f'fill="currentColor" font-family="\'Inter\',\'Plus Jakarta Sans\',system-ui,sans-serif" '
        f'font-size="{TEXT_SIZE:.0f}" font-weight="600" letter-spacing="{TEXT_TRACKING}em">plyra</text>\n'
        f"  </g>\n</svg>\n"
        "{% endmacro %}",
        text,
        count=1,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"<linearGradient id=\"oplyra-accent-gradient\"[^>]*>.*?</linearGradient>",
        '<linearGradient id="oplyra-accent-gradient" x1="16" y1="42" x2="42" y2="16" gradientUnits="userSpaceOnUse">\n'
        '      <stop offset="0%" stop-color="#0037D8"/>\n'
        '      <stop offset="30%" stop-color="#0066FF"/>\n'
        '      <stop offset="65%" stop-color="#1A8CFF"/>\n'
        '      <stop offset="100%" stop-color="#3DA2FF"/>\n'
        "    </linearGradient>",
        text,
        count=1,
        flags=re.DOTALL,
    )
    logo_html.write_text(text, encoding="utf-8")

    builder = SCRIPTS / "build_oplyra_symbol.py"
    btext = builder.read_text(encoding="utf-8")
    btext = re.sub(r'RESTORED_NAVY = ".*?"', f'RESTORED_NAVY = "{navy}"', btext, count=1)
    btext = re.sub(r'RESTORED_BLUE = ".*?"', f'RESTORED_BLUE = "{blue}"', btext, count=1)
    btext = re.sub(r"SYMBOL_RIGHT = [\d.]+", f"SYMBOL_RIGHT = {sym_right:.2f}", btext, count=1)
    builder.write_text(btext, encoding="utf-8")
    print(f"points~{blue.count('L')+1} sym_right={sym_right:.2f}")


def main():
    COMPARE.mkdir(parents=True, exist_ok=True)
    crop, navy_u8, blue_u8 = load()
    cx, cy, ro, ri, bottom, top = fit_ring(navy_u8)
    scale = RO / ro
    ox, oy = CX - cx * scale, CY - cy * scale
    ri_vb = ri * scale

    # Perfect circle for clean geometry, but scale/offset from fit so blue aligns.
    # Use mathematical ring — more "pixel perfect" than noisy contour for navy.
    # If gap issues persist vs PNG, prefer navy contour for exact match:
    use_navy_contour = True
    if use_navy_contour:
        navy = navy_contour_path(navy_u8, scale, ox, oy, epsilon_px=0.55)
    else:
        navy = (
            f"M {polar(RO, bottom)[0]:.2f} {polar(RO, bottom)[1]:.2f}"
            f" A {RO:.2f} {RO:.2f} 0 1 1 {polar(RO, top)[0]:.2f} {polar(RO, top)[1]:.2f}"
            f" L {polar(ri_vb, top)[0]:.2f} {polar(ri_vb, top)[1]:.2f}"
            f" A {ri_vb:.2f} {ri_vb:.2f} 0 1 0 {polar(ri_vb, bottom)[0]:.2f} {polar(ri_vb, bottom)[1]:.2f}"
            f" Z"
        )
    blue = blue_contour_path(blue_u8, scale, ox, oy, epsilon_px=0.5)
    print(f"RI={ri_vb:.2f} terminals {bottom:.0f}->{top:.0f}")
    print("navy pts~", navy.count(" L ") + 1)
    print("blue pts~", blue.count(" L ") + 1)
    write_assets(navy, blue)

    import base64

    svg = (OUT / "oplyra-symbol.svg").read_text(encoding="utf-8")
    svg2 = svg.replace('viewBox="0 0 48 48"', 'viewBox="0 0 48 48" width="360" height="360"')
    b64 = base64.b64encode((COMPARE / "symbol-from-icon.png").read_bytes()).decode()
    (COMPARE / "preview.html").write_text(
        f"""<!DOCTYPE html><html><body style="margin:0;background:#fff;display:flex;gap:32px;padding:32px;font-family:system-ui">
<div><div style="font-size:13px;margin-bottom:10px">Restored SVG</div>{svg2}</div>
<div><div style="font-size:13px;margin-bottom:10px">Official PNG</div>
<img src="data:image/png;base64,{b64}" width="360" height="360" style="object-fit:contain;border:1px solid #eee"/></div>
</body></html>""",
        encoding="utf-8",
    )
    print("done")


if __name__ == "__main__":
    main()
