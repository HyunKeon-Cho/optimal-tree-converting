"""Evaluate a circuit DAG using the repository's constant Liberty cost model."""

import math
from collections import Counter, deque
import Cell as cell


class CircuitMetrics:
    """Sum instance area/leakage and compute maximum output arrival time.

    Generic gates use X1 cells by default; gate_cells can override these choices.
    Delay uses lib2json's 20 ps slew, 4x mean input capacitance model, without
    actual fanout load or wire delay. Results are calculated at construction.
    Leakage current is only available when voltage is explicitly supplied.
    """

    DEFAULT_GATE_CELLS = {
        "AND": "AND2_X1", "NAND": "NAND2_X1",
        "OR": "OR2_X1", "NOR": "NOR2_X1",
        "XOR": "XOR2_X1", "XNOR": "XNOR2_X1",
        "INV": "INV_X1", "NOT": "INV_X1", "BUF": "BUF_X1",
    }
    TERMINALS = {"INPUT", "OUTPUT", "CONST", "CONST_0", "CONST_1"}

    def __init__(self, cells, graph, *, gate_cells=None, voltage=None):
        self.cells = {}
        for item in cells:
            if not isinstance(item, cell.Cell):
                raise TypeError("cells must contain s0_defineCells.Cell instances")
            if item.name in self.cells:
                raise ValueError(f"Duplicate library cell: {item.name}")
            for value in (item.area, item.leakage_power, item.delay):
                if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError(f"Invalid cell cost: {item.name}")
            self.cells[item.name] = item
        self.gate_cells = {**self.DEFAULT_GATE_CELLS, **(gate_cells or {})}
        if voltage is not None and (not isinstance(voltage, (int, float))
                                    or not math.isfinite(voltage) or voltage <= 0):
            raise ValueError("voltage must be positive and finite")
        self.voltage = float(voltage) if voltage is not None else None
        self.graph = graph
        self.evaluate()

    def evaluate(self, circuit=None):
        """Recalculate a graph dict and store numeric results on this instance.

        Every cell node is charged once, including instances unused by outputs.
        INPUT/OUTPUT/CONST nodes have zero cell cost. These abstract constants
        exclude physical tie cells. Input arrival times are zero. No files are
        written and the caller's graph is not changed.
        """
        circuit = self.graph if circuit is None else circuit
        if not isinstance(circuit, dict):
            raise TypeError("graph must be a toy.json-style dict")
        nodes, edges = circuit["nodes"], circuit["edges"]
        incoming, outgoing = [[] for _ in nodes], [[] for _ in nodes]

        def node_index(value):
            if type(value) is not int or not 0 <= value < len(nodes):
                raise ValueError(f"Invalid node index: {value}")
            return value

        for edge_id, edge in enumerate(edges):
            source, target = node_index(edge["source"]), node_index(edge["target"])
            if type(edge["port"]) is not int or edge["port"] < 0:
                raise ValueError(f"Invalid input port at edge {edge_id}")
            incoming[target].append(edge_id)
            outgoing[source].append(edge_id)

        area = power = 0.0
        delays, cell_names = [], []
        for node_id, node in enumerate(nodes):
            op = node["op"]
            name = None
            if op not in self.TERMINALS:
                name = (node.get("cell", node.get("cell_name", node.get("name")))
                        if op == "CELL" else op if op in self.cells
                        else self.gate_cells.get(op))
                if name not in self.cells:
                    raise ValueError(f"Node {node_id}: unknown library cell/gate {op!r}")
                selected_cell = self.cells[name]
                expected = selected_cell.inputs_len
                area += selected_cell.area
                power += selected_cell.leakage_power
                delays.append(selected_cell.delay)
            else:
                expected = 1 if op == "OUTPUT" else 0
                delays.append(0.0)
            cell_names.append(name)
            ports = sorted(edges[e]["port"] for e in incoming[node_id])
            if ports != list(range(expected)):
                raise ValueError(f"Node {node_id} ({name or op}): expected input ports "
                                 f"0..{expected - 1}, got {ports}")
            if op == "OUTPUT" and outgoing[node_id]:
                raise ValueError(f"Output node {node_id} cannot drive another node")
            for key, actual in (("input", incoming[node_id]), ("output", outgoing[node_id])):
                if key in node and sorted(node[key]) != sorted(actual):
                    raise ValueError(f"Node {node_id}: inconsistent {key} edge indices")

        degree = [len(e) for e in incoming]
        ready = deque(i for i, d in enumerate(degree) if d == 0)
        arrival, predecessor = [0.0] * len(nodes), [None] * len(nodes)
        order = []
        while ready:
            node_id = ready.popleft()
            order.append(node_id)
            if incoming[node_id]:
                parent = max((edges[e]["source"] for e in incoming[node_id]),
                             key=lambda i: arrival[i])
                arrival[node_id] = arrival[parent]
                predecessor[node_id] = parent
            arrival[node_id] += delays[node_id]
            for edge_id in outgoing[node_id]:
                target = edges[edge_id]["target"]
                degree[target] -= 1
                if degree[target] == 0:
                    ready.append(target)
        if len(order) != len(nodes):
            raise ValueError("Circuit must be a DAG")

        outputs = []
        for pin in circuit.get("outputs", []):
            if "edge" in pin:
                edge_id = pin["edge"]
                if type(edge_id) is not int or not 0 <= edge_id < len(edges):
                    raise ValueError(f"Invalid output edge: {edge_id}")
                node_id = node_index(edges[edge_id]["target"])
            else:
                node_id = node_index(pin["node"])
            if nodes[node_id]["op"] != "OUTPUT":
                raise ValueError(f"Output port {pin['name']!r} must reference an OUTPUT terminal")
            outputs.append({"name": pin["name"], "node": node_id,
                            "delay": {"value": arrival[node_id], "unit": "ns"}})
        if "outputs" not in circuit:
            outputs = [{"name": node.get("name", str(i)), "node": i,
                        "delay": {"value": arrival[i], "unit": "ns"}}
                       for i, node in enumerate(nodes) if node["op"] == "OUTPUT"]
        critical = max(outputs, key=lambda p: p["delay"]["value"], default=None)
        path = []
        cursor = critical["node"] if critical is not None else None
        while cursor is not None:
            path.append(cursor)
            cursor = predecessor[cursor]
        self.graph = circuit
        self.area = area
        self.leakage_power = power
        self.leakage_current = power / self.voltage if self.voltage is not None else None
        self.delay = critical["delay"]["value"] if critical else 0.0
        self.cell_counts = dict(Counter(n for n in cell_names if n is not None))
        self.output_delays = outputs
        self.critical_path = list(reversed(path))
        self.arrival_times = arrival
        self.result = {
            "area": {"value": area, "unit": "um^2"},
            "leakage_power": {"value": power, "unit": "nW"},
            "leakage_current": {"value": self.leakage_current, "unit": "nA"},
            "delay": {"value": self.delay, "unit": "ns"},
            "voltage": {"value": self.voltage, "unit": "V"},
            "cell_counts": self.cell_counts,
            "output_delays": self.output_delays,
            "critical_path": self.critical_path,
        }
        return self.result
