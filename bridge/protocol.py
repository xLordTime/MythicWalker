"""Validated, deliberately bounded subset of Deimos-style instructions. No eval."""
import math
import re

KEYS = {'Numeric_pad_2', 'Start_Mail', 'Applications', 'Browser_Search', 'ONE', 'LEFT_ARROW', 'Left_CONTROL', 'R', 'S', 'F6', 'Decimal', 'ENTER', 'Left_mouse', 'SPACEBAR', 'Attn', 'THREE', 'F7', 'HOME', 'SCROLL_LOCK', 'END', 'X', 'Z', 'Browser_Refresh', 'ALT', 'Right_SHIFT', 'F11', 'N', 'Numeric_pad_7', 'F12', 'Left_SHIFT', 'Numeric_pad_5', 'Add', 'Middle_mouse', 'O', 'Zoom', 'G', 'F20', 'F5', 'Play_Pause_Media', 'M', 'F16', 'Numeric_pad_6', 'Play', 'UP_ARROW', 'Separator', 'ESC', 'PRINT_SCREEN', 'Multiply', 'OEM_specific', 'INS', 'Control_break_processing', 'EXECUTE', 'F21', 'Select_Media', 'Browser_Favorites', 'W', 'F15', 'TAB', 'F2', 'RIGHT_ARROW', 'Numeric_pad_9', 'Right_Windows', 'Q', 'Start_Application_1', 'Computer_Sleep', 'F19', 'Left_Windows', 'P', 'PAGE_DOWN', 'Browser_Start_and_Home', 'FIVE', 'ZERO', 'DEL', 'Numeric_pad_8', 'Start_Application_2', 'L', 'Volume_Up', 'F13', 'CTRL', 'SELECT', 'Next_Track', 'Y', 'I', 'Numeric_pad_1', 'SHIFT', 'PAGE_UP', 'X2_mouse', 'Right_mouse', 'E', 'F1', 'Browser_Back', 'EIGHT', 'H', 'Browser_Forward', 'ExSel', 'K', 'Stop_Media', 'Numeric_pad_4', 'T', 'F8', 'V', 'Right_MENU', 'TWO', 'Divide', 'Browser_Stop', 'CAPS_LOCK', 'IME_PROCESS', 'NINE', 'Volume_Down', 'Left_MENU', 'F3', 'FOUR', 'F', 'Undefined', 'PAUSE', 'Volume_Mute', 'Numeric_pad_3', 'CrSel', 'Reserved', 'J', 'D', 'X1_mouse', 'F4', 'F23', 'Previous_Track', 'CLEAR', 'F24', 'F17', 'Numeric_pad_0', 'Subtract', 'PA1', 'NUM_LOCK', 'BACKSPACE', 'C', 'HELP', 'F18', 'F10', 'DOWN_ARROW', 'F14', 'SIX', 'SEVEN', 'F22', 'B', 'F9', 'Clear', 'A', 'U', 'Right_CONTROL', 'Erase_EOF', 'PRINT'}

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

def _parse_flat(source):
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
        elif body == 'tp navquest':item.update(op='navmap_tp',timeout=20)
        elif body == 'freecam':item.update(op='freecam')
        elif body == 'tp camera':item.update(op='camera_tp')
        elif body == 'pass':item.update(op='pass')
        elif body == 'waitforloading completion':item.update(op='wait_loading',timeout=120)
        elif m := re.fullmatch(r'waitforwindow\s+"([^"\n]+)"\s+(\d+)',body):item.update(op='wait_window',name=text(m[1]),timeout=int(number(m[2],1,120)))
        elif m := re.fullmatch(r'tp nearest\s+"([^"\n]+)"',body):item.update(op='nearest_entity',query=text(m[1]))
        elif m := re.fullmatch(r'cast\s+"([^"\n]+)"\s+@(self|enemy|none)',body):item.update(op='cast',name=text(m[1]),card_target=m[2])
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


def parse_script(source):
    if not isinstance(source,str) or len(source)>16000:raise ValueError('Skript zu lang (max. 16 KB).')
    stack=[{'steps':[],'count':1}]
    for line_no,raw in enumerate(source.splitlines(),1):
        line=raw.strip()
        if not line or line.startswith('#'):continue
        match=re.fullmatch(r'times\s+(\d+)\s*\{',line)
        if match:
            count=int(number(match[1],1,50))
            if len(stack)>=4:raise ValueError('Maximal drei verschachtelte Wiederholungen.')
            stack.append({'steps':[],'count':count});continue
        if line=='}':
            if len(stack)==1:raise ValueError('Unerwartete schließende Klammer.')
            frame=stack.pop()
            if not frame['steps']:raise ValueError('Leere Wiederholung.')
            expanded=frame['steps']*frame['count']
            if len(stack[-1]['steps'])+len(expanded)>200:raise ValueError('Maximal 200 Schritte inklusive Wiederholungen.')
            stack[-1]['steps'].extend(expanded);continue
        item=_parse_flat(line)[0];item['line']=line_no
        stack[-1]['steps'].append(item)
        if len(stack[-1]['steps'])>200:raise ValueError('Maximal 200 Schritte.')
    if len(stack)!=1:raise ValueError('Wiederholung nicht geschlossen.')
    if not stack[0]['steps']:raise ValueError('Das Skript enthält keine Schritte.')
    return stack[0]['steps']
