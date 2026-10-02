import json
import s1_ahoCorasick as ac

def dfs(po):
    global dp, lib, module, ahoCorasick
    
    if (dp.get(po)):
        pass

def main():
    global dp, lib, module, graph, ahoCorasick

    # input
    with open("input/library.json", 'r', encoding='utf-8') as f:
        lib = json.load(f)
        ahoCorasick = ac.getAhoCorasick(lib)
    with open("input/adder.json", 'r', encoding="utf-8") as f:
        module = json.load(f)

    # main
    for o in module["output"]:
        dfs(o)

if (__name__ == "__main__"):
    dp = {}
    lib = {}
    module = {}
    ahoCorasick = None
    graph = {"nodes": [], "edges": []}
    
    main()