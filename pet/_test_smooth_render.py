"""Offscreen regression checks and previews of the supersampled renderer."""
import copy
import ctypes
import math
import os
import statistics
import sys
import time
import unittest
import zlib
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import label
import nailong_pet as NP
from _test_quality import to_rgba

HERE = os.path.dirname(os.path.abspath(__file__))


def make_pet(sprite, scale=0.9):
    pet = object.__new__(NP.Pet)
    pet.sp = sprite
    pet.w, pet.h = round(sprite.w * scale), round(sprite.h * scale)
    pet.max_w, pet.max_h = pet.w, pet.h
    pet.idx, pet.face = 0, 1
    pet.mode, pet.dying = "idle", False
    pet.walk_dir, pet.wob = 0, 0.0
    pet.eye_off, pet.idle_mix = [0.0, 0.0], None
    pet.dst_buf = (ctypes.c_ubyte * (pet.w * pet.h * 4))()
    return pet


@unittest.skipUnless(os.path.isfile(os.path.join(HERE, "sprite.dat")),
                     "Local sprite assets are not included in the public repository")
class SmoothTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sprite = NP.Sprite(HERE)

    def setUp(self):
        NP._SCALE_CACHE.clear()

    def test_states_and_sizes_remain_valid(self):
        for scale in (0.4, 0.9, 2.2):
            pet = make_pet(self.sprite, scale)
            for state in ("idle", "walk", "belly", "laugh"):
                with self.subTest(scale=scale, state=state):
                    pet.mode = "laugh" if state == "laugh" else "idle"
                    pet.idx = 65 if state == "laugh" else 0
                    pet.walk_dir = int(state == "walk")
                    pet.wob = -pet.h * 0.1 if state == "belly" else 0
                    data = pet._render_pixels(pet.idx)
                    self.assertEqual(len(data), pet.w * pet.h * 4)
                    pixels = np.frombuffer(data, np.uint8).reshape(-1, 4)
                    self.assertTrue(np.all(pixels[:, :3] <= pixels[:, 3:4]))
                    self.assertGreater(int((pixels[:, 3] > 200).sum()), pet.w * pet.h // 5)

    def test_subpixel_belly_motion_and_fixed_head(self):
        pet = make_pet(self.sprite)
        before = np.frombuffer(pet._render_pixels(0), np.uint8).reshape(pet.h, pet.w, 4)
        pet.wob = 0.24
        after = np.frombuffer(pet._render_pixels(0), np.uint8).reshape(pet.h, pet.w, 4)
        self.assertGreater(int(np.count_nonzero(before != after)), 100)
        np.testing.assert_array_equal(before[:60], after[:60])

    def test_walking_preserves_head_and_mirrors_exactly(self):
        pet = make_pet(self.sprite)
        still = np.frombuffer(pet._render_pixels(0), np.uint8).reshape(pet.h, pet.w, 4)
        pet.walk_dir = 1
        with patch.object(NP.time, "time", return_value=0.077):
            normal = np.frombuffer(pet._render_pixels(0), np.uint8).reshape(pet.h, pet.w, 4)
            pet.face = -1
            mirrored = np.frombuffer(pet._render_pixels(0), np.uint8).reshape(pet.h, pet.w, 4)
        np.testing.assert_array_equal(normal[:160], still[:160])
        np.testing.assert_allclose(normal[:, :, 3], mirrored[:, ::-1, 3], atol=1)
        self.assertGreater(int(np.count_nonzero(normal[190:] != still[190:])), 1000)

    def test_one_window_paint_per_tick(self):
        class RecordingPet(NP.Pet):
            def render(self, idx):
                if getattr(self, "_in_tick", False):
                    return super().render(idx)
                self.paints.append(idx)

            def _advance_tick(self):
                for idx in (1, 2, 3):
                    self.render(idx)

        pet = object.__new__(RecordingPet)
        pet.hwnd, pet.paints = 1, []
        pet._tick()
        self.assertEqual(pet.paints, [3])

    def test_no_detached_foot_fragments_through_a_stride(self):
        pet = make_pet(self.sprite)
        pet.walk_dir = 1
        for idx in (0, 4, 7):
            pet.idx = idx
            for step in range(26):
                with self.subTest(frame=idx, phase=step):
                    with patch.object(NP.time, "time",
                                      return_value=step / 26 / NP.WALK_BOB_HZ):
                        pixels = np.frombuffer(pet._render_pixels(idx), np.uint8)
                    alpha = pixels.reshape(pet.h, pet.w, 4)[:, :, 3]
                    components, _ = label(alpha > 100)
                    sizes = sorted(np.bincount(components.ravel())[1:], reverse=True)
                    self.assertTrue(all(size <= 3 for size in sizes[1:]), sizes)


def old_pixels(pet):
    source = pet._scale_frame(pet.idx, pet.face < 0)
    ctypes.memmove(pet.dst_buf, source, len(source))
    if pet.walk_dir:
        pet._blit_walking_legs(ctypes.addressof(pet.dst_buf), pet.w * 4,
                               source, pet.w * 4)
    pet._draw_eyes(source)
    return bytes(pet.dst_buf)


def preview():
    sprite = NP.Sprite(HERE)
    before = copy.copy(sprite)
    with open(os.path.join(HERE, "sprite.before-smooth.dat"), "rb") as f:
        blob = zlib.decompress(f.read())
    before.frames = [blob[i * sprite.stride:(i + 1) * sprite.stride]
                     for i in range(sprite.n)]
    old, new = make_pet(before), make_pet(sprite)
    old.walk_dir = new.walk_dir = 1
    w, h = old.w, old.h
    sheet = Image.new("RGB", (w * 4, h * 2 + 56), "#eceff1")
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 6), "PREVIOUS - integer motion", fill="black")
    draw.text((8, h + 34), "NEW - supersampled, subpixel motion", fill="black")
    animation = []
    for i in range(26):
        frame = Image.new("RGBA", (w * 2, h + 24), "#eceff1")
        for version, pet in enumerate((old, new)):
            NP._SCALE_CACHE.clear()
            t = i / 26 / NP.WALK_BOB_HZ
            # The previous timer updated half as often.
            t = t if version else (i // 2 * 2) / 26 / NP.WALK_BOB_HZ
            with patch.object(NP.time, "time", return_value=t):
                data = pet._render_pixels(0) if version else old_pixels(pet)
            rgba = to_rgba(data, (w, h))
            frame.alpha_composite(rgba, (version * w, 24))
            if i in (0, 6, 13, 19):
                column = (0, 6, 13, 19).index(i)
                tile = Image.new("RGBA", (w, h), "#eceff1")
                tile.alpha_composite(rgba)
                sheet.paste(tile.convert("RGB"), (column * w, version * (h + 28) + 28))
        ImageDraw.Draw(frame).text((8, 6), "PREVIOUS                              NEW", fill="black")
        animation.append(frame.convert("RGB"))
    sheet.save(os.path.join(HERE, "smooth-comparison.png"))
    animation[0].save(os.path.join(HERE, "smooth-preview.webp"), save_all=True,
                      append_images=animation[1:], duration=16, loop=0, lossless=True)


def benchmark():
    sprite = NP.Sprite(HERE)
    for scale in (0.9, 2.2):
        for state in ("idle", "walk", "belly"):
            pet = make_pet(sprite, scale)
            pet.walk_dir = int(state == "walk")
            pet.wob = pet.h * 0.06 if state == "belly" else 0
            pet._render_pixels(0)
            samples = []
            for _ in range(12):
                start = time.perf_counter()
                pet._render_pixels(0)
                samples.append((time.perf_counter() - start) * 1000)
            print("scale=%.1f %s median=%.1fms max=%.1fms" %
                  (scale, state, statistics.median(samples), max(samples)))


if __name__ == "__main__":
    if "--preview" in sys.argv:
        preview()
    elif "--benchmark" in sys.argv:
        benchmark()
    else:
        unittest.main()
