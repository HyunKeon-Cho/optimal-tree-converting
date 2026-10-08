# Adder (128-bit) results

## Circuit outline

EPFL combinational benchmark, converted from `reference/module/adder.aig` to an AND/INV DAG.

| Property | Original circuit |
| --- | ---: |
| Inputs | 256 |
| Outputs | 129 |
| Nodes | 2556 |
| Edges | 3319 |
| Logic cells (AND/INV) | 2170 |

[Input DAG](../input/adder.json) · [Balanced mapped DAG](../output/experiments/adder_balanced.json)

## Result table (balanced)

Weights `(wA, wP, wD) = (0.34, 0.33, 0.33)`.

| Metric | Original | Balanced | Change |
| --- | ---: | ---: | ---: |
| Cells | 2170 | 1270 | -41.47% |
| Area (μm²) | 1697.080 | 1048.838 | -38.20% |
| Representative leakage power (nW) | 42073.548 | 25913.007 | -38.41% |
| Delay (ns) | 18.208995 | 13.437548 | -26.20% |

## Cell utilization table

| Library cell | Input | Opt (balanced) |
| --- | ---: | ---: |
| INV_X1 | 1150 | 506 |
| AND2_X1 | 1020 | 381 |
| NAND2_X1 | - | 128 |
| NOR2_X1 | - | 127 |
| AOI22_X1 | - | 126 |
| XOR2_X1 | - | 2 |
| **Total** | **2170** | **1270** |

## Comparison by weight setting

| Metric | Original | Area priority | Leakage priority | Delay priority | Balanced |
| --- | ---: | ---: | ---: | ---: | ---: |
| Weights (A, P, D) | — | 0.8, 0.1, 0.1 | 0.1, 0.8, 0.1 | 0.1, 0.1, 0.8 | 0.34, 0.33, 0.33 |
| Cells | 2170 | 1270<br>(-41.47%) | 1270<br>(-41.47%) | 1270<br>(-41.47%) | 1270<br>(-41.47%) |
| Area (μm²) | 1697.080 | 1048.838<br>(-38.20%) | 1048.838<br>(-38.20%) | 1150.184<br>(-32.23%) | 1048.838<br>(-38.20%) |
| Representative leakage power (nW) | 42073.548 | 25913.007<br>(-38.41%) | 25913.007<br>(-38.41%) | 35547.390<br>(-15.51%) | 25913.007<br>(-38.41%) |
| Delay (ns) | 18.208995 | 13.437548<br>(-26.20%) | 13.437548<br>(-26.20%) | 13.174168<br>(-27.65%) | 13.437548<br>(-26.20%) |

## Balanced circuit plot

![Adder (128-bit) balanced mapped circuit](../output/plots/adder_balanced.svg)

[Open full-size SVG](../output/plots/adder_balanced.svg)
