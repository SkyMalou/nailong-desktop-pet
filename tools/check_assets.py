"""Validate local media before starting or packaging the pet."""
import json
from pathlib import Path
import sys
import wave
import zlib

ROOT = Path(__file__).resolve().parents[1]


def check(directory):
    missing = [name for name in ('sprite.dat', 'sprite.json', 'laugh.wav')
               if not (directory / name).is_file()]
    if missing:
        raise ValueError('Missing local assets: %s. See ASSETS.md.' % ', '.join(missing))
    meta = json.loads((directory / 'sprite.json').read_text(encoding='utf-8'))
    w, h, n = (meta[name] for name in ('w', 'h', 'n'))
    if not all(isinstance(value, int) and value > 0 for value in (w, h, n)):
        raise ValueError('Sprite dimensions and frame count must be positive integers.')
    for name in ('idle', 'laugh'):
        lo, hi = meta[name]
        if not (0 <= lo <= hi < n):
            raise ValueError('Invalid %s animation range.' % name)
    expected = w * h * n * 4
    decoder = zlib.decompressobj()
    decoded = decoder.decompress((directory / 'sprite.dat').read_bytes(), expected + 1)
    if len(decoded) != expected or not decoder.eof or decoder.unused_data:
        raise ValueError('Sprite data does not match sprite.json.')
    with wave.open(str(directory / 'laugh.wav'), 'rb') as audio:
        if audio.getcomptype() != 'NONE' or audio.getnframes() <= 0:
            raise ValueError('laugh.wav must contain uncompressed PCM audio.')
    return w, h, n


def main():
    try:
        w, h, n = check(ROOT / 'pet')
    except (ValueError, KeyError, TypeError, OSError, zlib.error, wave.Error) as error:
        print('Asset check failed: %s' % error, file=sys.stderr)
        return 1
    print('Assets OK: %d x %d, %d frames.' % (w, h, n))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
