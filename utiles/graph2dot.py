"""Digital schematic: zero-length pin stubs, SVG gates and orthogonal wires.

The SVG renderer is self-contained. Default DOT works in ordinary previews.
Use --fixed-dot and Graphviz neato -n2 for an optional fixed-coordinate DOT.
"""
import argparse
import base64
from bisect import bisect_right
from collections import deque
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ROOT / 'utiles/symbols/schematic'
GATES = {'AND', 'NAND', 'OR', 'NOR', 'XOR', 'XNOR', 'INV', 'NOT', 'BUF'}
INK = '#334155'

def simplify_route(points):
    clean = []
    for point in points:
        if clean and point == clean[-1]:
            continue
        while len(clean) >= 2 and ((clean[-2][0] == clean[-1][0] == point[0]) or
                                  (clean[-2][1] == clean[-1][1] == point[1])):
            clean.pop()
        clean.append(point)
    return clean

def reduce_bends(route, boxes, source, target, gutters, other_routes=()):
    """Prefer a straight or two-bend route only when its entire path is clear."""
    obstacles = [(x-2, y-2, w+4, h+4) for i,(x,y,w,h) in boxes.items() if i not in (source,target)]
    def clear(points):
        for a,b in zip(points,points[1:]):
            for x,y,w,h in obstacles:
                if a[1] == b[1]:
                    if y < a[1] < y+h and max(min(a[0],b[0]),x) < min(max(a[0],b[0]),x+w): return False
                elif x < a[0] < x+w and max(min(a[1],b[1]),y) < min(max(a[1],b[1]),y+h): return False
            for other in other_routes:
                for c,d in zip(other,other[1:]):
                    if a[1]==b[1] and c[1]==d[1] and a[1]==c[1]:
                        if max(min(a[0],b[0]),min(c[0],d[0])) < min(max(a[0],b[0]),max(c[0],d[0])): return False
                    if a[0]==b[0] and c[0]==d[0] and a[0]==c[0]:
                        if max(min(a[1],b[1]),min(c[1],d[1])) < min(max(a[1],b[1]),max(c[1],d[1])): return False
        return True
    route = simplify_route(route)
    start,finish=route[0],route[-1]
    if len(route)<=4: return route
    candidates=[]
    if start[1]==finish[1]: candidates.append([start,finish])
    for lane in [start[0]+15,finish[0]-15]+gutters:
        if start[0]<lane<finish[0]:
            candidates.append(simplify_route([start,(lane,start[1]),(lane,finish[1]),finish]))
    for candidate in sorted(candidates,key=lambda p:len(p)):
        if len(candidate)<len(route) and clear(candidate): return candidate
    # Remove intermediate stair steps where a horizontal shortcut is possible.
    changed=True
    while changed:
        changed=False
        for i in range(len(route)-3):
            for j in range(len(route)-1,i+2,-1):
                a,b=route[i],route[j]
                if a[1]==b[1] and clear([a,b]):
                    route=simplify_route(route[:i+1]+route[j:]);changed=True;break
            if changed:break
    return route

def crossings(scene):
    """Bridge horizontal wires over unrelated vertical wires; preserve net dots."""
    horizontal,vertical=[],[]
    for ei,route in enumerate(scene['routes']):
        net=scene['graph']['edges'][ei]['source']
        for a,b in zip(route,route[1:]):
            if a[1]==b[1]: horizontal.append((ei,net,min(a[0],b[0]),max(a[0],b[0]),a[1]))
            else: vertical.append((net,a[0],min(a[1],b[1]),max(a[1],b[1])))
    vertical.sort(key=lambda v:v[1])
    xs=[v[1] for v in vertical]
    bridges={}
    for ei,net,left,right,y in horizontal:
        for other,x,top,bottom in vertical[bisect_right(xs,left+4):bisect_right(xs,right-4)]:
            if other!=net and top<=y<=bottom:
                bridges.setdefault(ei,set()).add((x,y))
    return bridges

def junction_points(scene):
    nets = {}
    for ei, route in enumerate(scene['routes']):
        net = scene['graph']['edges'][ei]['source']
        nets.setdefault(net, []).append(route)
    points = {}
    for net, routes in nets.items():
        for i, first in enumerate(routes):
            for second in routes[i+1:]:
                if len(first)>1 and len(second)>1:
                    x=min(first[1][0],second[1][0])
                    if x>first[0][0]: points.setdefault(net,set()).add((x,first[0][1]))
    return points

def jump_paths(scene):
    """One smooth bridge per crossing cluster; keep electrical junctions clear."""
    groups, supports = {}, {}
    junctions = junction_points(scene)
    for ei, locations in crossings(scene).items():
        net=scene['graph']['edges'][ei]['source']
        for x,y in locations: groups.setdefault((net,y),set()).add(x)
    for ei, route in enumerate(scene['routes']):
        net=scene['graph']['edges'][ei]['source']
        for a,b in zip(route,route[1:]):
            if a[1]==b[1]: supports.setdefault((net,a[1]),[]).append((min(a[0],b[0]),max(a[0],b[0])))
    paths, gaps = [],set()
    for (net,y), locations in sorted(groups.items()):
        protected=[x for x,jy in junctions.get(net,()) if jy==y]
        clusters=[]
        for x in sorted(locations):
            if any(abs(x-p)<6 for p in protected):
                # At a real branch, gap the unrelated vertical wire instead.
                gaps.add((x,y));continue
            if clusters and x-clusters[-1][-1]<11 and not any(clusters[-1][-1]<p<x for p in protected):
                clusters[-1].append(x)
            else: clusters.append([x])
        for cluster in clusters:
            left,right=cluster[0]-4,cluster[-1]+4
            intervals=[(a,b) for a,b in supports[(net,y)] if a<=cluster[0]<=b]
            if intervals:
                left=max(left,min(a for a,b in intervals)+1)
            intervals=[(a,b) for a,b in supports[(net,y)] if a<=cluster[-1]<=b]
            if intervals:
                right=min(right,max(b for a,b in intervals)-1)
            before=[p for p in protected if p<cluster[0]]
            after=[p for p in protected if p>cluster[-1]]
            if before:left=max(left,max(before)+3.5)
            if after:right=min(right,min(after)-3.5)
            rise=min(4.5,(right-left)/2)
            ramp=min(4,(right-left)/2)
            # Cubics meet the straight wire with horizontal tangents, and the
            # crest is continuous even when a bridge spans several close wires.
            d=(f'M{left:.3f} {y:.3f} C{left+ramp*.6:.3f} {y:.3f} '
               f'{left+ramp*.4:.3f} {y-rise:.3f} {left+ramp:.3f} {y-rise:.3f} '
               f'H{right-ramp:.3f} C{right-ramp*.4:.3f} {y-rise:.3f} '
               f'{right-ramp*.6:.3f} {y:.3f} {right:.3f} {y:.3f}')
            paths.append((net,left,right,y,d))
    return paths,gaps

def wire_path(points, net, bridges):
    """Replace horizontal sections by bridges instead of erasing base wires."""
    parts=[f'M{points[0][0]:.3f} {points[0][1]:.3f}']
    for a,b in zip(points,points[1:]):
        if a[1]==b[1]:
            spans=[item for item in bridges if item[0]==net and item[3]==a[1]
                   and min(a[0],b[0])<=item[1] and item[2]<=max(a[0],b[0])]
            spans.sort(key=lambda item:item[1],reverse=b[0]<a[0])
            for _,left,right,y,d in spans:
                if b[0]>=a[0]:
                    parts.append(f'H{left:.3f}')
                    parts.append(d.split(' ',2)[2])
                else:
                    ramp=min(4,(right-left)/2)
                    rise=min(4.5,(right-left)/2)
                    parts.append(f'H{right:.3f} C{right-ramp*.6:.3f} {y:.3f} '
                                 f'{right-ramp*.4:.3f} {y-rise:.3f} {right-ramp:.3f} {y-rise:.3f} '
                                 f'H{left+ramp:.3f} C{left+ramp*.4:.3f} {y-rise:.3f} '
                                 f'{left+ramp*.6:.3f} {y:.3f} {left:.3f} {y:.3f}')
            parts.append(f'H{b[0]:.3f}')
        else:
            parts.append(f'V{b[1]:.3f}')
    return ' '.join(parts)

def library():
    return json.loads((ROOT / 'input/library.json').read_text(encoding='utf-8'))

def describe(node, lib, basic=False):
    op = node['op']
    cell = node.get('cell', node.get('cell_name', op))
    if cell not in lib and op == 'CELL':
        cell = node.get('name', cell)
    if cell in lib:
        record = lib[cell]
        match = re.fullmatch(r'(AND|NAND|OR|NOR|XOR|XNOR)\d+_X\d+', cell)
        family = match.group(1) if match else ('INV' if cell.startswith('INV_') else 'BUF' if cell.startswith(('BUF_', 'CLKBUF_')) else 'BOX')
        return {'family': 'BOX' if basic else family, 'label': cell,
                'pins': record['inputs'], 'outputs': record['outputs']}
    if op == 'CELL':
        raise ValueError(f'Unknown library cell: {cell}')
    family = op if op in GATES and not basic else 'BOX'
    label = node.get('name', op) if op in ('INPUT', 'OUTPUT') else str(int(node['value'])) if op == 'CONST' else op
    return {'family': family, 'label': label, 'pins': None, 'outputs': ['Y']}

def geometry(info, count):
    family = info['family']
    height = max(44, count * 18 + 12)
    width = 80 if family != 'BOX' else max(76, len(info['label']) * 7.4 + 22)
    if family in ('INV', 'NOT'):
        width, height = 48, 28
    ys = [height * (p + 1) / (count + 1) for p in range(count)]
    def inlet(y):
        if family in ('OR', 'NOR', 'XOR', 'XNOR'):
            t = y / height
            # Quadratic Bezier M0,0 Q28,h/2 0,h: x=2*28*t*(1-t).
            return 56 * t * (1 - t)
        return 0
    return width, height, [(inlet(y), y) for y in ys], (width, height / 2)

def artwork(info, width, height):
    """Geometry boundary is also the electrical attachment boundary: no stubs."""
    family = info['family']
    h, w = height, width
    fill = '#f8fafc'
    if family == 'BOX':
        return f'<rect width="{w}" height="{h}" rx="0" fill="#eef2ff"/><text x="{w/2}" y="{h/2}" fill="{INK}" stroke="none" font-size="12" text-anchor="middle" dominant-baseline="middle">{html.escape(info["label"])}</text>'
    bubble = family in ('NAND', 'NOR', 'XNOR', 'INV', 'NOT')
    bubble_radius = 4 if family in ('INV', 'NOT') else 6
    end = w - 2 * bubble_radius if bubble else w
    if family in ('AND', 'NAND'):
        radius = h / 2
        body = f'M0 0 H{end-radius} A{radius} {radius} 0 0 1 {end-radius} {h} H0 Z'
    elif family in ('OR', 'NOR', 'XOR', 'XNOR'):
        left = 6 if family in ('XOR', 'XNOR') else 0
        body = f'M{left} 0 Q{end*.62} 0 {end} {h/2} Q{end*.62} {h} {left} {h} Q{28+left} {h/2} {left} 0 Z'
    else:
        body = f'M0 0 L{end} {h/2} L0 {h} Z'
    parts = [f'<path d="{body}" fill="{fill}"/>']
    if family in ('XOR', 'XNOR'):
        # Parallel arc is inside the symbol envelope; inlet lies on its boundary.
        parts.append(f'<path d="M0 0 Q28 {h/2} 0 {h}" fill="none"/>')
    if bubble:
        parts.append(f'<circle cx="{w-bubble_radius}" cy="{h/2}" r="{bubble_radius}" fill="white"/>')
    return ''.join(parts)

def layout(graph, basic=False, fast=False, lib=None):
    lib = library() if lib is None else lib
    nodes, edges = graph['nodes'], graph['edges']
    incoming = [[] for _ in nodes]
    outgoing = [[] for _ in nodes]
    for i, edge in enumerate(edges):
        a, b, port = edge['source'], edge['target'], edge['port']
        if not isinstance(port, int) or port < 0 or not (0 <= a < len(nodes) and 0 <= b < len(nodes)):
            raise ValueError(f'Invalid edge {i}')
        incoming[b].append(i)
        outgoing[a].append(i)
    degree = [len(v) for v in incoming]
    ready = deque(i for i, d in enumerate(degree) if d == 0)
    order, depth = [], [0] * len(nodes)
    while ready:
        a = ready.popleft()
        order.append(a)
        for ei in outgoing[a]:
            b = edges[ei]['target']
            depth[b] = max(depth[b], depth[a] + 1)
            degree[b] -= 1
            if degree[b] == 0:
                ready.append(b)
    if len(order) != len(nodes):
        raise ValueError('Circuit must be a DAG')
    # All output terminals share the rightmost column, even on short paths.
    output_depth = max((depth[i] for i, n in enumerate(nodes) if n['op'] != 'OUTPUT'), default=-1) + 1
    for i, node in enumerate(nodes):
        if node['op'] == 'OUTPUT':
            if outgoing[i]:
                raise ValueError(f'Output terminal {i} cannot drive another node')
            depth[i] = output_depth
    infos, sizes = [], []
    for i, node in enumerate(nodes):
        info = describe(node, lib, basic)
        count = len(incoming[i])
        ports = sorted(edges[e]['port'] for e in incoming[i])
        if ports != list(range(count)):
            raise ValueError(f'Node {i}: input ports must be unique and consecutive')
        expected = len(info['pins']) if info['pins'] is not None else 2 if node['op'] in ('AND', 'NAND', 'OR', 'NOR', 'XOR', 'XNOR') else 1 if node['op'] in ('INV', 'NOT', 'BUF', 'OUTPUT') else 0 if node['op'] in ('INPUT', 'CONST') else count
        if count != expected:
            raise ValueError(f'Node {i}: expected {expected} inputs, got {count}')
        infos.append(info)
        sizes.append(geometry(info, count))
    output_ids = [i for i,n in enumerate(nodes) if n['op']=='OUTPUT']
    declared = [pin['node'] for pin in graph.get('outputs', [])]
    if len(declared)!=len(set(declared)) or any(i not in output_ids for i in declared):
        raise ValueError('Invalid outputs list')
    output_order = declared + [i for i in output_ids if i not in declared]
    output_rank = {i:r for r,i in enumerate(output_order)}
    output_width = max((sizes[i][0] for i in output_ids), default=0)
    for i in output_ids:
        _,h,pins,_=sizes[i]
        sizes[i]=(output_width,h,pins,(output_width,h/2))
    # Insert invisible routing slots at every skipped layer. Wires then cannot
    # pass through an intermediate cell, and all bends stay in column gutters.
    layers = [[] for _ in range(max(depth, default=0) + 1)]
    neighbors_in, neighbors_out = {}, {}
    for i in order:
        layers[depth[i]].append(i)
    chains = []
    for ei, edge in enumerate(edges):
        chain = [edge['source']]
        for d in range(depth[edge['source']] + 1, depth[edge['target']]):
            dummy = f'e{ei}d{d}'
            layers[d].append(dummy)
            chain.append(dummy)
        chain.append(edge['target'])
        for a, b in zip(chain, chain[1:]):
            neighbors_out.setdefault(a, []).append(b)
            neighbors_in.setdefault(b, []).append(a)
        chains.append(chain)
    positions = {v: p for layer in layers for p, v in enumerate(layer)}
    for _ in range(2 if fast else 8):
        for forward in (True, False):
            sequence = layers[1:] if forward else list(reversed(layers[:-1]))
            neighbors = neighbors_in if forward else neighbors_out
            for layer in sequence:
                if layer and all(v in output_rank for v in layer):
                    layer.sort(key=output_rank.get)
                else:
                    layer.sort(key=lambda v: sum(positions[u] for u in neighbors.get(v, [])) / len(neighbors[v]) if neighbors.get(v) else positions[v])
                positions.update({v: p for p, v in enumerate(layer)})
    pitch = max(74, max((s[1] for s in sizes), default=44) + 30)
    maxrows = max(map(len, layers), default=1)
    column_widths = [max((sizes[v][0] for v in layer if isinstance(v, int)), default=80) for layer in layers]
    crossings = [sum(len(chain) > 1 and depth[edges[ei]['source']] <= d < depth[edges[ei]['target']] for ei, chain in enumerate(chains)) for d in range(max(0, len(layers)-1))]
    xs, x = [], 40
    for d, width in enumerate(column_widths):
        xs.append(x)
        x += width + (max(100, crossings[d] * 5 + 30) if d < len(crossings) else 40)
    points, placements = {}, {}
    for d, layer in enumerate(layers):
        offset = (maxrows - len(layer)) * pitch / 2
        for p, v in enumerate(layer):
            cy = 64 + offset + p * pitch + pitch / 2
            points[v] = (xs[d] + column_widths[d]/2, cy)
            if isinstance(v, int):
                w, h, _, _ = sizes[v]
                left = xs[d] + (column_widths[d]-w)/2
                if nodes[v]['op'] == 'OUTPUT':
                    left = xs[d] + column_widths[d] - w
                placements[v] = (left, cy-h/2, w, h)
    routes, lane_counts = [], [0] * len(crossings)
    for ei, chain in enumerate(chains):
        edge = edges[ei]
        a, b = edge['source'], edge['target']
        ax, ay, aw, ah = placements[a]
        bx, by, _, _ = placements[b]
        inlet = sizes[b][2][edge['port']]
        start = (ax + aw, ay + ah/2)
        finish = (bx + inlet[0], by + inlet[1])
        route = [start]
        for step, (u, v) in enumerate(zip(chain, chain[1:])):
            d = depth[a] + step
            left = xs[d] + column_widths[d]
            right = xs[d+1]
            lane_counts[d] += 1
            lane = left + 15 + (right-left-30) * lane_counts[d]/(crossings[d]+1)
            target = finish if v == b else points[v]
            route.extend([(lane, route[-1][1]), (lane, target[1]), target])
        routes.append(simplify_route(route))
    gutters=[(xs[d]+column_widths[d]+xs[d+1])/2 for d in range(len(xs)-1)]
    for ei,edge in enumerate(edges):
        other_routes=[route for j,route in enumerate(routes) if edges[j]['source']!=edge['source']]
        routes[ei]=reduce_bends(routes[ei],placements,edge['source'],edge['target'],gutters,other_routes)
    return {'graph': graph, 'infos': infos, 'sizes': sizes, 'placements': placements,
            'routes': routes, 'width': x, 'height': 128 + maxrows*pitch}

def svg(scene):
    w, h = scene['width'], scene['height']
    bridges,gaps=jump_paths(scene)
    result = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
              '<rect width="100%" height="100%" fill="white"/>',
              f'<text x="40" y="28" font-family="Arial" font-size="18" fill="{INK}">{html.escape(str(scene["graph"].get("source", "Circuit")))}</text>',
              f'<g fill="none" stroke="{INK}" stroke-width="1.5" stroke-linejoin="miter" stroke-linecap="butt">']
    for ei, points in enumerate(scene['routes']):
        edge = scene['graph']['edges'][ei]
        info = scene['infos'][edge['target']]
        pin = info['pins'][edge['port']] if info['pins'] else str(edge['port'])
        path=wire_path(points,edge['source'],bridges)
        result.append(f'<path id="wire-{ei}" d="{path}"><title>Node {edge["source"]} → Node {edge["target"]}, pin {html.escape(pin)}</title></path>')
    result.append('</g>')
    # Paint every halo first, then every foreground arc: adjacent/shared paths
    # cannot erase an arc that has already been painted.
    for net,left,right,y,d in bridges:
        result.append(f'<path class="wire-jump-mask" d="{d}" stroke="white" stroke-width="3.5" stroke-linecap="round" fill="none"/>')
    for x,y in sorted(gaps):
        result.append(f'<path class="wire-crossing-gap" d="M{x:.3f} {y-3:.3f} V{y+3:.3f}" stroke="white" stroke-width="2.5"/>')
    for net,left,right,y,d in bridges:
        # The round halo extends past the arc endpoints. Repaint a short
        # straight overlap at each end so the bridge joins without white seams.
        connected = d.replace(f'M{left:.3f} {y:.3f}',
                              f'M{left-2.5:.3f} {y:.3f} H{left:.3f}', 1)
        connected += f' H{right+2.5:.3f}'
        result.append(f'<path class="wire-jump" data-net="{net}" d="{connected}" stroke="{INK}" stroke-width="1.5" stroke-linecap="butt" fill="none"/>')
    for x,y in sorted(gaps):
        result.append(f'<path d="M{x-3:.3f} {y:.3f} H{x+3:.3f}" stroke="{INK}" stroke-width="1.5"/>')
    # A dot denotes a shared electrical net, never an unrelated wire crossing.
    junctions = {point for points in junction_points(scene).values() for point in points}
    for x, y in sorted(junctions):
        result.append(f'<circle class="junction" cx="{x:.3f}" cy="{y:.3f}" r="2.5" fill="{INK}"/>')
    for i, info in enumerate(scene['infos']):
        x, y, width, height = scene['placements'][i]
        result.append(f'<g id="node-{i}" transform="translate({x:.3f} {y:.3f})" font-family="Arial" stroke="{INK}" stroke-width="1.5" stroke-linejoin="miter"><title>Node {i}: {html.escape(info["label"])}</title>{artwork(info, width, height)}</g>')
    result.append('</svg>')
    return '\n'.join(result) + '\n'

def to_fixed_dot(graph, fast=False, basic=False):
    scene = layout(graph, basic, fast)
    payload = base64.b64encode(json.dumps({'graph': graph, 'basic': basic, 'fast': fast}).encode()).decode()
    lines = ['digraph circuit {', '// Fixed schematic: render with neato -n2.', '// schematic-data: ' + payload,
             'graph [layout=neato, splines=true, overlap=true, bgcolor="white"];',
             'node [shape=box, fixedsize=true, margin=0, fontname="Arial", fontsize=12];',
             f'edge [arrowhead=none, color="{INK}", penwidth=1.5, headclip=false, tailclip=false];']
    for i, info in enumerate(scene['infos']):
        x, y, w, h = scene['placements'][i]
        attrs = [f'pos="{x+w/2:.3f},{scene["height"]-y-h/2:.3f}!"', f'width={w/72:.6f}', f'height={h/72:.6f}']
        if info['family'] == 'BOX':
            attrs.extend(['style=filled', 'fillcolor="#eef2ff"', 'label='+json.dumps(info['label'])])
        else:
            filename = f'{info["family"].lower()}-{len(scene["sizes"][i][2])}.svg'
            attrs.extend(['shape=none', 'label=""', 'image='+json.dumps((SYMBOLS/filename).as_posix()), 'imagescale=true'])
        lines.append(f'n{i} [{", ".join(attrs)}];')
    for ei, points in enumerate(scene['routes']):
        # Encode each straight section as a cubic Bezier with collinear controls.
        controls = [points[0]]
        for a, b in zip(points, points[1:]):
            controls.extend([(a[0]+(b[0]-a[0])/3, a[1]+(b[1]-a[1])/3),
                             (a[0]+2*(b[0]-a[0])/3, a[1]+2*(b[1]-a[1])/3), b])
        pos = ' '.join(f'{x:.3f},{scene["height"]-y:.3f}' for x,y in controls)
        edge = graph['edges'][ei]
        lines.append(f'n{edge["source"]} -> n{edge["target"]} [pos="{pos}", tooltip="input {edge["port"]}"];')
    return '\n'.join(lines + ['}']) + '\n'

def to_dot(graph, fast=False, basic=False, fixed=False):
    if fixed:
        return to_fixed_dot(graph,fast,basic)
    scene=layout(graph,basic,fast)
    payload=base64.b64encode(json.dumps({'graph':graph,'basic':basic,'fast':fast}).encode()).decode()
    lines=['digraph circuit {','// Portable DOT preview: use --svg for exact gate artwork and wire jumps.',
           '// schematic-data: '+payload,
           'graph [layout=dot, rankdir=LR, splines=ortho, nodesep=0.3, ranksep=0.7, bgcolor="white"];',
           f'node [shape=box, style=filled, fillcolor="#f8fafc", color="{INK}", fontcolor="{INK}", fontname="Arial", fontsize=12, margin="0.1,0.05"];',
           f'edge [arrowhead=none, color="{INK}", penwidth=1.5];']
    for i,info in enumerate(scene['infos']):
        attrs=['label='+json.dumps(info['label'] if info['family']=='BOX' else info['family'])]
        op=graph['nodes'][i]['op']
        if op in ('INPUT','OUTPUT','CONST'):attrs.append('fillcolor="#eef2ff"')
        if op=='OUTPUT':attrs.extend([f'width={scene["sizes"][i][0]/72:.6f}', 'fixedsize=true'])
        lines.append(f'n{i} [{", ".join(attrs)}];')
    for edge in graph['edges']:
        lines.append(f'n{edge["source"]} -> n{edge["target"]} [tooltip="input {edge["port"]}"];')
    for op,rank,key in [('INPUT','source','inputs'),('OUTPUT','sink','outputs')]:
        ids=[i for i,n in enumerate(graph['nodes']) if n['op']==op]
        declared=[p['node'] for p in graph.get(key,[])]
        ids=declared+[i for i in ids if i not in declared]
        if ids:
            lines.append('{ rank='+rank+'; '+'; '.join(f'n{i}' for i in ids)+'; }')
            for a,b in zip(ids,ids[1:]):lines.append(f'n{a} -> n{b} [style=invis, weight=100];')
    return '\n'.join(lines+['}'])+'\n'

def write_symbols(scene):
    SYMBOLS.mkdir(parents=True, exist_ok=True)
    for i, info in enumerate(scene['infos']):
        if info['family'] == 'BOX': continue
        w, h, pins, _ = scene['sizes'][i]
        text = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><g stroke="{INK}" stroke-width="1.5" stroke-linejoin="miter">{artwork(info,w,h)}</g></svg>'
        (SYMBOLS/f'{info["family"].lower()}-{len(pins)}.svg').write_text(text, encoding='utf-8')

def render_svg(dot_path, output):
    match = re.search(r'^// schematic-data: (.+)$', Path(dot_path).read_text(encoding='utf-8'), re.M)
    if not match: raise ValueError('DOT must be generated by this schematic renderer')
    data = json.loads(base64.b64decode(match.group(1)))
    scene = layout(data['graph'], data['basic'], data['fast'])
    Path(output).write_text(svg(scene), encoding='utf-8')

def _read_graph(source):
    """Accept an already loaded graph or a JSON file path."""
    if isinstance(source, dict):
        return source
    return json.loads(Path(source).read_text(encoding='utf-8'))

def render_schematic(source, *, fast=False, basic=False, fixed_dot=False):
    """Return {'dot': str, 'svg': str} without writing files or printing.

    source may be a graph dictionary, a str path, or a pathlib.Path. Relative
    source paths are resolved from the caller's current working directory.
    Exceptions are propagated to the caller; this function never exits Python.
    """
    graph = _read_graph(source)
    scene = layout(graph, basic, fast)
    return {'dot': to_dot(graph, fast, basic, fixed=fixed_dot),
            'svg': svg(scene)}

def export_schematic(source, output_path=None, *, with_svg=True, fast=False,
                     basic=False, fixed_dot=False):
    """Write a schematic and return its paths and node/edge counts.

    source may be a graph dictionary or JSON path. A path source defaults to
    a DOT beside that JSON; a dictionary requires output_path. with_svg writes
    a companion SVG. Existing output files are replaced, but source overwrite
    and conflicting output paths are rejected. No printing or process exit.
    """
    input_path = None if isinstance(source, dict) else Path(source)
    if output_path is None:
        if input_path is None:
            raise ValueError('output_path is required for a graph dictionary')
        output_path = input_path.with_suffix('.dot')
    output_path = Path(output_path)
    svg_path = output_path.with_suffix('.svg') if with_svg else None
    if input_path is not None and output_path.resolve() == input_path.resolve():
        raise ValueError('Output must differ from input')
    if svg_path is not None:
        conflicts = [output_path.resolve()]
        if input_path is not None:
            conflicts.append(input_path.resolve())
        if svg_path.resolve() in conflicts:
            raise ValueError('SVG path conflicts with input or DOT')
    graph = _read_graph(source)
    rendered = render_schematic(graph, fast=fast, basic=basic, fixed_dot=fixed_dot)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if fixed_dot:
        write_symbols(layout(graph, basic, fast))
    output_path.write_text(rendered['dot'], encoding='utf-8')
    if svg_path is not None:
        svg_path.write_text(rendered['svg'], encoding='utf-8')
    return {'dot_path': output_path, 'svg_path': svg_path,
            'node_count': len(graph['nodes']), 'edge_count': len(graph['edges'])}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', type=Path, default=ROOT/'input/adder.json')
    parser.add_argument('-o', '--output', type=Path)
    parser.add_argument('--svg', action='store_true', help='Also write the authoritative circuit SVG')
    parser.add_argument('--fast', action='store_true', help='Fewer layout sweeps; wires remain orthogonal')
    parser.add_argument('--basic', action='store_true', help='Draw all cells as labeled boxes')
    parser.add_argument('--fixed-dot', action='store_true', help='Export fixed-position DOT for neato -n2 instead of portable preview DOT')
    args = parser.parse_args()
    try:
        result = export_schematic(args.input, args.output, with_svg=args.svg,
                                  fast=args.fast, basic=args.basic,
                                  fixed_dot=args.fixed_dot)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'graph2dot: {error}\n')
    print(f'Wrote {result["node_count"]} nodes, {result["edge_count"]} orthogonal wires to {result["dot_path"]}')
    if args.svg: print(f'Wrote {result["svg_path"]}')

if __name__ == '__main__':
    main()
