"""Reconstruct a circuit graph from selected dp cells."""

from collections import Counter


def makeGraph(dp, module):
    """Reconstruct the selected cells from dp, starting at output edges.

    dp[node] is [truth_table, boundary_node_ids, cell_name, cost,
                 [area, leakage_power, delay]].
    The legacy four-field form is also accepted. Only the selected cell name
    and boundary nodes are needed to reconstruct connectivity; cost fields
    are not copied into the toy.json-style output graph.
    Boundary order determines the selected cell's input pin order.
    """

    result = {
        "schema_version": 5,
        "source": module.get("source", "circuit") + "_opt",
        "inputs": [], "outputs": [], "nodes": [], "edges": [],
        "topological_order": [],
    }
    selected = {}
    visiting = set()

    def add_node(record):
        node_id = len(result["nodes"])
        result["nodes"].append({**record, "input": [], "output": []})
        result["topological_order"].append(node_id)
        return node_id

    def connect(source, target, port):
        edge_id = len(result["edges"])
        result["edges"].append({"source": source, "target": target, "port": port})
        result["nodes"][source]["output"].append(edge_id)
        result["nodes"][target]["input"].append(edge_id)
        return edge_id

    def select(node_id):
        if node_id in selected:
            return selected[node_id]
        if node_id in visiting:
            raise ValueError(f"Cycle in selected dp boundaries at node {node_id}")
        if not isinstance(node_id, int) or not 0 <= node_id < len(module["nodes"]):
            raise ValueError(f"Invalid dp boundary node: {node_id}")
        candidate = dp[node_id]
        if not isinstance(candidate, (list, tuple)) or len(candidate) not in (4, 5):
            raise ValueError(f"No selected dp cell for node {node_id}: {candidate}")
        _, boundaries, cell_name = candidate[:3]
        visiting.add(node_id)
        sources = [select(boundary) for boundary in boundaries]
        original = module["nodes"][node_id]
        if cell_name in ("INPUT", "CONST", "CONST_0", "CONST_1"):
            if boundaries:
                raise ValueError(f"Terminal node {node_id} has dp input boundaries")
            record = {k: v for k, v in original.items() if k not in ("input", "output")}
            record["op"] = cell_name
            if cell_name in ("CONST_0", "CONST_1"):
                record["value"] = cell_name == "CONST_1"
        else:
            record = {"op": cell_name, "name": original.get("name", f"n{node_id}")}
        new_id = add_node(record)
        for port, source in enumerate(sources):
            connect(source, new_id, port)
        selected[node_id] = new_id
        visiting.remove(node_id)
        return new_id

    # Keep the declared input interface, including unused inputs.
    for pin in module.get("inputs", []):
        node_id = pin["node"]
        if node_id not in selected:
            original = module["nodes"][node_id]
            selected[node_id] = add_node({k: v for k, v in original.items()
                                          if k not in ("input", "output")})
        result["inputs"].append({"name": pin["name"], "node": selected[node_id]})

    for pin in module["outputs"]:
        if "edge" in pin:
            source = module["edges"][pin["edge"]]["source"]
        else:
            terminal = module["nodes"][pin["node"]]
            source = module["edges"][terminal["input"][0]]["source"]
        source = select(source)
        target = add_node({"op": "OUTPUT", "name": pin["name"]})
        edge_id = connect(source, target, 0)
        result["outputs"].append({"name": pin["name"], "edge": edge_id})

    terminals = {"INPUT", "OUTPUT", "CONST", "CONST_0", "CONST_1"}
    cell_counts = dict(Counter(node["op"] for node in result["nodes"]
                               if node["op"] not in terminals))
    result["stats"] = {
        "inputs": len(result["inputs"]), "outputs": len(result["outputs"]),
        "cells": sum(cell_counts.values()), "cell_counts": cell_counts,
        "nodes": len(result["nodes"]), "edges": len(result["edges"]),
    }
    return result

