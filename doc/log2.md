# Log2 (32-bit) results

## Circuit outline

EPFL combinational benchmark, converted from `reference/module/log2.aig` to an AND/INV DAG.

| Property | Original circuit |
| --- | ---: |
| Inputs | 32 |
| Outputs | 32 |
| Nodes | 54559 |
| Edges | 86586 |
| Logic cells (AND/INV) | 54494 |

[Input DAG](../input/log2.json) · [Balanced mapped DAG](../output/experiments/log2_balanced.json)

## Result table (balanced)

Weights `(wA, wP, wD) = (0.34, 0.33, 0.33)`.

| Metric | Original | Balanced | Change |
| --- | ---: | ---: | ---: |
| Cells | 54494 | 41694 | -23.49% |
| Area (μm²) | 46046.728 | 36109.766 | -21.58% |
| Representative leakage power (nW) | 1125617.364 | 859534.990 | -23.64% |
| Delay (ns) | 28.665107 | 26.923811 | -6.07% |

## Cell utilization table

| Library cell | Input | Opt (balanced) |
| --- | ---: | ---: |
| AND2_X1 | 32060 | 19453 |
| INV_X1 | 22434 | 16252 |
| NAND2_X1 | - | 2157 |
| AND4_X1 | - | 1253 |
| OAI21_X1 | - | 1105 |
| AND3_X1 | - | 685 |
| AOI22_X1 | - | 303 |
| NOR2_X1 | - | 208 |
| AOI221_X1 | - | 170 |
| NOR3_X1 | - | 49 |
| NAND3_X1 | - | 17 |
| OR2_X1 | - | 17 |
| AOI21_X1 | - | 15 |
| NOR4_X1 | - | 8 |
| AOI211_X1 | - | 2 |
| **Total** | **54494** | **41694** |

## Comparison by weight setting

| Metric | Original | Area priority | Leakage priority | Delay priority | Balanced |
| --- | ---: | ---: | ---: | ---: | ---: |
| Weights (A, P, D) | — | 0.8, 0.1, 0.1 | 0.1, 0.8, 0.1 | 0.1, 0.1, 0.8 | 0.34, 0.33, 0.33 |
| Cells | 54494 | 41454<br>(-23.93%) | 41511<br>(-23.82%) | 42157<br>(-22.64%) | 41694<br>(-23.49%) |
| Area (μm²) | 46046.728 | 36000.174<br>(-21.82%) | 36017.996<br>(-21.78%) | 38356.668<br>(-16.70%) | 36109.766<br>(-21.58%) |
| Representative leakage power (nW) | 1125617.364 | 855817.621<br>(-23.97%) | 856046.966<br>(-23.95%) | 1052098.930<br>(-6.53%) | 859534.990<br>(-23.64%) |
| Delay (ns) | 28.665107 | 26.943867<br>(-6.00%) | 26.986496<br>(-5.86%) | 26.751613<br>(-6.68%) | 26.923811<br>(-6.07%) |

## Balanced circuit plot

![Log2 (32-bit) balanced mapped circuit](../output/plots/log2_balanced.svg)

[Open full-size SVG](../output/plots/log2_balanced.svg)
