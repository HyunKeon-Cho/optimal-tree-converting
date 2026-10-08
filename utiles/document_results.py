"""Build result documentation from collected main.main runs."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LABELS = {'toy': 'Toy example', 'adder': 'Adder (128-bit)', 'log2': 'Log2 (32-bit)'}
METRICS = [('cells', 'Cells', 0), ('area', 'Area (μm²)', 3),
           ('leakage_power', 'Representative leakage power (nW)', 3), ('delay', 'Delay (ns)', 6)]
NAMES = {'area': 'Area priority', 'leakage': 'Leakage priority',
         'delay': 'Delay priority', 'balanced': 'Balanced'}

def number(value, precision):
    return f'{value:.{precision}f}'

def balanced_table(record):
    original, mapped = record['original'], record['runs']['balanced']['metrics']
    lines = ['| Metric | Original | Balanced | Change |', '| --- | ---: | ---: | ---: |']
    for key, label, precision in METRICS:
        change = f'{(mapped[key]/original[key]-1)*100:+.2f}%' if original[key] else 'N/A'
        lines.append(f'| {label} | {number(original[key], precision)} | {number(mapped[key], precision)} | {change} |')
    return '\n'.join(lines)

def comparison(record):
    runs = list(record['runs'].items())
    lines = ['| Metric | Original | ' + ' | '.join(NAMES[s] for s, _ in runs) + ' |',
             '| --- | ---: | ' + ' | '.join('---:' for _ in runs) + ' |']
    lines.append('| Weights (A, P, D) | — | ' + ' | '.join(
        ', '.join(str(w) for w in run['weights']) for _, run in runs) + ' |')
    for key, label, precision in METRICS:
        original = record['original'][key]
        values = []
        for _, run in runs:
            value = run['metrics'][key]
            change = f'{(value/original-1)*100:+.2f}%' if original else 'N/A'
            values.append(f'{number(value, precision)}<br>({change})')
        lines.append(f'| {label} | {number(original, precision)} | ' + ' | '.join(values) + ' |')
    return '\n'.join(lines)

def build():
    results = json.loads((ROOT/'output/experiments/results.json').read_text(encoding='utf-8'))
    assert len(results['circuits']) == 3
    pages = ROOT/'doc'
    pages.mkdir(parents=True, exist_ok=True)
    for name, record in results['circuits'].items():
        assert list(record['runs']) == ['area', 'leakage', 'delay', 'balanced']
        outline = record['outline']
        source = ('AI-generated toy circuit covering basic gates, XOR/XNOR, MUX, AOI/OAI, wide AND functions, shared paths, constants, and inversion.'
                  if name == 'toy' else f'EPFL combinational benchmark, converted from `reference/module/{name}.aig` to an AND/INV DAG.')
        counts = record['runs']['balanced']['metrics']['cell_counts']
        original_counts = record['original']['cell_counts']
        total = sum(counts.values())
        utilization = ['| Library cell | Input | Opt (balanced) |', '| --- | ---: | ---: |']
        for cell in sorted(set(original_counts) | set(counts), key=lambda cell: (-counts.get(cell, 0), cell)):
            utilization.append(f'| {cell} | {original_counts.get(cell) or "-"} | {counts.get(cell) or "-"} |')
        utilization.append(f'| **Total** | **{sum(original_counts.values())}** | **{total}** |')
        text = f'# {LABELS[name]} results\n\n'
        text += f'## Circuit outline\n\n{source}\n\n'
        text += '| Property | Original circuit |\n| --- | ---: |\n' + '\n'.join(
            f'| {key.title()} | {value} |' for key, value in outline.items())
        text += f'\n| Logic cells (AND/INV) | {record["original"]["cells"]} |\n\n'
        text += f'[Input DAG](../input/{name}.json) · [Balanced mapped DAG](../output/experiments/{name}_balanced.json)\n\n'
        text += '## Result table (balanced)\n\nWeights `(wA, wP, wD) = (0.34, 0.33, 0.33)`.\n\n' + balanced_table(record)
        text += '\n\n## Cell utilization table\n\n' + '\n'.join(utilization)
        text += '\n\n## Comparison by weight setting\n\n' + comparison(record) + '\n\n'
        text += '## Balanced circuit plot\n\n'
        text += f'![{LABELS[name]} balanced mapped circuit](../output/plots/{name}_balanced.svg)\n\n[Open full-size SVG](../output/plots/{name}_balanced.svg)\n'
        (pages/f'{name}.md').write_text(text, encoding='utf-8')
    readme = ROOT/'README.md'
    text = readme.read_text(encoding='utf-8')
    top = '### Result (Log2 32-bit, balanced)\n\n' + balanced_table(results['circuits']['log2'])
    top += '\n\nWeights `(wA, wP, wD) = (0.34, 0.33, 0.33)`. [Full Log2 results](doc/log2.md).\n\n'
    text = re.sub(r'### Result .*?(?=# Problem)', lambda _: top, text, flags=re.S)
    section = '# RESULT\n\nAll three circuits use the balanced weights `(wA, wP, wD) = (0.34, 0.33, 0.33)`.\n'
    section += '\n'
    for name, record in results['circuits'].items():
        section += f'## [{LABELS[name]}](doc/{name}.md)\n\n' + balanced_table(record) + '\n\n'
    text = re.sub(r'# (?:result|RESULT)\n.*?(?=# File Structure)', lambda _: section, text, flags=re.S)
    text = text.replace('# ToDo\n- update result table', '# ToDo\n- fix candidate normalization in `getOptCircuit()`')
    readme.write_text(text, encoding='utf-8')

if __name__ == '__main__':
    build()
