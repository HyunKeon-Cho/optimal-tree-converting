
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def filter():
    rst = {}

    

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-i', '--input', type=Path, default=ROOT / 'reference/modified/nangate45.json')
    parser.add_argument('-o', '--output', type=Path, default=ROOT / 'input/library.json')
    args = parser.parse_args()
    try:
        pass

    except (OSError, ValueError, UnicodeError, IndexError) as error:
        parser.exit(1, f"logic2graph: {error}\n")


if __name__ == '__main__':
    main()