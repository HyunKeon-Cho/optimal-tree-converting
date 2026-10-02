# 입력 데이터 변환

Python 3.9 이상, 표준 라이브러리만 사용합니다. 프로젝트 루트에서 실행합니다.

```powershell
python reference/tools/lib2json.py reference/lib/NangateOpenCellLibrary_typical.lib -o reference/modified/nangate45.json
python reference/tools/logic2graph.py
```

위 명령은 라이브러리를 `reference/modified/nangate45.json`에 저장합니다.
회로 변환기의 기본 입력은 `reference/module/adder.aig`, 기본 출력은 `input/adder.json`입니다.
회로 입력을 지정하면 원본 파일 이름에 맞춰 `input/<이름>.json`으로 저장합니다.
입력과 출력 경로를 지정할 수도 있습니다.

```powershell
python reference/tools/lib2json.py reference/lib/NangateOpenCellLibrary_typical.lib -o outputs/library.json
python reference/tools/logic2graph.py reference/module/log2.aig
python reference/tools/logic2graph.py reference/module/adder.blif -o input/adder_blif.json
```

## Liberty JSON

`cells`는 셀 이름을 키로 하는 딕셔너리입니다. 각 셀에 `area`, `inputs`, `outputs`,
`functions`, `pins`가 있습니다. 입력 핀의 capacitance와 출력 핀의 timing arc를 보존합니다.
순차 셀, 다중 출력 셀, 물리 전용 셀도 포함하므로 매핑 알고리즘에서 지원 셀을 선택해야 합니다.

```python
import json

with open('reference/modified/nangate45.json', encoding='utf-8') as stream:
    library = json.load(stream)
cell = library['cells']['AND2_X1']
area = cell['area']
function = cell['functions']['ZN']
arc = cell['pins']['ZN']['timing'][0]
rise = next(group for group in arc['groups'] if group['type'] == 'cell_rise')
table = {entry['name']: entry['values'] for entry in rise['complex_attributes']}
# table['index_1'], table['index_2']: 숫자 축; table['values']: 2차원 숫자 배열
```

조회표의 `index_1`, `index_2`는 숫자 배열이고 `values`는 행별 숫자 배열입니다.
표가 참조하는 template 이름은 `args`에 있고, template의 축 정의는 최상위 `groups`에 있습니다.
단위와 PVT 조건은 최상위 `attributes`, `complex_attributes`, `groups`에 보존됩니다.
면적은 Liberty 원래 값이며 임의 단위를 추가하지 않습니다.
고정 slew/load의 단일 지연값 계산과 셀 함수의 패턴 그래프 변환은 이 변환기에 포함되지 않습니다.

## 회로 JSON 파일

```python
import json

with open('input/adder.json', encoding='utf-8') as stream:
    GRAPH = json.load(stream)

print(GRAPH['stats'])
first_node = GRAPH['nodes'][GRAPH['topological_order'][0]]
```

- `GRAPH['schema_version']`은 4입니다. `nodes`, `edges`는 모두 리스트이며 0부터 시작하는 인덱스로 식별합니다.
- `GRAPH['nodes'][i]`: i번 노드 속성. `op`은 `INPUT`, `CONST`, `AND`, `INV`, `OUTPUT`입니다.
- `GRAPH['edges'][i]`: i번 간선의 `source`, `target`, `port`입니다. `source`, `target`은 노드 인덱스입니다.
- 각 노드의 `input`, `output`은 들어오는/나가는 간선 인덱스 목록입니다. 연결이 없으면 빈 목록입니다.
- `input` 목록의 순서는 입력 번호 `port`와 같습니다(AND는 0, 1; INV/OUTPUT은 0).
- `GRAPH['inputs']`, `GRAPH['outputs']`: 신호 이름과 INPUT/OUTPUT 노드 인덱스입니다.
- 노드 0은 상수 False입니다. True가 필요하면 이 상수에서 INV 노드로 연결합니다.
- `GRAPH['topological_order']`: 입력 쪽부터 출력 쪽으로 모든 노드를 처리하는 순서입니다.
- 하나의 신호를 반전한 값이 여러 곳에서 사용되면 하나의 INV 노드를 공유합니다.
- 공유 노드를 분할하거나 복제하지 않습니다. 여러 간선이 같은 노드 인덱스를 참조하는 하나의 DAG입니다.
- 원본 AIGER의 노드 번호는 연속 리스트 인덱스로 변환합니다. 리스트 순서 자체는 위상 순서가 아니므로 계산할 때 `topological_order`를 사용합니다.
- `convert(path)`는 그래프 딕셔너리 하나를 반환하고, 출력 파일에는 이 딕셔너리를 JSON 객체로 저장합니다.
- 출력과 무관한 AND 노드는 제거하며 사용하지 않는 주입력은 이름과 함께 보존합니다.

AIGER 기본 `.aig`(바이너리), `.aag`(텍스트), flat BLIF의 `.names` 진리표를 지원합니다.
출력은 AND와 독립 INV 게이트로 이루어집니다. BLIF를 이 형태로 변환하므로 AIG 입력과 노드 ID/구조가 같을 필요는 없습니다.
BLIF는 on-set 또는 off-set 단일 극성 cover를 지원하며 혼합 cover는 오류로 처리합니다.
래치, BLIF `.gate`/`.subckt`, 확장 AIGER property 헤더는 지원하지 않습니다.
이 파일은 매핑 알고리즘의 입력 그래프이며, 매핑 결과를 계산하지 않습니다.
