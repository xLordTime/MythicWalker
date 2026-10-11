"""Block-aware bot compiler and cancellable interpreter. Never executes Python."""
import asyncio
import re
from protocol import _parse_flat, number

NAME = r'[A-Za-z_][A-Za-z0-9_]{0,63}'


def compile_bot(source, library=None):
    if not isinstance(source, str) or len(source) > 65536:
        raise ValueError('Bot zu lang (max. 64 KB).')
    if library is None: library = {}
    if not isinstance(library, dict) or len(library) > 100:
        raise ValueError('Maximal 100 Bibliotheksblöcke.')
    blocks = {}
    total = 0

    def parse(code, library_name=None):
        nonlocal total
        if not isinstance(code, str) or len(code) > 16000 and library_name:
            raise ValueError('Bibliotheksblock zu lang (max. 16 KB).')
        lines = [(i, s.strip()) for i, s in enumerate(code.splitlines(), 1) if s.strip() and not s.strip().startswith('#')]
        # Keep braces in quoted strings untouched; allow the usual } else { line.
        lines = [part for i, s in lines for part in ([(i, '}'), (i, 'else {')] if re.fullmatch(r'}\s*else\s*{', s) else [(i, s)])]
        pos = 0

        def body(depth=0, loop_depth=0, closing=False):
            nonlocal pos, total
            nodes = []
            if depth > 12: raise ValueError('Maximal 12 verschachtelte Ebenen.')
            while pos < len(lines):
                line, s = lines[pos]; pos += 1
                total += 1
                if total > 2000: raise ValueError('Maximal 2000 Anweisungen einschließlich Bibliothek.')
                if s == '}':
                    if not closing: raise ValueError(f'Zeile {line}: Unerwartete Klammer.')
                    return nodes
                m = re.fullmatch(r'block\s+('+NAME+r')\s*{', s)
                if m:
                    if depth: raise ValueError('Blöcke nur auf oberster Ebene definieren.')
                    name = m[1]
                    if name in local: raise ValueError('Block doppelt definiert: '+name)
                    local[name] = body(depth+1, 0, True); continue
                m = re.fullmatch(r'(times\s+(\d+)|loop|while\s+(.+)|until\s+(.+)|if\s+(.+))\s*{', s)
                if m:
                    kind = s.split()[0]
                    node = {'op':kind, 'line':line}
                    if kind == 'times': node['count'] = int(number(m[2], 1, 999999))
                    elif kind in {'if','while','until'}: node['condition'] = condition((m[5] or m[3] or m[4]).strip(), line)
                    node['body'] = body(depth+1, loop_depth+(kind!='if'), True)
                    if not node['body']: raise ValueError(f'Zeile {line}: Leerer Block.')
                    if kind == 'if' and pos < len(lines) and lines[pos][1] == 'else {':
                        pos += 1; node['else'] = body(depth+1, loop_depth, True)
                    nodes.append(node); continue
                if m := re.fullmatch(r'call\s+('+NAME+r')', s):
                    nodes.append({'op':'call','name':m[1],'line':line}); continue
                if s in {'break','exitloop'}:
                    if not loop_depth: raise ValueError(f'Zeile {line}: break benötigt eine Schleife.')
                    nodes.append({'op':'break','line':line}); continue
                # Expertmode omits "mass" for commands addressed to the selection.
                statement = s if re.match(r'^(mass|p[1-9]\d*|sleep)\s', s) else 'mass '+s
                m = re.fullmatch(r'(mass|p[1-9]\d*)\s+(tp closestmob|waitforzonechange completion)', statement)
                if m:
                    nodes.append({'op':'closest_mob' if m[2]=='tp closestmob' else 'wait_zone','target':m[1], 'line':line,'timeout':120}); continue
                try: node = _parse_flat(statement)[0]
                except ValueError as exc: raise ValueError(f'Zeile {line}: {exc}') from None
                node['line'] = line; nodes.append(node)
            if closing: raise ValueError('Block nicht geschlossen.')
            return nodes

        local = {}
        nodes = body()
        if library_name:
            if nodes and local: raise ValueError('Ein Bibliothekseintrag enthält entweder einen Block oder dessen Inhalt.')
            if local:
                if set(local) != {library_name}: raise ValueError('Blockname muss dem Bibliotheksnamen entsprechen: '+library_name)
                return local[library_name]
            return nodes
        return nodes, local

    def condition(s, line):
        m = re.fullmatch(r'(not\s+)?(?:(any|mass|p[1-9]\d*)\s+)?(incombat|loading)', s)
        if not m: raise ValueError(f'Zeile {line}: Bedingung nicht unterstützt: {s}')
        return {'not':bool(m[1]), 'target':m[2] or 'any','test':m[3]}

    for name, code in library.items():
        if not isinstance(name,str) or not re.fullmatch(NAME,name): raise ValueError('Ungültiger Bibliotheksname.')
        blocks[name] = parse(code, name)
    nodes, local = parse(source)
    blocks.update(local)  # Explicit bot definitions override defaults.
    if not nodes: raise ValueError('Der Bot enthält keine ausführbaren Anweisungen.')

    def calls(seq):
        for n in seq:
            if n['op']=='call': yield n['name']
            yield from calls(n.get('body', [])); yield from calls(n.get('else', []))
    for seq in [nodes, *blocks.values()]:
        for name in calls(seq):
            if name not in blocks: raise ValueError('Unbekannter Block: '+name)
    depths={}
    def cycle(name, active):
        if name in active:raise ValueError('Rekursiver Blockaufruf: '+' → '.join([*active,name]))
        if name in depths:return depths[name]
        length=1+max((cycle(other,[*active,name]) for other in calls(blocks[name])),default=0)
        if length>16:raise ValueError('Maximal 16 verschachtelte Blockaufrufe.')
        depths[name]=length
        return length
    for name in blocks:cycle(name, [])
    return {'body':nodes, 'blocks':blocks, 'instructions':total}


def walk_nodes(program):
    def walk(seq):
        for node in seq:
            yield node
            yield from walk(node.get('body', [])); yield from walk(node.get('else', []))
    yield from walk(program['body'])
    for seq in program['blocks'].values(): yield from walk(seq)


class BreakLoop(Exception): pass


async def interpret(program, execute, check, progress):
    """Loops stay compact. Always yield, including sleep-free loops, for Stop."""
    count = 0
    async def visit(seq):
        nonlocal count
        for node in seq:
            await asyncio.sleep(0)
            count += 1
            await progress(node, count)
            op = node['op']
            if op == 'call': await visit(program['blocks'][node['name']])
            elif op == 'break': raise BreakLoop()
            elif op == 'if': await visit(node['body'] if await check(node['condition']) else node.get('else', []))
            elif op in {'times','loop','while','until'}:
                iteration = 0
                while True:
                    if op == 'times' and iteration >= node['count']: break
                    if op in {'while','until'} and (await check(node['condition'])) == (op=='until'): break
                    try: await visit(node['body'])
                    except BreakLoop: break
                    iteration += 1
                    await asyncio.sleep(.01)
            else: await execute(node)
    await visit(program['body'])
