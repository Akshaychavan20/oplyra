"""Calibrate Oplyra symbol geometry from official reference PNG."""
from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REF = Path(
    r"C:\Users\Akshay\.cursor\projects\c-Users-Akshay-genny-ai\assets"
    r"\c__Users_Akshay_AppData_Roaming_Cursor_User_workspaceStorage_f7337cc95f5ba528b69c3b79148b1fa9"
    r"_images_Screenshot_2026-07-12_200141-983c3cfd-1692-484d-b17a-5a34acd23775.png"
)
OUT = ROOT / "app" / "static" / "img"


def load_masks():
    img = cv2.imread(str(REF))
    gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    x, y, w, h = cv2.boundingRect(cv2.findNonZero(th))
    crop = img[y : y + h, x : x + w]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    navy = cv2.inRange(hsv, (90, 80, 20), (130, 255, 80))
    blue = cv2.inRange(hsv, (90, 100, 80), (130, 255, 255))
    blue = cv2.bitwise_and(blue, cv2.bitwise_not(navy))
    return crop, navy, blue, w, h


def to_vb(pts: np.ndarray, w: int, h: int, size: float = 48.0) -> np.ndarray:
    scale = size / max(w, h)
    out = pts.astype(float).copy()
    out[:, 0] = (out[:, 0] - w / 2) * scale + size / 2
    out[:, 1] = (out[:, 1] - h / 2) * scale + size / 2
    return out


def fit_circle(points: np.ndarray) -> tuple[float, float, float]:
    x, y = points[:, 0], points[:, 1]
    A = np.column_stack([x, y, np.ones(len(x))])
    b = x * x + y * y
    c, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = c[0] / 2, c[1] / 2
    r = math.sqrt(c[2] + cx * cx + cy * cy)
    return cx, cy, r


def contour_points(mask: np.ndarray, w: int, h: int, eps: float = 0.8) -> np.ndarray:
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnt = max(cnts, key=cv2.contourArea)
    approx = cv2.approxPolyDP(cnt, eps, True).reshape(-1, 2)
    return to_vb(approx, w, h)


def angle(cx: float, cy: float, px: float, py: float) -> float:
    return math.degrees(math.atan2(py - cy, px - cx)) % 360


def main() -> None:
    crop, navy, blue, w, h = load_masks()
    scale = 48.0 / max(w, h)

    # Fit outer circle from navy mask outer edge points
    cnts, _ = cv2.findContours(navy, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    navy_cnt = max(cnts, key=cv2.contourArea).reshape(-1, 2)
    navy_vb = to_vb(navy_cnt, w, h)
    cx, cy, ro = fit_circle(navy_vb)

    # Inner circle from navy inner hole - use eroded boundary
    cnts, _ = cv2.findContours(navy, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    # approximate inner from ring thickness
    ri_est = ro * 0.625  # initial guess

    navy_pts = contour_points(navy, w, h, 0.6)
    blue_pts = contour_points(blue, w, h, 0.6)

    # Gap endpoints on navy outer arc
    # Find navy outer points in right gap (angles ~300-60)
    outer_pts = []
    for px, py in navy_vb[::4]:
        a = angle(cx, cy, px, py)
        dist = math.hypot(px - cx, py - cy)
        if 55 < a < 330 and dist > ro * 0.9:
            outer_pts.append((px, py, a, dist))
    outer_pts.sort(key=lambda t: t[2])

    print(f"Navy fit: CX={cx:.3f} CY={cy:.3f} RO={ro:.3f} RI~={ri_est:.3f}")
    print(f"Scale factor: {scale:.4f}")
    print("\nNavy simplified ({})".format(len(navy_pts)))
    for p in navy_pts:
        print(f"  ({p[0]:.2f}, {p[1]:.2f})")
    print("\nBlue simplified ({})".format(len(blue_pts)))
    for p in blue_pts:
        print(f"  ({p[0]:.2f}, {p[1]:.2f})")

    # Extrema blue
    print("\nBlue extrema:")
    print("  left", blue_pts[blue_pts[:, 0].argmin()])
    print("  right", blue_pts[blue_pts[:, 0].argmax()])
    print("  top", blue_pts[blue_pts[:, 1].argmin()])
    print("  bottom", blue_pts[blue_pts[:, 1].argmax()])

    # Save reference copy
    ref_out = OUT / "oplyra-symbol-reference.png"
    cv2.imwrite(str(ref_out), crop)


if __name__ == "__main__":
    main()
