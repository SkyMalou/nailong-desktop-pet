# -*- mode: python ; coding: utf-8 -*-
import os

a = Analysis(
    ['pet/nailong_pet.py'],
    pathex=['pet'],
    binaries=[],
    datas=[('pet/sprite.dat', '.'), ('pet/sprite.json', '.'), ('pet/laugh.wav', '.')],
    hiddenimports=['PIL.Image', 'PIL.ImageChops', 'PIL.ImageDraw', 'sprite_render'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'scipy', 'sounddevice', 'cffi', 'imageio_ffmpeg'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='NailongPet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon='pet/icon.ico' if os.path.isfile('pet/icon.ico') else None,
)
