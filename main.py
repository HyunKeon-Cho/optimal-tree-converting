import json
from pathlib import Path
import Cell as cell
from utiles.graph2dot import render_schematic, export_schematic
from utiles.makeGraph import makeGraph
from utiles.circuit_metrics import CircuitMetrics

LOGIC_GATE = {
    "AND": 0b1000,
    "INV": 0b01,
    "INPUT": 0b10,
    "CONST_0": 0b0,
    "CONST_1": 0b1
}

"""
def mergeAND(a, b):
    table = 0
    for i in range(2 ** len(a[1])):
        table += (b[0] if ((a[0] >> i) & 0b1) else 0) << ((2 ** len(b[1])) * i)

    port = 
    
    cell = [table, b[1] + a[1], "AND"]
    return cell
"""

def mergeAND(a, b): # AI
    boundaries = list(dict.fromkeys(b[1] + a[1]))
    positions = {node: i for i, node in enumerate(boundaries)}

    def value(candidate, assignment):
        local_assignment = 0

        for i, node in enumerate(candidate[1]):
            bit = (assignment >> positions[node]) & 1
            local_assignment |= bit << i

        return (candidate[0] >> local_assignment) & 1

    table = 0

    for assignment in range(1 << len(boundaries)):
        result = value(a, assignment) & value(b, assignment)
        table |= result << assignment

    return [table, boundaries, "AND"]

def mergeINV(a):
    cell = [~(a[0]) & ((1 << (1 << len(a[1]))) - 1), a[1], "INV"]
    return cell

def getCoat(area, leakage, delay):
    global W_AREA, W_LEAKAGECUEENT, W_DELAY
    return area*W_AREA + leakage*W_LEAKAGECUEENT + delay*W_DELAY

def getOptCircuit(circuits):
    # normalization
    max_cost = max([[c[4][i] for c in circuits] for i in range(3)])
    min_cost = min([[c[4][i] for c in circuits] for i in range(3)])
    cost = [getCoat(*[(c[4][i]-min_cost[i])/max_cost[i] for i in range(3)]) for c in circuits]
    i = cost.index(min(cost))

    return circuits[i]

def dfs(wire):
    global dp, dp_cost, lib, module, ahoCorasick
    
    # get sub tree
    op = module["edges"][wire]['source']
    port = module["nodes"][op]
    subTree = [] # { "table", "output" }
    
    if (dp[op] != -1):
        return [[LOGIC_GATE["INPUT"], [op], "INPUT"]] # AI

    if port["op"] in ("INPUT", "CONST_0", "CONST_1"): # AI
        table = LOGIC_GATE[port["op"]]
        dp[op] = [table, [], port["op"], 0, [0, 0, 0]]

        if port["op"] == "INPUT":
            return [[LOGIC_GATE["INPUT"], [op], "INPUT"]]

        return [[table, [], port["op"]]]
    

    for i in port["input"]:
        sub = dfs(i)
        subTree.append(sub)

    # marge
    tree = [[LOGIC_GATE[port["op"]], [module["edges"][i]["source"] for i in port["input"]], port["op"]]]

    if (len(port["output"]) > 1):
        pass
    
    elif (port["op"] == "AND"): # Case : AND
        A, B = subTree[0], subTree[1]
        for a in A:
            for b in B:
                if (len(set(a[1]) | set(b[1])) > 6): continue
                tree.append(mergeAND(a, b))
        for b in B:
            for a in A: 
                if (len(set(a[1]) | set(b[1])) > 6): continue
                tree.append(mergeAND(b, a))
    elif (port["op"] == "INV"): # Case : INV
        A = subTree[0]
        for a in A:
            tree.append(mergeINV(a))
    else:
        raise Exception(f"case break. {port["op"]}")

    # cal cost
    optCell = None
    cost = []
    for t in tree:
        for preset in lib:
            if (len(t[1]) != preset.inputs_len or t[0] != preset.table[0]): continue

            cost.append(
                [
                    preset.table[0], t[1], preset.name, cost,
                    [
                        preset.area_norm + sum(dp[i][4][0] for i in t[1]), 
                        preset.leakage_power_norm + sum(dp[i][4][1] for i in t[1]), 
                        preset.delay_norm + max(dp[i][4][2] for i in t[1]), 
                    ]
                ]
            )
    
    dp[op] = getOptCircuit(cost)

    if len(port["output"]) > 1: # AI
        return [[LOGIC_GATE["INPUT"], [op], "INPUT"]]
    
    return tree
    

def main():
    global dp, dp_cost, lib, module, graph, visited


    # input
    with open("input/library.json", 'r', encoding='utf-8') as f:
        temp = json.load(f)
        
        lib = [cell.Cell(key, value) for key, value in temp.items()]
        lib[0].normalization()

    with open(f"input/{MODULE_NAME}.json", 'r', encoding="utf-8") as f:
        module = json.load(f)

    # main
    dp = [-1 for _ in range(len(module["nodes"]))]
    visited = [0 for _ in range(len(module["nodes"]))]

    for o in module["outputs"]:
        dfs(o["edge"])

    # output
    graph = makeGraph(dp, module)
    before = CircuitMetrics(lib, module)
    after = CircuitMetrics(lib, graph)

    if (0):
        print("───────────────────────────────────────────────────────────")
        print("DP")
        print("───────────────────────────────────────────────────────────")
        for i in range(len(dp)):
            print(dp[i])

    print(f"{'Metric':<20} {'Original':>12} {'Optimized':>12} {'Change':>10}")
    for attribute, label in (("area", "Area (um^2)"),
                             ("leakage_power", "Leakage power (nW)"),
                             ("delay", "Delay (ns)")):
        original, optimized = getattr(before, attribute), getattr(after, attribute)
        change = f"{(optimized / original - 1) * 100:+.2f}%" if original else "N/A"
        print(f"{label:<20} {original:>12.6f} {optimized:>12.6f} {change:>10}")
    print()

    output_path = Path(f"output/{MODULE_NAME}_opt.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    if (0):
        export_schematic(graph, f"output/{INPUT_NAME}_opt.dot", with_svg=False)
    

if (__name__ == "__main__"):
    W_AREA, W_LEAKAGECUEENT, W_DELAY = 0.3, 0.3, 0.4
    MODULE_NAME = "log2"
    testCast = (
        ("OPT_Area"         , 0.8, 0.1, 0.1),
        ("OPT_Leakage_power", 0.1, 0.8, 0.1),
        ("OPT_Delay"        , 0.1, 0.1, 0.8),
        ("Balance"          , 0.34, 0.33, 0.33), 
    )

    for title, a, l, d in testCast:
        W_AREA, W_LEAKAGECUEENT, W_DELAY = a, l, d
        dp = []
        lib = []
        visited = []
        module = {}
        ahoCorasick = None
        graph = {"nodes": [], "edges": []}
        print("───────────────────────────────────────────────────────────")
        print(f"[ {title} ]")
        print("───────────────────────────────────────────────────────────")
        print(f'W_AREA: {W_AREA}')
        print(f'W_LEAKAGECUEENT: {W_LEAKAGECUEENT}')
        print(f'W_DELAY: {W_DELAY}\n')

        main()
