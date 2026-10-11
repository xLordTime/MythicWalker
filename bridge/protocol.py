"""Validated, deliberately bounded subset of Deimos-style instructions. No eval."""
import math
import re

KEYS = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ') | {'SPACEBAR', 'ENTER', 'ESC', 'PAGE_UP', 'PAGE_DOWN', 'UP_ARROW', 'DOWN_ARROW', 'LEFT_ARROW', 'RIGHT_ARROW', 'TAB'}

def number(value, low=-1_000_000, high=1_000_000):
    if isinstance(value, bool):
        raise ValueError('Bool ist keine Zahl.')
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f'Zahl muss zwischen {low} und {high} liegen.')
    return result

def xyz(values):
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        raise ValueError('Drei XYZ-Koordinaten erforderlich.')
    return [number(v) for v in values]

def key(value):
    if value not in KEYS:
        raise ValueError('Nicht unterstützte Taste.')
    return value

def text(value, limit=180):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('Leerer oder zu langer Text.')
    return value.strip()

def parse_script(source):
    if not isinstance(source, str) or len(source) > 16000:
        raise ValueError('Skript zu lang (max. 16 KB).')
    steps = []
    for line_no, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if len(steps) >= 200:
            raise ValueError('Maximal 200 Schritte.')
        if match := re.fullmatch(r'sleep\s+([\d.]+)', line):
            steps.append({'op': 'sleep', 'seconds': number(match[1], 0, 60), 'line': line_no})
            continue
        match = re.fullmatch(r'(mass|p[1-9]\d*)\s+(.+)', line)
        if not match:
            raise ValueError(f'Zeile {line_no}: Ziel mass oder p1/p2/… fehlt; Blocks/Loops werden noch nicht unterstützt.')
        target, body = match.groups()
        item = {'target': target, 'line': line_no}
        if m := re.fullmatch(r'sendkey\s+(\w+)(?:\s*,?\s+([\d.]+))?', body):
            item.update(op='key', key=key(m[1]), seconds=number(m[2] or .1, .01, 5))
        elif m := re.fullmatch(r'tp\s+XYZ\(\s*([^,]+),\s*([^,]+),\s*([^\)]+)\)', body):
            item.update(op='teleport', xyz=xyz(m.groups()))
        elif body == 'tp quest':item.update(op='quest_tp')
        elif m := re.fullmatch(r'(entitytp|clickwindow)\s+"([^"\n]+)"',body):
            item.update(op='entity_tp' if m[1]=='entitytp' else 'click_window',name=text(m[2]))
        elif m := re.fullmatch(r'speed\s+(\d+)',body):item.update(op='speed',percent=int(number(m[1],0,300)))
        elif body == 'restorespeed':item.update(op='restore_speed')
        elif body == 'waitforcombat completion':
            item.update(op='wait_combat', timeout=300)
        else:
            raise ValueError(f'Zeile {line_no}: Befehl nicht unterstützt. Erlaubt: sleep, sendkey, tp XYZ/quest, entitytp, clickwindow, speed, restorespeed, waitforcombat completion.')
        steps.append(item)
    if not steps:
        raise ValueError('Das Skript enthält keine Schritte.')
    return steps
