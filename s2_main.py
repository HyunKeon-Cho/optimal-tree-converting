import json
import s1_ahoCorasick as ac
from utiles.graph2dot import render_schematic, export_schematic

LOGIC_GATE = {
    "AND": 0b0001,
    "INV": 0b10,
}

"""
dp <- 이 노드가 끝단이라 가정할때 best case
dfs return 
"""

def mergeTable(i, o): pass

def dfs(op):
    global dp, lib, module, ahoCorasick
    
    # get sub tree
    port = module["node"][op]
    subTree = []
    # { "table", "output", "node", "edge" }
    
    if (dp.get(op)):
        subTree = dp[op] 
    
    elif (len(port["output"]) == 1): # output mult connet
        for i in port["input"]:
            sub = dfs(i)
            subTree.append(sub)
        
    # marge
    tree = []
    table = [
        [
              port["output"] 
            , LOGIC_GATE[port["op"]]
        ]
    ]
    
    if (sum([p["input"]] for p in subTree) <= 6): # gate input N limit
        mergeTable(subTree, table)
    else:
        for p in subTree:        
            if (p["input"] > 6):
                # TODO
                pass
            

def makeGraph():
    pass

def main():
    global dp, lib, module, graph, ahoCorasick
    INPUT_NAME = "toy"

    # input
    with open("input/library.json", 'r', encoding='utf-8') as f:
        lib = json.load(f)
        ahoCorasick = ac.getAhoCorasick(lib)
    with open(f"input/{INPUT_NAME}.json", 'r', encoding="utf-8") as f:
        module = json.load(f)

    # main
    for o in module["output"]:
        dfs(o["node"])
    
    # output
    rst = makeGraph()
    export_schematic(rst, f"output/{INPUT_NAME}_opt.dot", with_svg=False)
    

if (__name__ == "__main__"):
    dp = {}
    lib = {}
    module = {}
    ahoCorasick = None
    graph = {"nodes": [], "edges": []}
    
    main()