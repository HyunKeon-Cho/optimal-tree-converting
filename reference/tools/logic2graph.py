"""Read combinational AIGER (.aig/.aag) or flat BLIF; write a JSON graph.

Usage: python reference/tools/logic2graph.py [input.aig] [-o output.json]
The default output is input/<source stem>.json in the project root.
Shared nodes retain one ID with all incoming references in a single DAG.
INPUT, CONST, AND, INV and OUTPUT are explicit nodes joined by ordinary edges.
Nodes and edges are lists identified by index; nodes list input/output edge indices.
"""

import argparse
import json
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read_aiger(path):
    with Path(path).open('rb') as stream:
        header = stream.readline().decode('ascii').split()
        if len(header) != 6 or header[0] not in ('aig', 'aag'):
            raise ValueError("Expected basic AIGER header: aig/aag M I L O A")
        maximum, inputs_count, latches, outputs_count, and_count = map(int, header[1:])
        if min(maximum, inputs_count, latches, outputs_count, and_count) < 0:
            raise ValueError("Negative AIGER count")
        if latches:
            raise ValueError("Sequential AIGER is unsupported; latch count must be zero")
        inputs = list(range(2, 2 * inputs_count + 1, 2)) if header[0] == 'aig' else [int(stream.readline()) for _ in range(inputs_count)]
        outputs = [int(stream.readline()) for _ in range(outputs_count)]
        nodes = {}
        if header[0] == 'aig':
            if maximum != inputs_count + and_count:
                raise ValueError("Invalid binary AIGER maximum variable index")

            def delta():
                value, shift = 0, 0
                while True:
                    byte = stream.read(1)
                    if not byte:
                        raise ValueError("Truncated binary AIGER delta")
                    value |= (byte[0] & 127) << shift
                    if byte[0] < 128:
                        return value
                    shift += 7
                    if shift > 63:
                        raise ValueError("Oversized AIGER delta")

            for variable in range(inputs_count + 1, maximum + 1):
                lhs = variable * 2
                right0 = lhs - delta()
                right1 = right0 - delta()
                if not 0 <= right1 <= right0 < lhs:
                    raise ValueError("Invalid binary AND operands")
                nodes[variable] = [right0, right1]
        else:
            for _ in range(and_count):
                line = stream.readline().split()
                if len(line) != 3:
                    raise ValueError("Malformed ASCII AND record")
                lhs, right0, right1 = map(int, line)
                if lhs <= 0 or lhs % 2 or lhs // 2 in nodes:
                    raise ValueError("Invalid or duplicate AND definition")
                nodes[lhs // 2] = [right0, right1]
        input_names = {i: f'i{i}' for i in range(inputs_count)}
        output_names = {i: f'o{i}' for i in range(outputs_count)}
        for raw in stream:
            line = raw.decode('utf-8', errors='replace').rstrip('\r\n')
            if line == 'c':
                break
            if line and line[0] in ('i', 'o'):
                key, separator, name = line.partition(' ')
                if separator and key[1:].isdigit():
                    index = int(key[1:])
                    names = input_names if key[0] == 'i' else output_names
                    if index not in names:
                        raise ValueError("Symbol index outside header counts")
                    names[index] = name
    if any(v < 0 or v > 2 * maximum + 1 for v in inputs + outputs + [v for pair in nodes.values() for v in pair]):
        raise ValueError("Literal outside header maximum")
    if any(v == 0 or v % 2 for v in inputs) or len(set(inputs)) != len(inputs):
        raise ValueError("Invalid or duplicate input literal")
    if any(node > maximum for node in nodes):
        raise ValueError("AND definition outside header maximum")
    return inputs, outputs, nodes, [input_names[i] for i in range(inputs_count)], [output_names[i] for i in range(outputs_count)]


def topological(nodes, input_literals):
    input_ids = {v // 2 for v in input_literals}
    if input_ids & nodes.keys():
        raise ValueError("Input and AND definitions overlap")
    defined = input_ids | nodes.keys() | {0}
    degree, consumers = {}, {}
    for node, operands in nodes.items():
        dependencies = {v // 2 for v in operands if v // 2 in nodes}
        for literal in operands:
            if literal < 0 or literal // 2 not in defined:
                raise ValueError(f"Undefined literal {literal} at node {node}")
        degree[node] = len(dependencies)
        for dependency in dependencies:
            consumers.setdefault(dependency, []).append(node)
    ready = deque(n for n in nodes if degree[n] == 0)
    order = []
    while ready:
        node = ready.popleft()
        order.append(node)
        for consumer in consumers.get(node, []):
            degree[consumer] -= 1
            if degree[consumer] == 0:
                ready.append(consumer)
    if len(order) != len(nodes):
        raise ValueError("Cycle in logic graph")
    return order


def read_blif(path):
    text = Path(path).read_text(encoding='utf-8-sig').replace('\\\n', ' ')
    lines = [line.split('#', 1)[0].strip() for line in text.splitlines()]
    input_names, output_names, definitions = [], [], {}
    current = None
    for line in lines:
        if not line:
            continue
        fields = line.split()
        if line.startswith('.'):
            current = None
            if fields[0] == '.inputs':
                input_names.extend(fields[1:])
            elif fields[0] == '.outputs':
                output_names.extend(fields[1:])
            elif fields[0] == '.names':
                if len(fields) < 2 or fields[-1] in definitions:
                    raise ValueError("Missing or duplicate BLIF node name")
                current = (fields[1:-1], [])
                definitions[fields[-1]] = current
            elif fields[0] not in ('.model', '.end'):
                raise ValueError(f"Unsupported BLIF directive: {fields[0]} (flat combinational .names only)")
        elif current is None:
            raise ValueError("Truth-table row outside .names block")
        else:
            fanins, rows = current
            if not fanins and len(fields) == 1:
                cube, value = '', fields[0]
            elif len(fields) == 2:
                cube, value = fields
            else:
                raise ValueError("Malformed BLIF truth-table row")
            if len(cube) != len(fanins) or any(c not in '01-' for c in cube) or value not in ('0', '1'):
                raise ValueError("Invalid BLIF truth-table cube")
            rows.append((cube, value))
    if len(set(input_names)) != len(input_names) or set(input_names) & definitions.keys():
        raise ValueError("Duplicate BLIF input or overlapping definitions")
    signals = {name: 2 * (i + 1) for i, name in enumerate(input_names)}
    nodes, unique, next_id = {}, {}, len(input_names) + 1

    def conjunction(left, right):
        nonlocal next_id
        if left == 0 or right == 0 or left == (right ^ 1):
            return 0
        if left == 1:
            return right
        if right == 1 or left == right:
            return left
        key = tuple(sorted((left, right), reverse=True))
        if key not in unique:
            unique[key] = next_id * 2
            nodes[next_id] = list(key)
            next_id += 1
        return unique[key]

    dependencies, consumers = {}, {}
    for name, (fanins, _) in definitions.items():
        if any(n not in signals and n not in definitions for n in fanins):
            raise ValueError(f"Undefined BLIF fanin at {name}")
        dependencies[name] = len(set(fanins) & definitions.keys())
        for dependency in set(fanins) & definitions.keys():
            consumers.setdefault(dependency, []).append(name)
    ready = deque(n for n, degree in dependencies.items() if degree == 0)
    while ready:
        name = ready.popleft()
        fanins, rows = definitions[name]
        values = {v for _, v in rows}
        if len(values) > 1:
            raise ValueError(f"Mixed on/off-set BLIF rows at {name} are unsupported")
        result = 0
        for cube, _ in rows:
            term = 1
            for signal, bit in zip(fanins, cube):
                if bit != '-':
                    term = conjunction(term, signals[signal] ^ (bit == '0'))
            result = conjunction(result ^ 1, term ^ 1) ^ 1
        signals[name] = result ^ (values == {'0'})
        for consumer in consumers.get(name, []):
            dependencies[consumer] -= 1
            if dependencies[consumer] == 0:
                ready.append(consumer)
    if len(signals) != len(input_names) + len(definitions):
        raise ValueError("Cycle in BLIF circuit")
    if any(name not in signals for name in output_names):
        raise ValueError("Undefined BLIF output")
    return [signals[n] for n in input_names], [signals[n] for n in output_names], nodes, input_names, output_names


def convert(path):
    reader = read_blif if Path(path).suffix.lower() == '.blif' else read_aiger
    inputs, outputs, nodes, input_names, output_names = reader(path)
    order = topological(nodes, inputs)
    defined = {0} | {v // 2 for v in inputs} | nodes.keys()
    if any(v < 0 or v // 2 not in defined for v in outputs):
        raise ValueError("Undefined output literal")
    # Drop gates that do not influence any output.
    reachable, pending = set(), [v // 2 for v in outputs]
    while pending:
        node = pending.pop()
        if node in nodes and node not in reachable:
            reachable.add(node)
            pending.extend(v // 2 for v in nodes[node])
    nodes = {n: nodes[n] for n in order if n in reachable}
    order = list(nodes)

    graph_nodes = {0: {"op": "CONST", "value": False}}
    graph_nodes.update({v // 2: {"op": "INPUT", "name": name} for name, v in zip(input_names, inputs)})
    graph_nodes.update({n: {"op": "AND"} for n in nodes})
    next_id = max(graph_nodes) + 1
    edges, inverters = [], {}
    graph_order = [0] + [v // 2 for v in inputs]

    def signal(literal):
        nonlocal next_id
        node = literal // 2
        if not literal & 1:
            return node
        # One explicit inverter per source signal; all consumers share it.
        if node not in inverters:
            inverter = next_id
            next_id += 1
            inverters[node] = inverter
            graph_nodes[inverter] = {"op": "INV"}
            edges.append({"source": node, "target": inverter, "port": 0})
            graph_order.append(inverter)
        return inverters[node]

    for node in order:
        for port, literal in enumerate(nodes[node]):
            edges.append({"source": signal(literal), "target": node, "port": port})
        graph_order.append(node)
    graph_outputs = []
    for name, literal in zip(output_names, outputs):
        source = signal(literal)
        output_id = next_id
        next_id += 1
        graph_nodes[output_id] = {"op": "OUTPUT", "name": name}
        edges.append({"source": source, "target": output_id, "port": 0})
        graph_order.append(output_id)
        graph_outputs.append({"name": name, "node": output_id})

    node_indices = {node_id: index for index, node_id in enumerate(graph_nodes)}
    graph_nodes = list(graph_nodes.values())
    for edge in edges:
        edge['source'] = node_indices[edge['source']]
        edge['target'] = node_indices[edge['target']]
    for record in graph_nodes:
        record['input'] = []
        record['output'] = []
    for edge_id, edge in enumerate(edges):
        graph_nodes[edge['source']]['output'].append(edge_id)
        graph_nodes[edge['target']]['input'].append(edge_id)

    graph = {
        "schema_version": 4,
        "source": Path(path).name,
        "inputs": [{"name": name, "node": node_indices[v // 2]} for name, v in zip(input_names, inputs)],
        "outputs": [{"name": pin['name'], "node": node_indices[pin['node']]} for pin in graph_outputs],
        "nodes": graph_nodes,
        "edges": edges,
        "topological_order": [node_indices[node] for node in graph_order],
        "stats": {
            "inputs": len(inputs), "outputs": len(outputs), "and_nodes": len(nodes),
            "inv_nodes": len(inverters), "nodes": len(graph_nodes), "edges": len(edges),
        },
    }
    return graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', type=Path, default=ROOT / 'reference/module/adder.aig')
    parser.add_argument('-o', '--output', type=Path, help='Output JSON path (default: input/<source stem>.json)')
    args = parser.parse_args()
    if args.output is None:
        args.output = ROOT / 'input' / (args.input.stem + '.json')
    try:
        graph = convert(args.input)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('w', encoding='utf-8') as stream:
            json.dump(graph, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    except (OSError, ValueError, UnicodeError, IndexError) as error:
        parser.exit(1, f"logic2graph: {error}\n")
    print(f"Wrote {graph['stats']} to {args.output}")


if __name__ == '__main__':
    main()
