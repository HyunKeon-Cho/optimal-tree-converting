"""Convert Liberty to JSON without discarding timing tables or pin information.

Usage: python utiles/lib2json.py [input.lib] [-o output.json]
No third-party packages required. Numeric values retain the library's units.
"""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|[{}():;,]|[^\s{}():;,"\\]+|\\', re.S)


def scalar(token):
    if token.startswith('"'):
        return re.sub(r'\\(["\\])', r'\1', token[1:-1])
    if re.fullmatch(r'[+-]?\d+', token):
        return int(token)
    if re.fullmatch(r'[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?', token):
        return float(token)
    return token


class Parser:
    def __init__(self, source):
        self.tokens = []
        position = 0
        for match in TOKEN.finditer(source):
            if source[position:match.start()].strip():
                raise ValueError(f"Unrecognized Liberty text near character {position}")
            position = match.end()
            token = match.group()
            if not token.startswith(('/*', '//')) and token != '\\':
                self.tokens.append(token)
        if source[position:].strip():
            raise ValueError("Unrecognized trailing Liberty text")
        self.pos = 0

    def pop(self, expected=None):
        if self.pos >= len(self.tokens):
            raise ValueError("Unexpected end of Liberty file")
        token = self.tokens[self.pos]
        self.pos += 1
        if expected is not None and token != expected:
            raise ValueError(f"Expected {expected!r}, got {token!r} at token {self.pos}")
        return token

    def until(self, end):
        values = []
        while self.pos < len(self.tokens) and self.tokens[self.pos] != end:
            values.append(self.pop())
        self.pop(end)
        return values

    def body(self, closing=False):
        result = {"attributes": {}, "complex_attributes": [], "groups": []}
        while self.pos < len(self.tokens):
            if self.tokens[self.pos] == '}':
                if not closing:
                    raise ValueError("Unexpected closing brace")
                self.pop('}')
                return result
            name = self.pop()
            delimiter = self.pop()
            if delimiter == ':':
                tokens = self.until(';')
                if not tokens:
                    raise ValueError(f"Empty attribute: {name}")
                result['attributes'][name] = scalar(tokens[0]) if len(tokens) == 1 else ' '.join(tokens)
            elif delimiter == '(':
                tokens = self.until(')')
                # Liberty group arguments and complex attributes use comma-separated scalars.
                args, part = [], []
                for token in tokens + [',']:
                    if token == ',':
                        if part:
                            args.append(scalar(part[0]) if len(part) == 1 else ' '.join(part))
                        part = []
                    else:
                        part.append(token)
                following = self.pop()
                if following == '{':
                    result['groups'].append({"type": name, "args": args, **self.body(True)})
                elif following == ';':
                    if name.startswith('index_') or name == 'values':
                        rows = [[float(v.strip()) for v in str(row).split(',')] for row in args]
                        args = rows if name == 'values' else (rows[0] if len(rows) == 1 else rows)
                    result['complex_attributes'].append({"name": name, "values": args})
                else:
                    raise ValueError(f"Expected group or complex attribute after {name}")
            else:
                raise ValueError(f"Unsupported Liberty statement: {name} {delimiter}")
        if closing:
            raise ValueError("Missing closing brace")
        return result


def convert(path):
    document = Parser(Path(path).read_text(encoding='utf-8-sig')).body()
    libraries = [g for g in document['groups'] if g['type'] == 'library']
    if len(libraries) != 1:
        raise ValueError("Expected exactly one library group")
    library = libraries[0]
    cells = {}
    for group in library['groups']:
        if group['type'] != 'cell':
            continue
        name = str(group['args'][0])
        if name in cells:
            raise ValueError(f"Duplicate cell: {name}")
        pins = {}
        for pin in group['groups']:
            if pin['type'] == 'pin':
                pin_name = str(pin['args'][0])
                pins[pin_name] = {
                    **pin['attributes'],
                    "complex_attributes": pin['complex_attributes'],
                    "timing": [g for g in pin['groups'] if g['type'] == 'timing'],
                    "other_groups": [g for g in pin['groups'] if g['type'] != 'timing'],
                }
        cells[name] = {
            "area": group['attributes'].get('area'),
            "inputs": [n for n, p in pins.items() if p.get('direction') == 'input'],
            "outputs": [n for n, p in pins.items() if p.get('direction') == 'output'],
            "functions": {n: p['function'] for n, p in pins.items() if 'function' in p},
            "pins": pins,
            "attributes": group['attributes'],
            "complex_attributes": group['complex_attributes'],
            "other_groups": [g for g in group['groups'] if g['type'] != 'pin'],
        }
    return {
        "schema_version": 1,
        "source": Path(path).name,
        "library": library['args'][0],
        "attributes": library['attributes'],
        "complex_attributes": library['complex_attributes'],
        "groups": [g for g in library['groups'] if g['type'] != 'cell'],
        "cells": cells,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', type=Path, default=ROOT / 'reference/NangateOpenCellLibrary_typical.lib')
    parser.add_argument('-o', '--output', type=Path, default=ROOT / 'outputs/nangate45.json')
    args = parser.parse_args()
    try:
        data = convert(args.input)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except (OSError, ValueError, IndexError) as error:
        parser.exit(1, f"lib2json: {error}\n")
    print(f"Wrote {len(data['cells'])} cells to {args.output}")


if __name__ == '__main__':
    main()
