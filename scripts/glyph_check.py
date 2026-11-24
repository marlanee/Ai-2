"""Check that a restyled sign still has the same glyph strokes as the font-composited reference.

Both images are rectified to the sign quad, binarized (Otsu on luminance; text darker or lighter than the
face is detected automatically), and compared. A changed stroke (e.g. ㅜ -> ㅗ) shows up as a region where
one mask has ink and the other does not.

  python scripts/glyph_check.py ref.png cand1.png [cand2.png ...] --quad x y x y x y x y --rect W H [--save diff.png]

Score: IoU of the two ink masks after a 1px tolerance, plus the largest connected blob of disagreement
(as % of the glyph area). A stroke swap gives a large blob even when IoU is still high.
"""
import argparse
import numpy as np
from PIL import Image, ImageFilter


def coeffs(dst, src):
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def rgb(path, quad, rect, inset=0.08):
    w, h = rect
    im = Image.open(path).convert("RGB").transform((w, h), Image.PERSPECTIVE,
                                                   coeffs([(0, 0), (w, 0), (w, h), (0, h)], quad), Image.BICUBIC)
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(1))).astype(float)
    dx, dy = int(w * inset), int(h * inset)
    return a[dy:h - dy, dx:w - dx]


def otsu(a):
    hist, edges = np.histogram(a, 64)
    best, t = -1, a.mean()
    for i in range(1, 64):                                  # Otsu threshold
        w0, w1 = hist[:i].sum(), hist[i:].sum()
        if not w0 or not w1:
            continue
        m0 = (hist[:i] * edges[:i]).sum() / w0; m1 = (hist[i:] * edges[i:64]).sum() / w1
        v = w0 * w1 * (m0 - m1) ** 2
        if v > best:
            best, t = v, edges[i]
    return t


def ref_axis(a):
    """From the clean font reference: ink is the minority side of a luminance Otsu split.
    Returns (ink color, face color) so candidates are split along the ink->face color axis."""
    h, w, _ = a.shape
    r = max(2, int(min(h, w) * 0.06))
    ring = np.concatenate([a[:r].reshape(-1, 3), a[-r:].reshape(-1, 3), a[:, :r].reshape(-1, 3), a[:, -r:].reshape(-1, 3)])
    face = np.median(ring, 0)                                # glyphs rarely touch the sign edge
    dist = np.linalg.norm(a - face, axis=2)
    m = dist > otsu(dist)                                    # far from the face color = ink
    return a[m].mean(0), a[~m].mean(0)


def ink(a, axis):
    ink_c, face_c = axis
    d = face_c - ink_c
    p = ((a - ink_c) @ d) / (d @ d)                          # 0 = ink color, 1 = face color
    return p < otsu(p)


def blobs(mask):
    """Size of the largest 4-connected component (simple flood fill)."""
    seen = np.zeros_like(mask); best = 0
    H, W = mask.shape
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        stack, n = [(y0, x0)], 0; seen[y0, x0] = True
        while stack:
            y, x = stack.pop(); n += 1
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True; stack.append((yy, xx))
        best = max(best, n)
    return best


def dilate(m, r=1):
    return np.asarray(Image.fromarray(m.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(2 * r + 1))) > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref"); ap.add_argument("cands", nargs="+")
    ap.add_argument("--quad", type=float, nargs=8, required=True)
    ap.add_argument("--rect", type=int, nargs=2, required=True)
    ap.add_argument("--tol", type=int, default=2, help="pixel tolerance for stroke edges (in rect space)")
    ap.add_argument("--chars", type=int, default=1, help="number of syllables; blobs are scored per syllable")
    ap.add_argument("--max-blob", type=float, default=3.5, help="FAIL above this %% of one syllable's ink")
    ap.add_argument("--save-diff", action="store_true", help="write <cand>.diff.png (red=missing, blue=extra)")
    a = ap.parse_args()
    quad = list(zip(a.quad[0::2], a.quad[1::2]))
    ra = rgb(a.ref, quad, a.rect)
    axis = ref_axis(ra)
    ref = ink(ra, axis)
    for c in a.cands:
        m = ink(rgb(c, quad, a.rect), axis)
        inter = (ref & m).sum(); union = (ref | m).sum()
        miss = ref & ~dilate(m, a.tol)                      # strokes that disappeared
        extra = m & ~dilate(ref, a.tol)                     # strokes that appeared
        worst = max(blobs(miss), blobs(extra)) / max(1, ref.sum() / a.chars) * 100
        verdict = "PASS" if worst < a.max_blob else "FAIL"
        print(f"{verdict}  IoU {inter / max(1, union):.3f}  worst-blob {worst:5.2f}% of a syllable  {c}")
        if a.save_diff:
            v = np.zeros(ref.shape + (3,), np.uint8)
            v[ref & m] = 200; v[miss] = (255, 0, 0); v[extra] = (0, 120, 255)
            Image.fromarray(v).save(c.rsplit(".", 1)[0] + ".diff.png")


if __name__ == "__main__":
    main()
