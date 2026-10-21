"""Import user-supplied media without adding it to version control."""
import argparse
from pathlib import Path
import shutil

from check_assets import ROOT, check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-dir', type=Path, required=True)
    args = parser.parse_args()
    source = args.from_dir.resolve()
    if (source / 'pet').is_dir():
        source /= 'pet'
    check(source)
    destination = ROOT / 'pet'
    for name in ('sprite.dat', 'sprite.json', 'laugh.wav', 'icon.ico'):
        path = source / name
        if path.is_file() and path.resolve() != (destination / name).resolve():
            shutil.copy2(path, destination / name)
    check(destination)
    print('Local assets imported. Media files remain excluded from Git.')


if __name__ == '__main__':
    main()
