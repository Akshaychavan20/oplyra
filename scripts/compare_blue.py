"""Generate blue-only comparison images at 100/200/400/800% zoom."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from build_oplyra_symbol import blue_path
from tune_blue import render, ref_blue_mask

OUT = Path(__file__).resolve().parents[1] / "app" / "static" / "img" / "_compare"
OUT.mkdir(exist_ok=True)


def main() -> None:
    bp = blue_path()
    for zoom, label in [(1, "100"), (2, "200"), (4, "400"), (8, "800")]:
        size = 48 * zoom
        ref = ref_blue_mask(size)
        built = render(bp, size)
        combo = np.zeros((size, size * 2 + 16, 3), np.uint8)
        combo[:, :size, 1] = ref
        combo[:, size + 16 :, 2] = built
        Image.fromarray(combo).save(OUT / f"blue_{label}pct.png")
        mask = (ref > 0) | (built > 0)
        mse = float(np.mean((ref.astype(float) - built.astype(float))[mask] ** 2)) if mask.any() else 0
        print(f"{label}%  MSE={mse:.1f}")


if __name__ == "__main__":
    main()
