"""Fine grid search for blue path."""
from __future__ import annotations

import numpy as np
from tune_blue import score, ref_blue_mask


def build(**k: float) -> str:
    return (
        f"M {k['tx']:.2f} {k['ty']:.2f}"
        f" C {k['d1x']:.2f} {k['d1y']:.2f} {k['d2x']:.2f} {k['d2y']:.2f} {k['sx']:.2f} {k['sy']:.2f}"
        f" C {k['s1x']:.2f} {k['s1y']:.2f} {k['s2x']:.2f} {k['s2y']:.2f} 46.00 17.85"
        f" L 46.00 44.35"
        f" C 46.00 46.10 44.15 46.50 42.05 46.50"
        f" C 39.95 46.50 38.40 45.75 38.40 44.35"
        f" L 38.40 {k['iy']:.2f}"
        f" C 38.40 {k['i1y']:.2f} {k['i2x']:.2f} {k['i2y']:.2f} {k['i3x']:.2f} {k['i3y']:.2f}"
        f" C {k['c1x']:.2f} {k['c1y']:.2f} {k['c2x']:.2f} {k['c2y']:.2f} {k['tx']:.2f} {k['ty']:.2f}"
        f" Z"
    )


def main() -> None:
    ref = ref_blue_mask(480)
    best = (99999.0, "")
    base = dict(
        d1x=17.5,
        d1y=43.0,
        sx=41.0,
        sy=18.05,
        s1x=43.5,
        s1y=17.85,
        s2x=45.05,
        s2y=17.85,
        iy=33.6,
        i2x=33.5,
        i2y=38.0,
        i3y=41.5,
        c1x=20.5,
        c1y=46.2,
        c2x=16.0,
        c2y=47.05,
    )
    for tx in np.arange(12.5, 13.2, 0.05):
        for ty in np.arange(46.3, 46.9, 0.05):
            for d2x in np.arange(29.0, 32.0, 0.5):
                for d2y in np.arange(23.5, 26.5, 0.5):
                    for i1y in np.arange(29.0, 31.5, 0.25):
                        for i3x in np.arange(24.5, 27.5, 0.5):
                            d = build(tx=tx, ty=ty, d2x=d2x, d2y=d2y, i1y=i1y, i3x=i3x, **base)
                            s = score(d, ref)
                            if s < best[0]:
                                best = (s, d)
    print(f"MSE {best[0]:.1f}")
    print(best[1])


if __name__ == "__main__":
    main()
