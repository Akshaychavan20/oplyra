"""Extract ring/blue boundary from reference at shoulder intersection."""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

REF = Path(
    r"C:\Users\Akshay\.cursor\projects\c-Users-Akshay-genny-ai\assets"
    r"\c__Users_Akshay_AppData_Roaming_Cursor_User_workspaceStorage_f7337cc95f5ba528b69c3b79148b1fa9"
    r"_images_Screenshot_2026-07-12_200141-aeee1779-a7b1-418d-b0cc-6b8c3bbba119.png"
)


def vb(px, py, w, h, size=48.0):
    s = size / max(w, h)
    return (px - w / 2) * s + size / 2, (py - h / 2) * s + size / 2


def main() -> None:
    img = cv2.imread(str(REF))
    gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    x, y, w, h = cv2.boundingRect(cv2.findNonZero(th))
    crop = img[y : y + h, x : x + w]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    navy = cv2.inRange(hsv, (90, 80, 20), (130, 255, 80))
    blue = cv2.inRange(hsv, (90, 100, 80), (130, 255, 255))
    blue = cv2.bitwise_and(blue, cv2.bitwise_not(navy))

    cx, cy, ro = 22.20, 21.75, 20.30

    # Navy outer edge angles in shoulder zone (y 14-22)
    cnts, _ = cv2.findContours(navy, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnt = max(cnts, key=cv2.contourArea).reshape(-1, 2)
    pts = np.array([vb(p[0], p[1], w, h) for p in cnt])

    shoulder = pts[(pts[:, 1] > 14) & (pts[:, 1] < 22) & (pts[:, 0] > 30)]
    dists = np.hypot(shoulder[:, 0] - cx, shoulder[:, 1] - cy)
    angs = np.degrees(np.arctan2(shoulder[:, 1] - cy, shoulder[:, 0] - cx)) % 360

    # Navy terminus = max angle with high radius in gap zone
    hi = shoulder[dists > ro * 0.85]
    if len(hi):
        max_ang = hi[np.argmax(hi[:, 0])] if False else None
        for i in range(len(hi)):
            a = angs[dists > ro * 0.85][i] if False else 0
        mask = dists > ro * 0.85
        sa = angs[mask]
        sp = shoulder[mask]
        print("Navy shoulder outer points (r>0.85*RO):")
        for a, (px, py), d in sorted(zip(sa, sp, dists[mask]), key=lambda t: t[0])[-8:]:
            print(f"  ang={a:.1f}  ({px:.2f},{py:.2f})  r={d:.2f}")

    # Blue min angle near shoulder
    cnts, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    b = max(cnts, key=cv2.contourArea).reshape(-1, 2)
    bpts = np.array([vb(p[0], p[1], w, h) for p in b])
    bsh = bpts[(bpts[:, 1] > 14) & (bpts[:, 1] < 22) & (bpts[:, 0] > 34)]
    bd = np.hypot(bsh[:, 0] - cx, bsh[:, 1] - cy)
    ba = np.degrees(np.arctan2(bsh[:, 1] - cy, bsh[:, 0] - cx)) % 360
    print("\nBlue shoulder outer points:")
    for a, (px, py), d in sorted(zip(ba, bsh, bd), key=lambda t: t[0])[:8]:
        print(f"  ang={a:.1f}  ({px:.2f},{py:.2f})  r={d:.2f}")

    # Gap: find last navy angle before blue at similar y
    print(f"\nTarget: ring OE should be ~{sa.min():.1f} if navy ends before blue at {ba.min():.1f}" if len(sa) and len(ba) else "")


if __name__ == "__main__":
    main()
