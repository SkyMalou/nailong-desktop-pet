# -*- coding: utf-8 -*-
"""
把 奶龙大笑.mp4 的抽帧处理成桌宠精灵：
1. 洪水填充从四边抠掉白色背景（保留肚皮白毛）
2. 统一裁剪 + 缩放，输出带透明通道的帧
3. 打包为 sprite.dat（zlib 压缩的预乘 BGRA 帧）+ sprite.json 元数据
"""
import glob
import json
import os
import zlib
from collections import deque

from PIL import Image, ImageFilter
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES_DIR = os.path.join(HERE, "frames")
OUT_DAT = os.path.join(HERE, "sprite.dat")
OUT_JSON = os.path.join(HERE, "sprite.json")

TARGET_H = None         # 保持原生分辨率（不缩放）
IDLE_LAST = 15          # f_001..f_015 为站立待机
LAUGH_FIRST = 18        # f_018 开始大笑
FPS = 12
CROP_BOX = (217, 58, 460, 377)  # Keep the coordinate system used by eyes and legs.


def defringe(rgba, max_dist=4):
    """Recover local foreground color from the original white matte."""
    arr = np.array(rgba)
    rgb = arr[:, :, :3].astype(np.float32)
    alpha = arr[:, :, 3].astype(np.float32) / 255.0
    h, w = alpha.shape
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]))
    background = np.median(border, axis=0)
    solid = alpha >= 0.98
    edge = (alpha > 0) & ~solid
    ref = rgb.copy()
    found = np.zeros((h, w), dtype=bool)
    pad_rgb = np.pad(rgb, ((max_dist, max_dist), (max_dist, max_dist), (0, 0)), mode="edge")
    pad_solid = np.pad(solid, max_dist)
    offsets = sorted(((dy, dx) for dy in range(-max_dist, max_dist + 1)
                      for dx in range(-max_dist, max_dist + 1)),
                     key=lambda p: p[0] ** 2 + p[1] ** 2)
    for dy, dx in offsets:
        ys, xs = max_dist + dy, max_dist + dx
        valid = edge & ~found & pad_solid[ys:ys + h, xs:xs + w]
        ref[valid] = pad_rgb[ys:ys + h, xs:xs + w][valid]
        found |= valid

    # C = alpha * F + (1 - alpha) * B. Project onto the local F/B line.
    direction = background - ref
    denom = np.sum(direction * direction, axis=2)
    coverage = np.sum((background - rgb) * direction, axis=2) / np.maximum(denom, 1)
    coverage = np.clip(coverage, 0, 1)
    recover = edge & found & (denom > 100)
    alpha[recover] = coverage[recover]
    corrected = (rgb - (1 - alpha[:, :, None]) * background) / np.maximum(alpha[:, :, None], 1 / 255.0)
    rgb[recover] = corrected[recover]
    arr[:, :, :3] = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
    arr[:, :, 3] = np.rint(alpha * 255).astype(np.uint8)
    arr[arr[:, :, 3] == 0, :3] = 0
    return Image.fromarray(arr)


def key_frame(img):
    """返回 RGBA 图，背景透明。洪水填充 + 边缘羽化。"""
    img = img.convert("RGB")
    w, h = img.size
    px = img.load()

    # 背景参考色：四边像素的中值
    border = []
    for x in range(0, w, 7):
        border.append(px[x, 0]); border.append(px[x, h - 1])
    for y in range(0, h, 7):
        border.append(px[0, y]); border.append(px[w - 1, y])
    rs = sorted(p[0] for p in border)
    gs = sorted(p[1] for p in border)
    bs = sorted(p[2] for p in border)
    br, bg_, bb = rs[len(rs) // 2], gs[len(gs) // 2], bs[len(bs) // 2]

    def is_bg(p):
        dr = p[0] - br; dg = p[1] - bg_; db = p[2] - bb
        if dr * dr + dg * dg + db * db < 1600:      # 距离 < 40
            return True
        # 白/极浅的软阴影块（贴近背景色但略有色偏）也算背景：
        # 高亮度、低饱和，且亮度不低于背景太多
        v = max(p); c = max(p) - min(p)
        bv = max(br, bg_, bb)
        return v > 195 and c < 26 and v >= bv - 18

    mask = bytearray(w * h)  # 1=背景
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if is_bg(px[x, y]) and not mask[y * w + x]:
                mask[y * w + x] = 1
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if is_bg(px[x, y]) and not mask[y * w + x]:
                mask[y * w + x] = 1
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h:
                i = ny * w + nx
                if not mask[i] and is_bg(px[nx, ny]):
                    mask[i] = 1
                    q.append((nx, ny))

    # 第二次清理（宽松阈值）：清除与背景断开的浅色地面阴影。
    # 阴影有两类：暖白（如 RGB 222,209,187，饱和度低）和浅蓝灰（饱和度中等）。
    # 奶龙身体是高饱和黄（红蓝都远高于绿的部分不会命中），白肚皮饱和度也不够低。
    # 关键：种子不是"图像边界"（边界早被第一次填充掩掉，那样永远没有种子），
    # 而是"已掩区域的边界"—— 从包围阴影的已掩背景向内生长，孤岛也能被吃掉。
    def is_loose_bg(p):
        v = max(p)
        c = max(p) - min(p)
        if v <= 150:
            return False
        if c < 40:
            return True
        # 浅蓝灰阴影：偏蓝（b>=r）且饱和度不高
        return p[2] >= p[0] and c < 75

    q = deque()
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if mask[i]:
                continue
            # 未掩像素：四邻里只要有一个已掩（贴着背景/阴影外围），就作种子
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and mask[ny * w + nx] \
                        and is_loose_bg(px[x, y]):
                    mask[i] = 1
                    q.append((x, y))
                    break
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h:
                i = ny * w + nx
                if not mask[i] and is_loose_bg(px[nx, ny]):
                    mask[i] = 1
                    q.append((nx, ny))

    # alpha：前景 255，然后整体轻微羽化边缘
    alpha = Image.frombytes("L", (w, h), bytes(
        0 if mask[i] else 255 for i in range(w * h)))
    alpha = alpha.filter(__import__("PIL.ImageFilter", fromlist=["x"])
                         .GaussianBlur(0.55))

    # The space between overlapping feet can enclose the pale floor shadow,
    # making it unreachable from the border flood fill. Restrict this cleanup
    # to the ground band so pale belly details and teeth remain intact.
    colors = np.array(img)
    ground = np.arange(h)[:, None] >= int(h * 0.82)
    pale = (np.ptp(colors, axis=2) < 55) & (colors.max(axis=2) > 175)
    coverage = np.array(alpha)
    coverage[ground & pale] = 0
    alpha = Image.fromarray(coverage)

    out = img.convert("RGBA")
    out.putalpha(alpha)
    return out


def refine_detail(rgba):
    """A restrained detail pass inside the silhouette, leaving matte edges alone."""
    rgb = rgba.convert("RGB")
    detail = rgb.filter(ImageFilter.UnsharpMask(radius=0.75, percent=60, threshold=2))
    interior = rgba.getchannel("A").filter(ImageFilter.MinFilter(5))
    interior = interior.point(lambda a: 255 if a >= 250 else 0)
    result = Image.composite(detail, rgb, interior).convert("RGBA")
    result.putalpha(rgba.getchannel("A"))
    return result


def main():
    files = sorted(glob.glob(os.path.join(FRAMES_DIR, "f_*.png")))
    if len(files) < LAUGH_FIRST:
        raise ValueError("Expected at least %d input frames in pet/frames; see ASSETS.md."
                         % LAUGH_FIRST)
    print("frames:", len(files))
    keyed = []
    for i, path in enumerate(files):
        with Image.open(path) as source:
            keyed.append(refine_detail(defringe(key_frame(source.crop(CROP_BOX)))))
        if (i + 1) % 24 == 0:
            print("processed:", i + 1, flush=True)

    # 统一裁剪框（取所有帧内容并集）
    l, t = 0, 0
    r, btm = keyed[0].size
    print("crop box:", l, t, r, btm)

    crop_w, crop_h = r - l, btm - t
    if TARGET_H:
        scale = TARGET_H / crop_h
        out_w = max(1, int(crop_w * scale))
        out_h = TARGET_H
    else:
        out_w, out_h = crop_w, crop_h

    rgba = []
    for k in keyed:
        c = k.crop((l, t, r, btm)).resize((out_w, out_h), Image.LANCZOS)
        rgba.append(c.tobytes())

    # 预乘 alpha 并转为 BGRA（UpdateLayeredWindow 直接可用）
    frames = []
    for data in rgba:
        pixels = np.frombuffer(data, dtype=np.uint8).reshape(-1, 4)
        buf = pixels[:, [2, 1, 0, 3]].copy()
        buf[:, :3] = (buf[:, :3].astype(np.uint16)
                      * buf[:, 3:4].astype(np.uint16) + 127) // 255
        frames.append(buf.tobytes())

    blob = zlib.compress(b"".join(frames), 6)
    with open(OUT_DAT, "wb") as f:
        f.write(blob)

    n = len(frames)
    meta = dict(w=out_w, h=out_h, n=n, fps=FPS, crop=list(CROP_BOX),
                idle=[0, min(IDLE_LAST, n - 1)],
                laugh=[min(LAUGH_FIRST, n - 1) - 1, n - 1])
    # laugh 用 0-based：f_018 -> 索引 17
    meta["laugh"] = [LAUGH_FIRST - 1, n - 1]
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("done:", out_w, "x", out_h, "x", n,
          "%.1f MB" % (os.path.getsize(OUT_DAT) / 1048576))


if __name__ == "__main__":
    main()
