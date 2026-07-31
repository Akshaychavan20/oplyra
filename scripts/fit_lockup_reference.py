"""Fit Oplyra symbol + lockup spacing against official lockup reference PNG."""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "app" / "static" / "img" / "oplyra-lockup-reference.png"
OUT = ROOT / "app" / "static" / "img" / "_compare"


def load_reference_masks(size: int = 480) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """Return (symbol_mask, text_mask, full_mask, meta) scaled to `size`."""
    img = cv2.imread(str(REF))
    if img is None:
        raise FileNotFoundError(REF)

    # Trim UI selection border (~4px)
    crop = img[4 : img.shape[0] - 4, 4 : img.shape[1] - 4]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    blue = cv2.inRange(hsv, (105, 180, 180), (115, 255, 255))
    white = cv2.inRange(hsv, (0, 0, 180), (180, 80, 255))

    bp = cv2.findNonZero(blue)
    if bp is None:
        raise RuntimeError("Could not detect blue growth element")
    bx0, by0, bw, bh = cv2.boundingRect(bp)
    sym_right = bx0 + bw

    white_sym = white.copy()
    white_sym[:, sym_right + 2 :] = 0
    sym_mask = cv2.bitwise_or(white_sym, blue)

    # Symbol bounding box with padding
    sp = cv2.findNonZero(sym_mask)
    sx0, sy0, sw, sh = cv2.boundingRect(sp)
    pad = 2
    sx0 = max(0, sx0 - pad)
    sy0 = max(0, sy0 - pad)
    sw = min(crop.shape[1] - sx0, sw + 2 * pad)
    sh = min(crop.shape[0] - sy0, sh + 2 * pad)
    sym_crop = sym_mask[sy0 : sy0 + sh, sx0 : sx0 + sw]

    # Scale symbol to fill 48×48
    scale = 48.0 / max(sw, sh)
    cw, ch = int(sw * scale), int(sh * scale)
    sym48 = cv2.resize(sym_crop, (cw, ch), interpolation=cv2.INTER_NEAREST)
    canvas = np.zeros((48, 48), np.uint8)
    ox = (48 - cw) // 2
    oy = (48 - ch) // 2
    canvas[oy : oy + ch, ox : ox + cw] = sym48

    # Text start in crop coords
    white_text = white.copy()
    white_text[:, : sym_right + 1] = 0
    text_cols = np.where(np.mean(white_text > 0, axis=0) > 0.15)[0]
    text_start = int(text_cols[0]) if len(text_cols) else sym_right + 4

    sym_right_vb = ox + int((sym_right - sx0) * scale)
    gap_vb = (text_start - sym_right) * scale

    ref480 = cv2.resize(canvas, (size, size), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(str(OUT / "ref-symbol-mask-48.png"), canvas)

    meta = {
        "sym_right_vb": sym_right_vb,
        "gap_vb": gap_vb,
        "text_start_crop": text_start,
        "sym_right_crop": sym_right,
        "scale": scale,
        "offset": (ox, oy),
    }
    return canvas, white_text, ref480, meta


def polar(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    rad = math.radians(deg)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def ring_path(cx: float, cy: float, ro: float, ri: float, os_: float, oe: float, is_: float, ie: float) -> str:
    ox0, oy0 = polar(cx, cy, ro, os_)
    ox1, oy1 = polar(cx, cy, ro, oe)
    ix1, iy1 = polar(cx, cy, ri, ie)
    ix0, iy0 = polar(cx, cy, ri, is_)
    return (
        f"M {ox0:.2f} {oy0:.2f}"
        f" A {ro:.2f} {ro:.2f} 0 1 1 {ox1:.2f} {oy1:.2f}"
        f" L {ix1:.2f} {iy1:.2f}"
        f" A {ri:.2f} {ri:.2f} 0 1 0 {ix0:.2f} {iy0:.2f}"
        f" L {ox0:.2f} {oy0:.2f} Z"
    )


def parse_path(d: str) -> list[tuple[float, float]]:
    tokens = re.sub(r"([MLCZ])", r" \1 ", d).split()
    pts: list[tuple[float, float]] = []
    i = 0
    while i < len(tokens):
        cmd = tokens[i]
        i += 1
        if cmd == "M":
            pts.append((float(tokens[i]), float(tokens[i + 1])))
            i += 2
        elif cmd == "L":
            pts.append((float(tokens[i]), float(tokens[i + 1])))
            i += 2
        elif cmd == "C":
            x1, y1 = float(tokens[i]), float(tokens[i + 1])
            x2, y2 = float(tokens[i + 2]), float(tokens[i + 3])
            cx, cy = float(tokens[i + 4]), float(tokens[i + 5])
            for t in np.linspace(0, 1, 24)[1:]:
                t1 = 1 - t
                p = pts[-1]
                pts.append(
                    (
                        t1**3 * p[0] + 3 * t1**2 * t * x1 + 3 * t1 * t**2 * x2 + t**3 * cx,
                        t1**3 * p[1] + 3 * t1**2 * t * y1 + 3 * t1 * t**2 * y2 + t**3 * cy,
                    )
                )
            i += 6
    return pts


def render_paths(paths: list[str], size: int = 480) -> np.ndarray:
    sc = size / 48.0
    canvas = np.zeros((size, size), np.uint8)
    for d in paths:
        poly = np.array([[int(x * sc), int(y * sc)] for x, y in parse_path(d)], np.int32)
        if len(poly) >= 3:
            cv2.fillPoly(canvas, [poly], 255)
    return canvas


def align_mse(ref: np.ndarray, built: np.ndarray) -> float:
    def centroid(m: np.ndarray) -> tuple[float, float]:
        m_ = cv2.moments(m)
        if not m_["m00"]:
            return m.shape[1] / 2, m.shape[0] / 2
        return m_["m10"] / m_["m00"], m_["m01"] / m_["m00"]

    rcx, rcy = centroid(ref)
    bcx, bcy = centroid(built)
    m = np.float32([[1, 0, rcx - bcx], [0, 1, rcy - bcy]])
    built = cv2.warpAffine(built, m, (built.shape[1], built.shape[0]))
    mask = (ref > 0) | (built > 0)
    if not mask.any():
        return 9999.0
    return float(np.mean((ref.astype(float) - built.astype(float))[mask] ** 2))


def blue_path(**k: float) -> str:
    return (
        f"M {k['tx']:.2f} {k['ty']:.2f}"
        f" C {k['d1x']:.2f} {k['d1y']:.2f} {k['d2x']:.2f} {k['d2y']:.2f} {k['sx']:.2f} {k['sy']:.2f}"
        f" C {k['s1x']:.2f} {k['s1y']:.2f} {k['s2x']:.2f} {k['s2y']:.2f} {k['top_x']:.2f} {k['top_y']:.2f}"
        f" L {k['leg_x']:.2f} {k['leg_bot']:.2f}"
        f" C {k['leg_x']:.2f} {k['leg_c1']:.2f} {k['leg_c2x']:.2f} {k['leg_c2y']:.2f} {k['leg_c3x']:.2f} {k['leg_c3y']:.2f}"
        f" C {k['leg_c4x']:.2f} {k['leg_c4y']:.2f} {k['leg_c5x']:.2f} {k['leg_c5y']:.2f} {k['leg_x']:.2f} {k['leg_mid']:.2f}"
        f" L {k['leg_x']:.2f} {k['in_y']:.2f}"
        f" C {k['leg_x']:.2f} {k['i1y']:.2f} {k['i2x']:.2f} {k['i2y']:.2f} {k['i3x']:.2f} {k['i3y']:.2f}"
        f" C {k['c1x']:.2f} {k['c1y']:.2f} {k['c2x']:.2f} {k['c2y']:.2f} {k['tx']:.2f} {k['ty']:.2f}"
        f" Z"
    )


def score_combo(ref: np.ndarray, cx: float, cy: float, ro: float, ri: float, oe: float, bp: str) -> float:
    navy = ring_path(cx, cy, ro, ri, 58, oe, 62, 323.5)
    return align_mse(ref, render_paths([navy, bp]))


def optimize_ring(ref: np.ndarray, bp: str) -> tuple[float, float, float, float, float]:
    best = (1e9, 22.2, 21.75, 20.3, 12.68, 331.0)
    for cx in np.arange(21.0, 23.5, 0.1):
        for cy in np.arange(20.5, 23.0, 0.1):
            for ro in np.arange(19.0, 21.0, 0.1):
                ri = ro * 0.624
                for oe in np.arange(326, 334, 1):
                    s = score_combo(ref, cx, cy, ro, ri, oe, bp)
                    if s < best[0]:
                        best = (s, cx, cy, ro, ri, float(oe))
    return best[1:]


def optimize_blue(ref: np.ndarray, cx: float, cy: float, ro: float, ri: float, oe: float) -> tuple[str, float]:
    navy = ring_path(cx, cy, ro, ri, 58, oe, 62, 323.5)
    best = (1e9, "")
    base = dict(
        d1x=18.0,
        d1y=43.0,
        s1x=43.6,
        s1y=17.75,
        s2x=45.3,
        s2y=17.15,
        top_x=47.47,
        top_y=18.64,
        leg_x=47.47,
        leg_bot=44.40,
        leg_c1=46.15,
        leg_c2x=45.62,
        leg_c2y=46.55,
        leg_c3x=43.52,
        leg_c3y=46.55,
        leg_c4x=41.42,
        leg_c4y=46.55,
        leg_c5x=39.38,
        leg_c5y=45.80,
        leg_mid=44.40,
        i1y=30.15,
        i2x=34.60,
        i2y=36.80,
        i3y=40.80,
        c1x=20.50,
        c1y=46.20,
        c2x=16.0,
        c2y=47.05,
    )
    for tx in np.arange(12.8, 14.2, 0.1):
        for ty in np.arange(46.2, 47.0, 0.1):
            for d2x in np.arange(28.0, 32.0, 0.5):
                for d2y in np.arange(25.0, 28.5, 0.5):
                    for sx in np.arange(40.5, 42.5, 0.25):
                        for sy in np.arange(17.5, 19.0, 0.25):
                            for in_y in np.arange(31.0, 33.5, 0.25):
                                for i3x in np.arange(26.0, 30.0, 0.5):
                                    d = blue_path(
                                        tx=tx,
                                        ty=ty,
                                        d2x=d2x,
                                        d2y=d2y,
                                        sx=sx,
                                        sy=sy,
                                        in_y=in_y,
                                        i3x=i3x,
                                        **base,
                                    )
                                    s = align_mse(ref, render_paths([navy, d]))
                                    if s < best[0]:
                                        best = (s, d)
    return best[1], best[0]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _, _, ref480, meta = load_reference_masks(480)
    print("Reference meta:", meta)

    # Start from current production blue path
    bp0 = (
        "M 13.89 46.59 C 18.40 42.80 29.80 27.20 42.02 18.81"
        " C 43.60 17.75 45.30 17.15 46.95 17.93"
        " C 47.15 18.15 47.30 18.45 47.47 18.64"
        " L 47.47 44.40"
        " C 47.47 46.15 45.62 46.55 43.52 46.55"
        " C 41.42 46.55 39.38 45.80 39.38 44.40"
        " L 39.38 32.35"
        " C 39.38 30.15 34.60 36.80 28.66 40.80"
        " C 24.97 43.20 20.50 46.00 19.87 47.30"
        " C 17.80 47.15 15.60 46.80 13.89 46.59 Z"
    )
    cx, cy, ro, ri, oe = optimize_ring(ref480, bp0)
    print(f"Ring: cx={cx:.2f} cy={cy:.2f} ro={ro:.2f} ri={ri:.2f} oe={oe:.1f}")
    navy = ring_path(cx, cy, ro, ri, 58, oe, 62, 323.5)
    print("Navy:", navy)

    bp, mse = optimize_blue(ref480, cx, cy, ro, ri, oe)
    print(f"Blue MSE={mse:.1f}")
    print("Blue:", bp)

    built = render_paths([navy, bp])
    combo = np.zeros((480, 980, 3), np.uint8)
    combo[:, :480, 1] = ref480
    combo[:, 500:, 2] = built
    cv2.imwrite(str(OUT / "fit-result.png"), combo)

    sym_right = float(parse_path(bp)[-1][0]) if bp else 47.47
    for pt in parse_path(bp):
        sym_right = max(sym_right, pt[0])
    for pt in parse_path(navy):
        sym_right = max(sym_right, pt[0])

    gap = max(meta["gap_vb"], 5.5)
    text_x = sym_right + gap
    print(f"Lockup: sym_right={sym_right:.2f} gap={gap:.2f} text_x={text_x:.2f}")


if __name__ == "__main__":
    main()
