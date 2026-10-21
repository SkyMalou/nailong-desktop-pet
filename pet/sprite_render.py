"""Premultiplied image transforms for smooth sprite motion."""
import math

from PIL import Image, ImageChops, ImageDraw


def clamp_premultiplied(image):
    b, g, r, a = image.split()
    return Image.merge("RGBa", tuple(ImageChops.darker(c, a)
                                     for c in (b, g, r)) + (a,))


def over(background, foreground):
    inverse = ImageChops.invert(foreground.getchannel("a"))
    return Image.merge("RGBa", tuple(
        ImageChops.add(src, ImageChops.multiply(dst, inverse))
        for dst, src in zip(background.split(), foreground.split())))


def belly_warp(image, amount, top, bottom):
    if abs(amount) < 0.001:
        return image
    w, h = image.size
    start, end = int(h * top), int(h * bottom)
    crop_top, crop_bottom = max(0, start - 4), min(h, end + 4)
    band = image.crop((0, crop_top, w, crop_bottom))
    span = max(1, end - start)

    def source_y(y):
        y += crop_top
        if y <= start or y >= end:
            return float(y - crop_top)
        return y - crop_top + amount * math.sin((y - start) / span * math.pi)

    mesh = []
    edges = sorted(set([0, band.height, start - crop_top, end - crop_top]
                       + list(range(start - crop_top, end - crop_top, 4))))
    for y0, y1 in zip(edges, edges[1:]):
        sy0, sy1 = source_y(y0), source_y(y1)
        mesh.append(((0, y0, w, y1), (0, sy0, 0, sy1, w, sy1, w, sy0)))
    warped = band.transform(band.size, Image.Transform.MESH, mesh,
                            Image.Resampling.BICUBIC)
    result = image.copy()
    result.paste(warped.crop((0, start - crop_top, w, end - crop_top)), (0, start))
    return result


def walking_legs(image, sprite_size, legs, top, swing, lift, ease, phase,
                 flip=False):
    # Warp the canonical orientation and mirror once, so both directions
    # have identical pixel-center conventions and leg overlap.
    if flip:
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    w, h = image.size
    sx, sy = w / sprite_size[0], h / sprite_size[1]
    y_top = int(round(top * sy))
    result = image.copy()
    layers = []
    pad = int(math.ceil(swing * sx)) + 4
    alpha = image.getchannel("a").tobytes()
    cuts = []
    search_left, search_right = round(105 * sx), min(w, round(176 * sx))
    for y in range(y_top, h):
        split = round(legs[1][0] * sx)
        if y / sy >= 240:
            occupied = [x for x in range(search_left, search_right)
                        if alpha[y * w + x] > 32]
            gaps = [(a, b) for a, b in zip(occupied, occupied[1:])
                    if b - a >= 3 and 115 * sx < (a + b) / 2 < 160 * sx]
            if gaps:
                a, b = max(gaps, key=lambda gap: gap[1] - gap[0])
                split = (a + b) // 2
        if y / sy >= legs[0][2] + 1:
            split = round((legs[1][0] - 16) * sx)
        cuts.append(split)
    for index, (left, right, bottom) in enumerate(legs):
        # The nearer foot extends across the vertical leg split beneath the
        # farther sole. Keep that toe with its own foot when the legs cross.
        extended_left = left - 16 if index else left
        extended_right = right if index else right + 16
        x0, x1 = int(round(extended_left * sx)), int(round((extended_right + 1) * sx))
        span = max(1, bottom * sy - y_top)
        width = x1 - x0 + 2 * pad
        layer = Image.new("RGBa", (width, h - y_top))
        layer.paste(image.crop((x0, y_top, x1, h)), (pad, 0))
        split_y = min(layer.height, int(round((legs[0][2] + 1) * sy)) - y_top)
        if not index:
            layer.paste(0, (0, split_y, width, layer.height))
        # Follow the actual transparent gap; the heel and toe extend across
        # the nominal vertical split at different heights.
        boundary = [(cut - x0 + pad - (1 if index else 0), y)
                    for y, cut in enumerate(cuts)]
        outer = 0 if index else width - 1
        ImageDraw.Draw(layer).polygon(
            [(outer, 0)] + boundary + [(outer, layer.height - 1)], fill=0)
        result.paste(0, (x0, y_top, x1, h))
        dx_max = swing * sx * math.sin(phase + index * math.pi)
        dy_max = lift * sy * max(0, math.cos(phase + index * math.pi))
        mesh = []
        for y0 in range(0, layer.height, 4):
            y1 = min(layer.height, y0 + 4)
            e0 = min(1, y0 / span) ** ease
            e1 = min(1, y1 / span) ** ease
            dx0, dx1 = dx_max * e0, dx_max * e1
            sy0, sy1 = y0 + dy_max * e0, y1 + dy_max * e1
            mesh.append(((0, y0, width, y1),
                         (-dx0, sy0, -dx1, sy1,
                          width - dx1, sy1, width - dx0, sy0)))
        layer = layer.transform(layer.size, Image.Transform.MESH, mesh,
                                Image.Resampling.BICUBIC)
        layers.append((layer, x0 - pad))
    for layer, x in layers:
        box = (x, y_top, x + layer.width, h)
        result.paste(over(result.crop(box), layer), (x, y_top))
    if flip:
        result = result.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return result
