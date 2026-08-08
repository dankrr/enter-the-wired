"""Optional GIF recoloring support.

This module is intentionally isolated from the core UI so NumPy and Pillow are
only required when accent-color GIF processing is actually enabled.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def _rgb_to_hsv(r, g, b):
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx = max(r, g, b)
    mn = min(r, g, b)
    df = mx - mn

    if mx == mn:
        h = 0.0
    elif mx == r:
        h = (60 * ((g - b) / df) + 360) % 360
    elif mx == g:
        h = (60 * ((b - r) / df) + 120) % 360
    else:
        h = (60 * ((r - g) / df) + 240) % 360

    s = 0.0 if mx == 0 else df / mx
    return h, s, mx


def _rgb_to_hsv_batch(rgb_array):
    r, g, b = rgb_array[..., 0], rgb_array[..., 1], rgb_array[..., 2]
    r, g, b = r / 255.0, g / 255.0, b / 255.0

    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    df = mx - mn

    h = np.zeros_like(mx)
    s = np.zeros_like(mx)
    v = mx
    nonzero = df != 0

    mask_r = (mx == r) & nonzero
    mask_g = (mx == g) & nonzero
    mask_b = (mx == b) & nonzero

    h[mask_r] = (60 * ((g[mask_r] - b[mask_r]) / df[mask_r]) + 360) % 360
    h[mask_g] = (60 * ((b[mask_g] - r[mask_g]) / df[mask_g]) + 120) % 360
    h[mask_b] = (60 * ((r[mask_b] - g[mask_b]) / df[mask_b]) + 240) % 360
    s[mx != 0] = df[mx != 0] / mx[mx != 0]

    return np.stack([h, s, v], axis=-1)


def _hsv_to_rgb_batch(h, s, v):
    h = h % 360
    hi = (h / 60).astype(int) % 6
    f = (h / 60) - (h / 60).astype(int)

    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)

    r = np.zeros_like(h)
    g = np.zeros_like(h)
    b = np.zeros_like(h)
    conditions = [
        (v, t, p),
        (q, v, p),
        (p, v, t),
        (p, q, v),
        (t, p, v),
        (v, p, q),
    ]

    for i, (rr, gg, bb) in enumerate(conditions):
        mask = hi == i
        r[mask] = rr[mask]
        g[mask] = gg[mask]
        b[mask] = bb[mask]

    return np.clip(np.stack([r * 255, g * 255, b * 255], axis=-1), 0, 255)


def _apply_color_transform(img_array, target_h, target_s, target_v):
    r, g, b, a = (
        img_array[..., 0],
        img_array[..., 1],
        img_array[..., 2],
        img_array[..., 3],
    )

    rgb_mean = (r + g + b) / 3.0
    rgb_std = np.sqrt(
        ((r - rgb_mean) ** 2 + (g - rgb_mean) ** 2 + (b - rgb_mean) ** 2) / 3.0
    )
    colored_mask = (a > 10) & (rgb_std > 5)
    if not np.any(colored_mask):
        return img_array

    colored_hsv = _rgb_to_hsv_batch(img_array[colored_mask][:, :3])
    avg_s = max(float(np.mean(colored_hsv[:, 1])), 0.001)
    avg_v = max(float(np.mean(colored_hsv[:, 2])), 0.001)

    new_h = np.full(colored_hsv.shape[0], target_h)
    new_s = np.clip(colored_hsv[:, 1] * (target_s / avg_s), 0.0, 1.0)
    new_v = np.clip(colored_hsv[:, 2] * (target_v / avg_v), 0.0, 1.0)

    result = img_array.copy()
    result[colored_mask, :3] = _hsv_to_rgb_batch(new_h, new_s, new_v)
    return result


def colorize_gif(input_path: Path, output_path: Path, accent_color: str) -> None:
    target_rgb = tuple(
        int(accent_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)
    )
    target_h, target_s, target_v = _rgb_to_hsv(*target_rgb)

    with Image.open(input_path) as gif:
        frames = []
        durations = []
        info = gif.info.copy()

        try:
            while True:
                frame = gif.copy().convert("RGBA")
                arr = np.array(frame, dtype=np.float32)
                recolored = _apply_color_transform(arr, target_h, target_s, target_v)
                frames.append(Image.fromarray(recolored.astype(np.uint8), "RGBA"))
                durations.append(gif.info.get("duration", 100))
                gif.seek(gif.tell() + 1)
        except EOFError:
            pass

    if not frames:
        raise ValueError(f"No GIF frames found in {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=info.get("loop", 0),
        optimize=True,
        disposal=2,
    )
