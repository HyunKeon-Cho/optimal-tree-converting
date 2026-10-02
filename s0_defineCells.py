class Cell():
    library = []
    area_unit = None
    leakage_power_unit = None
    delay = None

    def __init__(self, name, lib):
        self.library.append(self)

        # port
        self.name = name 
        self.inputs_name = lib["inputs"]
        self.inputs_len = len(self.inputs_name)
        self.outputs_name = lib["outputs"]
        self.outputs_len = len(self.outputs_name)
        # logic
        self.functions_str = [lib["functions"][o] for o in self.outputs_name]
        self.functions = self.__getFunction()
        self.table = self.__getTable()
        # property
        self.area = lib["area"]["value"]
        self.leakage_power = lib["leakage_power"]["value"]
        self.delay = lib["delay"]["value"]
        if (self.area_unit is None): 
            self.area_unit = lib["area"]["unit"]
        if (self.leakage_power is None): 
            self.leakage_power = lib["leakage_power"]["unit"]
        if (self.delay is None): 
            self.delay = lib["delay"]["unit"]

    def __getFunction(self):
        functions = []

        for expr in self.functions_str:
            expr = expr.replace("!", "~").strip()
            code = compile(expr, "<expr>", "eval")

            func = lambda x, code=code: int(eval(
                code,
                {"__builtins__": {}},
                {key: (x >> i) & 1 for i, key in enumerate(self.inputs_name)}
            )) & 1
            functions.append(func)

        return functions

    def __getTable(self):
        tables = []

        for func in self.functions:
            table = 0
            for x in range(1 << self.inputs_len):
                table |= func(x) << x
            tables.append(table)

        return tables

def main():
    import json

    with open("input/library.json", "r", encoding="utf-8") as f:
        cells = json.load(f)

    lib = []
    for key, value in cells.items():
        lib.append(Cell(key, value))

    print("\n".join([f"{cell.name}: {cell.inputs_len}" for cell in lib]))

if (__name__ == "__main__"):
    main()
