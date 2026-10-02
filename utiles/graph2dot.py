"""Export a circuit JSON as DOT for Interactive Graphviz (default: adder)."""

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = Path(__file__).resolve().parent / "symbols"
SYMBOL_FILES = {"AND": "and.svg", "NAND": "nand.svg", "NOT": "not.svg", "INV": "not.svg"}
STYLES = {
    "INPUT": ("box", "#dbeafe"),
    "OUTPUT": ("box", "#dcfce7"),
    "AND": ("box", "#f1f5f9"),
    "INV": ("box", "#fef3c7"),
    "NOT": ("box", "#fef3c7"),
    "NAND": ("box", "#ede9fe"),
    "CONST": ("box", "#e2e8f0"),
}


def quote(value):
    return json.dumps(str(value), ensure_ascii=False)


def node_label(node, ports, basic):
    """HTML port cells fix each input to the left and the output to the right."""
    op = node["op"]
    label = node.get("name", op)
    if op == "CONST":
        label = str(int(node["value"]))
    if not basic and op in SYMBOL_FILES:
        expected = 2 if op in ("AND", "NAND") else 1
        if ports != list(range(expected)):
            raise ValueError(f"{op} symbol requires input ports {list(range(expected))}, got {ports}")
        symbol = SYMBOLS / SYMBOL_FILES[op]
        dimensions = ET.parse(symbol).getroot()
        width, symbol_height = int(dimensions.get("width")), int(dimensions.get("height"))
        image = html.escape(symbol.as_posix(), quote=True)
        content = f'<IMG SRC="{image}" SCALE="TRUE"/>'
        body = f'<TD ROWSPAN="{expected}" WIDTH="{width}" HEIGHT="{symbol_height}" FIXEDSIZE="TRUE">{content}</TD>'
        border, color = 0, "white"
    else:
        palette = ("#fce7f3", "#ffedd5", "#ccfbf1", "#e0e7ff", "#fef9c3", "#cffafe")
        color = STYLES.get(op, ("box", palette[hashlib.sha256(op.encode()).digest()[0] % len(palette)]))[1]
        content = html.escape(str(label), quote=True)
        body = f'<TD ROWSPAN="{max(1, len(ports))}" WIDTH="72">{content}</TD>'
        border = 1
    rows = max(1, len(ports))
    table = [f'<TABLE BORDER="{border}" COLOR="#334155" BGCOLOR="{color}" CELLBORDER="0" CELLSPACING="0" CELLPADDING="0">']
    for row in range(rows):
        # Pins are centered in each input row; SVG dimensions set the layout size.
        height = symbol_height // rows if not basic and op in SYMBOL_FILES else 20
        pin = f' PORT="i{ports[row]}"' if ports else ""
        table.append(f'<TR><TD{pin} WIDTH="1" HEIGHT="{height}"></TD>')
        if row == 0:
            table.append(body)
            table.append(f'<TD PORT="o" ROWSPAN="{rows}" WIDTH="1"></TD>')
        table.append('</TR>')
    table.append('</TABLE>')
    return "".join(table)


def to_dot(graph, fast=False, basic=False):
    nodes = graph["nodes"]
    ports = [set() for _ in nodes]
    for edge in graph["edges"]:
        source, target = edge["source"], edge["target"]
        if not (0 <= source < len(nodes) and 0 <= target < len(nodes)):
            raise ValueError(f"Invalid edge endpoints: {source} -> {target}")
        port = edge["port"]
        if not isinstance(port, int) or port < 0:
            raise ValueError(f"Invalid input port: {port}")
        ports[target].add(port)
    lines = [
        "digraph circuit {",
        '  graph [rankdir=LR, bgcolor="white", nodesep=0.2, ranksep=0.6];',
        '  node [shape=plain, fontname="Arial", fontsize=10];',
        '  edge [color="#64748b", arrowhead=none, tailport="o:e"];',
        f'  label={quote(graph.get("source", "Circuit"))};',
        '  labelloc="t";',
    ]
    if fast:
        # Bound layout optimization and draw straight edges for a quick preview.
        lines.append('  graph [splines=line, nslimit=0.1, nslimit1=0.1, mclimit=0.1];')
    for index, node in enumerate(nodes):
        op = node["op"]
        tooltip = f"Node {index}: {op}"
        label = node_label(node, sorted(ports[index]), basic)
        lines.append(
            f"  n{index} [label=<{label}>, tooltip={quote(tooltip)}];"
        )
    # Forcing all outputs to the final rank creates long edges and extra work.
    ranks = () if fast else (("INPUT", "source"), ("OUTPUT", "sink"))
    for op, rank in ranks:
        members = " ".join(f"n{i};" for i, node in enumerate(nodes) if node["op"] == op)
        if members:
            lines.append(f"  {{ rank={rank}; {members} }}")
    for edge in graph["edges"]:
        source, target = edge["source"], edge["target"]
        if not (0 <= source < len(nodes) and 0 <= target < len(nodes)):
            raise ValueError(f"Invalid edge endpoints: {source} -> {target}")
        tooltip = f"Node {source} -> Node {target}, input port {edge['port']}"
        lines.append(f'  n{source} -> n{target} [headport="i{edge["port"]}:w", tooltip={quote(tooltip)}];')
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_svg(dot_path, output):
    """Render with native dot or the installed extension's bundled WebAssembly."""
    native_dot = shutil.which("dot")
    if native_dot:
        command = [native_dot, "-Tsvg", str(dot_path), "-o", str(output)]
    else:
        extensions = Path.home() / ".vscode/extensions"
        renderers = sorted(extensions.glob("tintinweb.graphviz-interactive-preview-*/content/dist"))
        node = shutil.which("node")
        bundled_node = Path(sys.executable).parent.parent / "node/bin/node.exe"
        if node is None and bundled_node.is_file():
            node = str(bundled_node)
        if not node or not renderers:
            raise ValueError("SVG rendering needs Graphviz dot, or Node.js and the Interactive Graphviz extension")
        command = [node, str(Path(__file__).with_name("render_graphviz.cjs")), str(renderers[-1]),
                   str(dot_path), str(output), str(SYMBOLS)]
    subprocess.run(command, check=True, timeout=120)
    # Embed the actual artwork so the resulting SVG has no external file dependency.
    namespace = "http://www.w3.org/2000/svg"
    ET.register_namespace("", namespace)
    tree = ET.parse(output)
    for parent in tree.iter():
        for element in list(parent):
            if element.tag != f"{{{namespace}}}image":
                continue
            href = element.get("{http://www.w3.org/1999/xlink}href", element.get("href", ""))
            symbol = SYMBOLS / Path(href).name
            if symbol.name not in set(SYMBOL_FILES.values()) or not symbol.is_file():
                raise ValueError(f"Unknown SVG image: {href}")
            artwork = ET.parse(symbol).getroot()
            for attribute in ("x", "y", "width", "height"):
                artwork.set(attribute, element.get(attribute, "0"))
            parent.insert(list(parent).index(element), artwork)
            parent.remove(element)
    # The extension's WASM can reserve an image's size but omit its artwork.
    # Insert the symbol at the reserved node rectangle in that case.
    symbol_nodes = {}
    for line in dot_path.read_text(encoding="utf-8").splitlines():
        match = re.match(r'  (n\d+) \[.*<IMG SRC="([^"]+)"', line)
        if match:
            symbol_nodes[match[1]] = SYMBOLS / Path(html.unescape(match[2])).name
    embedded = 0
    for group in tree.iter(f"{{{namespace}}}g"):
        if group.get("class") != "node":
            continue
        title = group.find(f"{{{namespace}}}title")
        symbol = symbol_nodes.get(title.text if title is not None else "")
        if symbol is None:
            continue
        if group.find(f".//{{{namespace}}}svg") is None:
            polygon = group.find(f".//{{{namespace}}}polygon")
            if polygon is None:
                raise ValueError(f"Missing symbol rectangle at {title.text}")
            points = [tuple(map(float, pair.split(","))) for pair in polygon.get("points").split()]
            left, top = min(x for x, y in points), min(y for x, y in points)
            artwork = ET.parse(symbol).getroot()
            artwork.set("x", str(left + 1))
            artwork.set("y", str(top))
            group.append(artwork)
        embedded += 1
    if embedded != len(symbol_nodes):
        raise ValueError(f"Only embedded {embedded} of {len(symbol_nodes)} gate symbols")
    tree.write(output, encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=ROOT / "input/adder.json")
    parser.add_argument("-o", "--output", type=Path, help="DOT output (default: beside input JSON)")
    parser.add_argument("--fast", action="store_true", help="Use straight edges, fewer layout iterations, and natural input/output ranks")
    parser.add_argument("--basic", action="store_true", help="Use colored boxes without external images for the VS Code DOT preview")
    parser.add_argument("--svg", action="store_true", help="Also render a self-contained SVG beside the DOT file")
    args = parser.parse_args()
    output = args.output if args.output is not None else args.input.with_suffix(".dot")
    try:
        if output.resolve() == args.input.resolve():
            raise ValueError("Output path must differ from input path")
        graph = json.loads(args.input.read_text(encoding="utf-8"))
        svg_output = output.with_suffix(".svg")
        if args.svg and svg_output.resolve() in (args.input.resolve(), output.resolve()):
            raise ValueError("SVG output path must differ from input and DOT paths")
        dot = to_dot(graph, fast=args.fast, basic=args.basic)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(dot, encoding="utf-8")
        if args.svg:
            render_svg(output, svg_output)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, ET.ParseError) as error:
        parser.exit(1, f"graph2dot: {error}\n")
    print(f"Wrote {len(graph['nodes'])} nodes and {len(graph['edges'])} edges to {output}")
    if args.svg:
        print(f"Wrote self-contained circuit preview to {svg_output}")


if __name__ == "__main__":
    main()
