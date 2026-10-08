import unittest

from Cell import Cell


def make_cell(name, area, power, delay):
    return Cell(name, {
        "inputs": ["A"], "outputs": ["Y"], "functions": {"Y": "A"},
        "area": {"value": area, "unit": "um^2"},
        "leakage_power": {"value": power, "unit": "nW"},
        "delay": {"value": delay, "unit": "ns"},
    })


class NormalizationTests(unittest.TestCase):
    def setUp(self):
        self.registry = Cell.library
        Cell.library = []

    def tearDown(self):
        Cell.library = self.registry

    def test_maximum_scale_and_original_costs(self):
        a, b = make_cell("a", 1, 6, 0.2), make_cell("b", 4, 3, 0.4)
        library = [a, b]
        self.assertIsNone(a.normalization(library))
        self.assertEqual((b.area_norm, b.leakage_power_norm, b.delay_norm), (1.0, 0.5, 1.0))
        self.assertEqual((a.area_norm, a.leakage_power_norm,
                          a.delay_norm), (0.25, 1.0, 0.5))
        self.assertEqual((a.area, a.leakage_power, a.delay), (1, 6, 0.2))
        self.assertIsNone(a.normalization(library))
        self.assertEqual((a.area_norm, a.leakage_power_norm, a.delay_norm), (0.25, 1.0, 0.5))
        self.assertIsNone(b.normalization(library))
        self.assertEqual((b.area_norm, b.leakage_power_norm, b.delay_norm), (1.0, 0.5, 1.0))

    def test_all_zero_and_constant_columns(self):
        a, b = make_cell("a", 0, 2, 0), make_cell("b", 0, 2, 0)
        self.assertIsNone(a.normalization())
        self.assertEqual((a.area_norm, a.leakage_power_norm, a.delay_norm), (0.0, 1.0, 0.0))
        self.assertEqual((b.area_norm, b.leakage_power_norm, b.delay_norm), (0.0, 1.0, 0.0))

    def test_mixed_units_rejected(self):
        a, b = make_cell("a", 1, 1, 1), make_cell("b", 1, 1, 1)
        b.delay_unit = "ps"
        with self.assertRaisesRegex(ValueError, "Mixed units for delay"):
            a.normalization([a, b])

    def test_invalid_cost_rejected(self):
        a, b = make_cell("a", 1, 1, 1), make_cell("b", 1, float("nan"), 1)
        with self.assertRaisesRegex(ValueError, "Invalid leakage_power"):
            a.normalization([a, b])


if __name__ == "__main__":
    unittest.main()
