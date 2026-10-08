"""Audit documented metrics, relative links, and complete circuit plots."""
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import Cell
from utiles.circuit_metrics import CircuitMetrics
from utiles.document_results import LABELS, balanced_table, comparison
from utiles.graph2dot import describe

def verify(plots=True):
    results = json.loads((ROOT/'output/experiments/results.json').read_text(encoding='utf-8'))
    for filename, digest in results['source_sha256'].items():
        assert hashlib.sha256((ROOT/filename).read_bytes()).hexdigest() == digest, filename
    cells = [Cell.Cell(name, record) for name, record in json.loads((ROOT/'input/library.json').read_text()).items()]
    library = json.loads((ROOT/'input/library.json').read_text())
    readme = (ROOT/'README.md').read_text(encoding='utf-8')
    assert balanced_table(results['circuits']['log2']) in readme
    pages = [ROOT/'README.md']
    for name, record in results['circuits'].items():
        source = ROOT/f'input/{name}.json'
        assert hashlib.sha256(source.read_bytes()).hexdigest() == record['source_sha256']
        def check(path, expected):
            graph = json.loads(path.read_text(encoding='utf-8'))
            metrics = CircuitMetrics(cells, graph)
            assert sum(metrics.cell_counts.values()) == expected['cells']
            assert metrics.cell_counts == expected['cell_counts']
            for key in ('area', 'leakage_power', 'delay'):
                assert math.isclose(getattr(metrics, key), expected[key], rel_tol=1e-12), (name, key)
            return graph
        check(source, record['original'])
        for setting, run in record['runs'].items():
            graph = check(ROOT/run['graph'], run['metrics'])
            assert (ROOT/f'output/experiments/{name}_{setting}.txt').exists()
            if setting == 'balanced':
                assert graph == json.loads((ROOT/f'output/{name}_opt.json').read_text(encoding='utf-8'))
        page = ROOT/f'doc/{name}.md'
        pages.append(page)
        text = page.read_text(encoding='utf-8')
        assert balanced_table(record) in text and comparison(record) in text
        assert balanced_table(record) in readme
        original_counts = record['original']['cell_counts']
        counts = record['runs']['balanced']['metrics']['cell_counts']
        for cell in set(original_counts) | set(counts):
            assert f'| {cell} | {original_counts.get(cell) or "-"} | {counts.get(cell) or "-"} |' in text
        for heading in ('Circuit outline', 'Result table (balanced)', 'Cell utilization table', 'Comparison by weight setting'):
            assert f'## {heading}' in text
        assert f'![{LABELS[name]} balanced mapped circuit](../output/plots/{name}_balanced.svg)' in text
        if plots:
            graph = json.loads((ROOT/record['runs']['balanced']['graph']).read_text(encoding='utf-8'))
            svg = ROOT/f'output/plots/{name}_balanced.svg'
            root = ET.parse(svg).getroot()
            elements = {element.get('id'): element for element in root.iter() if element.get('id')}
            ids = set(elements)
            assert all(f'node-{i}' in ids for i in range(len(graph['nodes'])))
            assert all(f'wire-{i}' in ids for i in range(len(graph['edges'])))
            title_tag = '{http://www.w3.org/2000/svg}title'
            for i, node in enumerate(graph['nodes']):
                label = describe(node, library)['label']
                assert elements[f'node-{i}'].find(title_tag).text == f'Node {i}: {label}'
            for i, edge in enumerate(graph['edges']):
                info = describe(graph['nodes'][edge['target']], library)
                pin = info['pins'][edge['port']] if info['pins'] else str(edge['port'])
                assert elements[f'wire-{i}'].find(title_tag).text == f'Node {edge["source"]} → Node {edge["target"]}, pin {pin}'
                assert elements[f'wire-{i}'].get('d'), (name, i)
            assert f'../output/plots/{name}_balanced.svg' in text
            assert 'pending sequential' not in text
        print(f'Verified {name}: four runs, metrics, tables' + (', full circuit SVG' if plots else ''), flush=True)
    for page in pages:
        for target in re.findall(r'\]\(([^)]+)\)', page.read_text(encoding='utf-8')):
            assert '\\' not in target, (str(page), target)
            if '://' in target or target.startswith('#'):
                continue
            deferred_plots = {f'../output/plots/{name}_balanced.svg' for name in results['circuits']}
            if not plots and target in deferred_plots:
                continue
            assert (page.parent/target.split('#')[0]).exists(), (str(page), target)
    result_section = readme.split('# RESULT\n', 1)[1].split('# File Structure', 1)[0]
    assert not any(label in result_section for label in ('Area priority', 'Leakage priority', 'Delay priority'))
    print('All required documentation links and source hashes verified.' +
          (' Plot files deferred.' if not plots else ''), flush=True)

if __name__ == '__main__':
    verify('--no-plots' not in sys.argv)
