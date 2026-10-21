"""Rendering regressions and an optional before/after contact sheet."""
import ctypes
import json
import os
import sys
import unittest
import zlib
from types import SimpleNamespace

# Load the Pillow build belonging to the interpreter running this test.
from PIL import Image, ImageDraw
import numpy as np
import nailong_pet as NP
from build_sprites import defringe

HERE = os.path.dirname(os.path.abspath(__file__))


class QualityTests(unittest.TestCase):
    def setUp(self):
        NP._SCALE_CACHE.clear()

    def test_premultiplied_resize_preserves_edge_color(self):
        pixels = np.zeros((8, 8, 4), dtype=np.uint8)
        pixels[2:6, 2:6] = (40, 80, 120, 128)
        pet = object.__new__(NP.Pet)
        pet.sp = SimpleNamespace(w=8, h=8, frames=[pixels.tobytes()])
        pet.w, pet.h = 23, 23
        result = np.frombuffer(pet._scale_frame(0), np.uint8).reshape(23, 23, 4)
        self.assertTrue(np.all(result[:, :, :3] <= result[:, :, 3:4]))
        a = result[:, :, 3].astype(float)
        edges = (a > 10) & (a < 90)
        self.assertGreater(int(edges.sum()), 20)
        ratios = result[:, :, 2][edges] / a[edges]
        self.assertLess(float(np.max(np.abs(ratios - 120 / 128))), 0.08)
        mirrored = pet._scale_frame(0, True)
        self.assertEqual(mirrored, result[:, ::-1].tobytes())

    def test_matte_recovers_local_colors_and_preserves_interior(self):
        image = np.full((13, 18, 4), 255, dtype=np.uint8)
        image[:, :, 3] = 0
        image[4:9, 3:7] = (240, 180, 30, 255)
        image[4:9, 11:15] = (60, 90, 40, 255)
        image[4:9, 7] = (248, 218, 143, 128)
        image[4:9, 10] = (158, 173, 148, 128)
        result = np.array(defringe(Image.fromarray(image)))
        self.assertTrue(np.array_equal(result[4:9, 3:7], image[4:9, 3:7]))
        for x, color in ((7, (240, 180, 30)), (10, (60, 90, 40))):
            np.testing.assert_allclose(result[6, x, :3], color, atol=3)
            self.assertLess(abs(int(result[6, x, 3]) - 128), 3)

    @unittest.skipUnless(os.path.isfile(os.path.join(HERE, "sprite.dat")),
                         "Local sprite assets are not included in the public repository")
    def test_every_asset_is_valid_premultiplied_bgra(self):
        sp = NP.Sprite(HERE)
        self.assertEqual((sp.w, sp.h, sp.n), (243, 319, 216))
        for frame in sp.frames:
            pixels = np.frombuffer(frame, np.uint8).reshape(-1, 4)
            self.assertEqual(len(frame), sp.stride)
            self.assertTrue(np.all(pixels[:, :3] <= pixels[:, 3:4]))
        self.assertTrue(all(sp.eyes[i - sp.idle_lo] is not None for i in sp.idle_play))
        self.assertLessEqual(abs(sp.idle_play[-1] - sp.idle_play[0]), 1)


def to_rgba(data, size):
    return Image.frombytes("RGBa", size, data, "raw", "BGRa").convert("RGBA")


def preview():
    sp = NP.Sprite(HERE)
    with open(os.path.join(HERE, "sprite.before-quality.dat"), "rb") as f:
        previous = zlib.decompress(f.read())
    w, h = sp.w, sp.h
    sheet = Image.new("RGB", (w * 6, h * 2 + 60), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 8), "BEFORE / AFTER - light, dark, colored desktop", fill="black")
    for row, idx in enumerate((0, 65)):
        for bg_idx, bg in enumerate(("#fafafa", "#23272d", "#7a9e87")):
            for version in range(2):
                data = (sp.frames[idx] if version else
                        previous[idx * sp.stride:(idx + 1) * sp.stride])
                tile = Image.new("RGBA", (w, h), bg)
                tile.alpha_composite(to_rgba(data, (w, h)))
                x, y = (bg_idx * 2 + version) * w, row * h + 40
                sheet.paste(tile.convert("RGB"), (x, y))
    output = os.path.join(HERE, "quality-comparison.png")
    sheet.save(output)
    print(output)

    pet = object.__new__(NP.Pet)
    pet.sp = sp
    pet.w, pet.h = w, h
    pet.max_w, pet.max_h = w, h
    pet.face, pet.idx = 1, 0
    pet.dst_buf = (ctypes.c_ubyte * sp.stride)()
    closeups = Image.new("RGB", (150 * 4, 150), "#f4f4f4")
    for col, off in enumerate(((-3.4, 0), (3.4, 0), (0, -2.6), (0, 2.6))):
        pet.eye_off = off
        ctypes.memmove(pet.dst_buf, sp.frames[0], sp.stride)
        pet._draw_eyes(sp.frames[0])
        eye = to_rgba(bytes(pet.dst_buf), (w, h)).crop((94, 10, 124, 40))
        eye = eye.resize((150, 150), Image.Resampling.NEAREST)
        closeups.paste(eye, (col * 150, 0), eye)
    closeups.save(os.path.join(HERE, "quality-eyes.png"))


if __name__ == "__main__":
    if "--preview" in sys.argv:
        preview()
    else:
        unittest.main()
