import copy
import json
import unittest
from pathlib import Path
import Cell as cell

from utiles.circuit_metrics import CircuitMetrics


def graph(ops, connections, outputs):
    nodes = [{"op": op, "name": f"n{i}", "input": [], "output": []}
             for i, op in enumerate(ops)]
    edges = []
    for source, target, port in connections:
        edge_id = len(edges)
        edges.append({"source": source, "target": target, "port": port})
        nodes[source]["output"].append(edge_id)
        nodes[target]["input"].append(edge_id)
    return {"nodes": nodes, "edges": edges,
            "outputs": [{"name": name, "edge": edge} for name, edge in outputs]}


class CircuitMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        library_path = Path(__file__).resolve().parents[1] / "input/library.json"
        library = json.loads(library_path.read_text(encoding="utf-8"))
        cls.cells = [cell.Cell(name, record) for name, record in library.items()]

    def setUp(self):
        self.metrics = CircuitMetrics(self.cells, {"nodes": [], "edges": []}, voltage=1.1)

    def test_shared_cell_and_parallel_paths(self):
        circuit = graph(
            ["INPUT", "INV_X1", "BUF_X1", "BUF_X1", "OUTPUT", "OUTPUT"],
            [(0, 1, 0), (1, 2, 0), (1, 3, 0), (2, 4, 0), (3, 5, 0)],
            [("left", 3), ("right", 4)])
        before = copy.deepcopy(circuit)
        result = self.metrics.evaluate(circuit)
        inv, buf = (self.metrics.cells[n] for n in ("INV_X1", "BUF_X1"))
        self.assertAlmostEqual(result["area"]["value"],
                               inv.area + 2 * buf.area)
        power = inv.leakage_power + 2 * buf.leakage_power
        self.assertAlmostEqual(result["leakage_power"]["value"], power)
        self.assertAlmostEqual(result["leakage_current"]["value"], power / 1.1)
        self.assertAlmostEqual(result["delay"]["value"],
                               inv.delay + buf.delay)
        self.assertEqual(result["cell_counts"], {"INV_X1": 1, "BUF_X1": 2})
        self.assertEqual(result["critical_path"], [0, 1, 2, 4])
        self.assertEqual(circuit, before)
        self.assertEqual(self.metrics.area, result["area"]["value"])
        self.assertEqual(self.metrics.delay, result["delay"]["value"])
        self.assertEqual(self.metrics.leakage_power, power)
        self.assertEqual(self.metrics.result, result)

    def test_constructor_stores_results_without_voltage(self):
        circuit = graph(["INPUT", "INV_X1", "OUTPUT"],
                        [(0, 1, 0), (1, 2, 0)], [("out", 1)])
        metrics = CircuitMetrics(self.cells, circuit)
        inv = metrics.cells["INV_X1"]
        self.assertEqual(metrics.area, inv.area)
        self.assertEqual(metrics.leakage_power, inv.leakage_power)
        self.assertEqual(metrics.delay, inv.delay)
        self.assertIsNone(metrics.leakage_current)
        self.assertEqual(metrics.evaluate(), metrics.result)

    def test_repeated_signal_and_generic_gate(self):
        circuit = graph(["INPUT", "AND", "OUTPUT"],
                        [(0, 1, 0), (0, 1, 1), (1, 2, 0)], [("out", 2)])
        result = self.metrics.evaluate(circuit)
        self.assertEqual(result["cell_counts"], {"AND2_X1": 1})
        circuit["nodes"][1].update(op="CELL", cell="AND2_X1")
        circuit["outputs"] = [{"name": "out", "node": 2}]
        self.assertEqual(self.metrics.evaluate(circuit), result)

    def test_invalid_cell_pin_count(self):
        circuit = graph(["INPUT", "INV_X1", "OUTPUT"],
                        [(0, 1, 0), (0, 1, 1), (1, 2, 0)], [("out", 2)])
        with self.assertRaisesRegex(ValueError, "INV_X1.*expected input ports"):
            self.metrics.evaluate(circuit)

    def test_cycle(self):
        circuit = graph(["INV_X1", "INV_X1", "OUTPUT"],
                        [(0, 1, 0), (1, 0, 0), (1, 2, 0)], [("out", 2)])
        with self.assertRaisesRegex(ValueError, "DAG"):
            self.metrics.evaluate(circuit)

    def test_constant_has_zero_cost(self):
        circuit = graph(["CONST_1", "OUTPUT"], [(0, 1, 0)], [("one", 0)])
        result = self.metrics.evaluate(circuit)
        self.assertEqual(result["area"]["value"], 0)
        self.assertEqual(result["leakage_current"]["value"], 0)
        self.assertEqual(result["delay"]["value"], 0)


if __name__ == "__main__":
    unittest.main()
