"""Render one complete balanced circuit with the existing schematic layout."""
import json
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utiles import graph2dot
from utiles.graph2dot import layout, svg

if __name__ == '__main__':
    name = sys.argv[1]
    graph = json.loads((ROOT/f'output/experiments/{name}_balanced.json').read_text(encoding='utf-8'))
    destination = ROOT/'output/plots'
    destination.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    print(f'Layout started: {name}, {len(graph["nodes"])} nodes, {len(graph["edges"])} edges', flush=True)
    original_reduce = graph2dot.reduce_bends
    completed_routes = 0
    def report_route(*args, **kwargs):
        global completed_routes
        result = original_reduce(*args, **kwargs)
        completed_routes += 1
        if completed_routes % 1000 == 0:
            print(f'Routes refined: {completed_routes}/{len(graph["edges"])}; {time.monotonic()-started:.1f}s', flush=True)
        return result
    graph2dot.reduce_bends = report_route
    scene = layout(graph)
    print(f'Layout complete: {time.monotonic()-started:.1f}s; creating SVG', flush=True)
    rendered = svg(scene)
    root = ET.fromstring(rendered)
    ids = {element.get('id') for element in root.iter()}
    assert all(f'node-{i}' in ids for i in range(len(graph['nodes'])))
    assert all(f'wire-{i}' in ids for i in range(len(graph['edges'])))
    path = destination/f'{name}_balanced.svg'
    path.write_text(rendered, encoding='utf-8')
    info = {'source': f'output/experiments/{name}_balanced.json', 'nodes': len(graph['nodes']),
            'edges': len(graph['edges']), 'width': scene['width'], 'height': scene['height'],
            'elapsed_seconds': time.monotonic()-started, 'svg_bytes': path.stat().st_size}
    (destination/f'{name}_balanced.manifest.json').write_text(json.dumps(info, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(info), flush=True)
