import math

class Cell():
    library = []
    area_unit = None
    leakage_power_unit = None
    delay_unit = None

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
        self.area_norm = None
        self.area_unit = lib["area"]["unit"]
        self.leakage_power = lib["leakage_power"]["value"]
        self.leakage_power_norm = None
        self.leakage_power_unit = lib["leakage_power"]["unit"]
        self.delay = lib["delay"]["value"]
        self.delay_norm = None
        self.delay_unit = lib["delay"]["unit"]

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

    def normalization(self, library=None):
        """Normalize every cell relative to each library cost maximum.

        One call updates all cells in Cell.library, or in the supplied list.
        Original physical costs are unchanged. An all-zero cost column stays
        zero. Store results in each cell's *_norm fields; return nothing.
        """
        library = list(self.library if library is None else library)
        if not library or not any(item is self for item in library):
            raise ValueError("Normalization library must include this cell")
        reference = {}
        for attribute in ("area", "leakage_power", "delay"):
            values = []
            unit = getattr(self, attribute + "_unit")
            for item in library:
                if not isinstance(item, Cell):
                    raise TypeError("Normalization library must contain Cell instances")
                if getattr(item, attribute + "_unit") != unit:
                    raise ValueError(f"Mixed units for {attribute}")
                value = getattr(item, attribute)
                if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError(f"Invalid {attribute} for cell {item.name}")
                values.append(value)
            reference[attribute] = max(values)

        for item in library:
            item.normalization_reference = reference.copy()
            for attribute, maximum in reference.items():
                value = getattr(item, attribute) / maximum if maximum else 0.0
                setattr(item, attribute + "_norm", value)

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
