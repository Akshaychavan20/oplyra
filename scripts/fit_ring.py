"""Fit navy ring gap angles and compare full symbol to reference."""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

REF = Path(
    r"C:\Users\Akshay\.cursor\projects\c-Users-Akshay-genny-ai\assets"
    r"\c__Users_Akshay_AppData_Roaming_Cursor_User_workspaceStorage_f7337cc95f5ba528b69c3b79148b1fa9"
    r"_images_Screenshot_2026-07-12_200141-983c3cfd-1692-484d-b17a-5a34acd23775.png"
)


def load():
    img = cv2.imread(str(REF))
    gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    x, y, w, h = cv2.boundingRect(cv2.findNonZero(th))
    crop = img[y : y + h, x : x + w]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    navy = cv2.inRange(hsv, (90, 80, 20), (130, 255, 80))
    blue = cv2.inRange(hsv, (90, 100, 80), (130, 255, 255))
    blue = cv2.bitwise_and(blue, cv2.bitwise_not(navy))
    return navy, blue, w, h


def vb(px, py, w, h, size=48.0):
    s = size / max(w, h)
    return (px - w / 2) * s + size / 2, (py - h / 2) * s + size / 2


def fit_circle_pts(pts):
    x, y = pts[:, 0], pts[:, 1]
    A = np.column_stack([x, y, np.ones(len(x))])
    b = x * x + y * y
    c, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = c[0] / 2, c[1] / 2
    r = math.sqrt(max(c[2] + cx * cx + cy * cy, 0))
    return cx, cy, r


def main():
    navy, blue, w, h = load()
    cnts, _ = cv2.findContours(navy, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnt = max(cnts, key=cv2.contourArea).reshape(-1, 2)
    pts = np.array([vb(p[0], p[1], w, h) for p in cnt])

    cx, cy, ro = fit_circle_pts(pts)

    # inner circle from points closest to center
    dists = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
    inner_band = pts[(dists > ro * 0.55) & (dists < ro * 0.72)]
    _, _, ri = fit_circle_pts(inner_band) if len(inner_band) > 20 else (cx, cy, ro * 0.625)

    angs = np.degrees(np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx)) % 360
    dists = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)

    # outer gap: angles where dist < ro*0.85
    outer_gap = sorted(set(int(a) for a, d in zip(angs, dists) if d < ro * 0.85))
    # find contiguous gap ranges
    gaps = []
    if outer_gap:
        start = outer_gap[0]
        prev = outer_gap[0]
        for a in outer_gap[1:] + [outer_gap[0] + 360]:
            if a - prev > 2:
                gaps.append((start, prev))
                start = a if a < 360 else outer_gap[0]
            prev = a if a < 360 else prev

    print(f"Center ({cx:.2f}, {cy:.2f})  RO={ro:.2f}  RI={ri:.2f}  thickness={ro-ri:.2f}")

    # Find outer arc endpoints (max dist points near gap boundaries)
    outer_arc = pts[dists > ro * 0.92]
    arc_angs = np.degrees(np.arctan2(outer_arc[:, 1] - cy, outer_arc[:, 0] - cx)) % 360

    # Gap on right: find min/max angles NOT covered by outer arc
    all_bins = np.zeros(360)
    for a in arc_angs:
        all_bins[int(a)] = 1
    # smooth
    missing = [i for i in range(360) if all_bins[i] == 0 and 30 < i < 120]
    if missing:
        print(f"Missing arc angles (gap sample): {missing[0]}-{missing[-1]}")

    # Explicit endpoint search: bottom gap start, top gap end
    for target_deg, label in [(60, "outer_start"), (320, "outer_end"), (65, "inner_start"), (315, "inner_end")]:
        idx = np.argmin(np.abs(arc_angs - target_deg))
        px, py = outer_arc[idx]
        print(f"{label}~{target_deg}: ({px:.2f},{py:.2f}) ang={arc_angs[idx]:.1f} dist={math.hypot(px-cx,py-cy):.2f}")

    # Compute exact gap termini by ray casting
    def polar_pt(r, deg):
        rad = math.radians(deg)
        return cx + r * math.cos(rad), cy + r * math.sin(rad)

    for deg in range(40, 130):
        x, y = polar_pt(ro, deg)
        ix = int((x - 0) * 480 / 48)  # not used
    # simpler: scan degrees for navy occupancy
    def navy_at(r, deg):
        x, y = polar_pt(r, deg)
        px = int((x - (24 - w * 48 / max(w, h) / 2)) * max(w, h) / 48)  # skip
        return False

    # Print polar at key angles for manual tuning
    print("\nPolar outer ring:")
    for deg in [55, 58, 60, 62, 315, 318, 320, 323, 325, 328]:
        x, y = polar_pt(ro, deg)
        print(f"  {deg:3d}° -> ({x:.2f}, {y:.2f})")
    print("\nPolar inner ring:")
    for deg in [62, 65, 318, 320, 323]:
        x, y = polar_pt(ri, deg)
        print(f"  {deg:3d}° -> ({x:.2f}, {y:.2f})")

    # Blue key measurements
    cnts, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    b = max(cnts, key=cv2.contourArea).reshape(-1, 2)
    bvb = np.array([vb(p[0], p[1], w, h) for p in b])
    print(f"\nBlue width outer={bvb[:,0].max():.2f} inner~{bvb[(bvb[:,0]>38)&(bvb[:,1]>40)][:,0].min():.2f}")
    print(f"Blue top y={bvb[:,1].min():.2f}  tip=({bvb[:,0].min():.2f},{bvb[bvb[:,0].argmin()][1]:.2f})")


if __name__ == "__main__":
    main()
