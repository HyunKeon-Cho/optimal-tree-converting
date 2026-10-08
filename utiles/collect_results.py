"""Run main.main without plots and preserve every experiment's evidence."""
import contextlib
import gc
import hashlib
import io
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main as mapper
from utiles.circuit_metrics import CircuitMetrics

SETTINGS = [('area', (0.8, 0.1, 0.1)), ('leakage', (0.1, 0.8, 0.1)),
            ('delay', (0.1, 0.1, 0.8)), ('balanced', (0.34, 0.33, 0.33))]

def collect():
    sys.setrecursionlimit(20000)
    destination = ROOT / 'output/experiments'
    destination.mkdir(parents=True, exist_ok=True)
    results = {'settings': dict(SETTINGS), 'source_sha256': {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [ROOT/'main.py', ROOT/'Cell.py', ROOT/'input/library.json']}, 'circuits': {}}
    for name in ('toy', 'adder', 'log2'):
        source = ROOT / f'input/{name}.json'
        graph = json.loads(source.read_text(encoding='utf-8'))
        record = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                  'outline': {'inputs': len(graph['inputs']), 'outputs': len(graph['outputs']),
                              'nodes': len(graph['nodes']), 'edges': len(graph['edges'])},
                  'runs': {}}
        results['circuits'][name] = record
        for setting, weights in SETTINGS:
            print(f'Start {name}/{setting}', flush=True)
            mapper.cell.Cell.library.clear()
            mapper.MODULE_NAME = name
            mapper.W_AREA, mapper.W_LEAKAGECUEENT, mapper.W_DELAY = weights
            started = time.monotonic()
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                mapper.main()
            (destination / f'{name}_{setting}.txt').write_text(capture.getvalue(), encoding='utf-8')
            path = destination / f'{name}_{setting}.json'
            path.write_text(json.dumps(mapper.graph, indent=2) + '\n', encoding='utf-8')
            before = CircuitMetrics(mapper.lib, mapper.module)
            after = CircuitMetrics(mapper.lib, mapper.graph)
            def metrics(m):
                return {'cells': sum(m.cell_counts.values()), 'area': m.area,
                        'leakage_power': m.leakage_power, 'delay': m.delay,
                        'cell_counts': m.cell_counts}
            record['original'] = metrics(before)
            record['runs'][setting] = {'weights': weights, 'metrics': metrics(after),
                                       'elapsed_seconds': time.monotonic()-started,
                                       'graph': path.relative_to(ROOT).as_posix()}
            (destination/'results.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
            print(capture.getvalue(), flush=True)
            mapper.dp = []
            gc.collect()
    return results

if __name__ == '__main__':
    collect()
