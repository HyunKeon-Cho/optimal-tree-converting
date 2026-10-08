import tempfile
import unittest
from pathlib import Path

from utiles.module2json import ROOT, convert


class ModuleConversionTests(unittest.TestCase):
    def convert_text(self, text, suffix):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ("circuit" + suffix)
            path.write_text(text, encoding="utf-8")
            return convert(path)

    def assert_schema(self, graph):
        self.assertEqual(graph["schema_version"], 5)
        nodes, edges = graph["nodes"], graph["edges"]
        rank = {node: i for i, node in enumerate(graph["topological_order"])}
        self.assertEqual(set(rank), set(range(len(nodes))))
        for i, node in enumerate(nodes):
            self.assertTrue({"op", "name", "input", "output"} <= node.keys())
            self.assertEqual(node["input"], [e for e, edge in enumerate(edges) if edge["target"] == i])
            self.assertEqual(node["output"], [e for e, edge in enumerate(edges) if edge["source"] == i])
        for edge in edges:
            self.assertLess(rank[edge["source"]], rank[edge["target"]])
        for pin in graph["outputs"]:
            self.assertEqual(set(pin), {"name", "edge"})
            terminal = nodes[edges[pin["edge"]]["target"]]
            self.assertEqual(terminal["op"], "OUTPUT")
            self.assertEqual(terminal["name"], pin["name"])

    def test_aag_shared_signals_and_constants(self):
        graph = self.convert_text(
            "aag 3 2 0 6 1\n2\n4\n6\n7\n7\n0\n1\n1\n6 4 2\n",
            ".aag")
        self.assert_schema(graph)
        sources = [graph["edges"][p["edge"]]["source"] for p in graph["outputs"]]
        ops = [graph["nodes"][i]["op"] for i in sources]
        self.assertEqual(ops, ["AND", "INV", "INV", "CONST_0", "CONST_1", "CONST_1"])
        self.assertEqual(sources[1], sources[2])
        self.assertEqual(sources[4], sources[5])
        self.assertEqual(graph["stats"]["inv_nodes"], 1)
        for assignment in range(4):
            values = [0] * len(graph["nodes"])
            for i, pin in enumerate(graph["inputs"]):
                values[pin["node"]] = (assignment >> i) & 1
            for node_id in graph["topological_order"]:
                node = graph["nodes"][node_id]
                args = [values[graph["edges"][e]["source"]] for e in node["input"]]
                if node["op"] == "AND": values[node_id] = args[0] & args[1]
                elif node["op"] == "INV": values[node_id] = 1 - args[0]
                elif node["op"].startswith("CONST"): values[node_id] = int(node["value"])
                elif node["op"] == "OUTPUT": values[node_id] = args[0]
            expected = int(assignment == 3)
            self.assertEqual([values[i] for i in sources],
                             [expected, 1 - expected, 1 - expected, 0, 1, 1])

    def test_blif_output_edges(self):
        graph = self.convert_text(
            ".model test\n.inputs a b\n.outputs y one\n"
            ".names a b y\n11 1\n.names one\n1\n.end\n", ".blif")
        self.assert_schema(graph)
        self.assertEqual([p["name"] for p in graph["outputs"]], ["y", "one"])

    def test_default_project_root(self):
        self.assertTrue((ROOT / "reference/module/adder.aig").is_file())


if __name__ == "__main__":
    unittest.main()
