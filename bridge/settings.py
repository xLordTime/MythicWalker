"""Validated settings, including migration of the earlier browser/bridge schema."""
import copy
import json
import math
import re
from pathlib import Path

BINDINGS={'scan':'Ctrl+Alt+S','hook':'Ctrl+Alt+H','unhook':'Ctrl+Alt+U','interact':'X','sync':'F8','quest_tp':'F7','quest_all':'F6','speed_toggle':'F5','combat_toggle':'9','dialogue_toggle':'F4','questing_toggle':'F3','sigil_toggle':'F2','freecam':'F1','camera_tp':'Shift+F1','run_script':'Ctrl+Alt+R','stop':'Ctrl+Alt+F8','forward':'Ctrl+Alt+W'}
ACTIONS=tuple(BINDINGS)
DEFAULTS={'global_hotkeys':True,'poll_seconds':2,'key_seconds':0.2,'bindings':BINDINGS,
 'movement':{'scope':'all','speed_percent':100,'navmap_target':'auto','navmap_timeout':20,'freecam_scope':'leader'},
 'automation':{'interval':1,'max_minutes':15,'combat_rules':'any<aoe>@enemy\npass','combat_pass':True,'quest_accept':True,'quest_forward':False,'quest_distance':150,'sigil_rejoin':True,'sigil_confirm':True,'sigil_cooldown':5}}

def combo(value):
    if not isinstance(value,str):raise ValueError('Shortcut muss Text sein.')
    if not value.strip():return ''
    parts=re.sub(r'\s','',value).upper().replace('NINE','9').split('+');key=parts.pop();mods=set(parts)
    if len(mods)!=len(parts) or not mods<={'CTRL','ALT','SHIFT'}:raise ValueError('Nur Ctrl, Alt und Shift sind erlaubt.')
    if not re.fullmatch(r'[A-Z0-9]|F([1-9]|10|11)|SPACE|ENTER|ESC|TAB',key):raise ValueError('Nicht unterstützte Taste (F12 ist reserviert).')
    if not mods and key not in {'X','9'} and not re.fullmatch(r'F([1-9]|10|11)',key):raise ValueError('Diese Taste benötigt Ctrl, Alt oder Shift.')
    return '+'.join([m.title() for m in ('CTRL','ALT','SHIFT') if m in mods]+[key])

def number(n,lo,hi,name):
    if type(n) not in (float,int) or not math.isfinite(n) or not lo<=n<=hi:raise ValueError(f'{name}: erlaubt sind {lo} bis {hi}.')
    return n

def combat_rules(source):
    if not isinstance(source,str) or len(source)>4000:raise ValueError('Kampfregeln: maximal 4000 Zeichen.')
    rows=[]
    for raw in source.splitlines():
        line=raw.strip()
        if not line or line.startswith('#'):continue
        if line=='pass':rows.append({'name':'pass','target':'none'});continue
        match=re.fullmatch(r'([^@\n]{1,180})@(self|enemy|none)',line)
        if not match:raise ValueError('Kampfregel: Kartenname@self/enemy/none, any<aoe>@enemy oder pass.')
        name=match[1].strip()
        if '<' in name and name!='any<aoe>':raise ValueError('Unterstützter Filter: any<aoe>.')
        rows.append({'name':name,'target':match[2]})
    if not 1<=len(rows)<=30:raise ValueError('1–30 Kampfregeln erforderlich.')
    return rows

def validate(data):
    if not isinstance(data,dict) or set(data)!=set(DEFAULTS):raise ValueError('Ungültiges Settings-Format.')
    result=copy.deepcopy(data)
    if type(data['global_hotkeys']) is not bool:raise ValueError('Global-Schalter muss boolesch sein.')
    number(data['poll_seconds'],.5,10,'Status-Intervall');number(data['key_seconds'],.01,5,'Tastendauer')
    if not isinstance(data['bindings'],dict) or set(data['bindings'])!=set(ACTIONS):raise ValueError('Ungültige Shortcut-Aktionen.')
    result['bindings']={a:combo(data['bindings'][a]) for a in ACTIONS};used=[v for v in result['bindings'].values() if v]
    if len(used)!=len(set(used)):raise ValueError('Jeder Shortcut darf nur einer Aktion zugewiesen sein.')
    m=data['movement'];a=data['automation']
    if not isinstance(m,dict) or set(m)!=set(DEFAULTS['movement']):raise ValueError('Ungültige Movement-Einstellungen.')
    if m['scope'] not in {'all','selected'} or m['navmap_target'] not in {'auto','own','leader'} or m['freecam_scope'] not in {'leader','selected'}:raise ValueError('Ungültiger Movement-Modus.')
    n=number(m['speed_percent'],0,300,'Geschwindigkeit')
    if int(n)!=n:raise ValueError('Geschwindigkeit muss ganzzahlig sein.')
    number(m['navmap_timeout'],3,25,'Navmap-Zeitlimit')
    if not isinstance(a,dict) or set(a)!=set(DEFAULTS['automation']):raise ValueError('Ungültige Automatik-Einstellungen.')
    for k in ['combat_pass','quest_accept','quest_forward','sigil_rejoin','sigil_confirm']:
        if type(a[k]) is not bool:raise ValueError(k+' muss boolesch sein.')
    for k,lo,hi in [('interval',.5,5),('max_minutes',1,60),('quest_distance',25,1000),('sigil_cooldown',2,60)]:number(a[k],lo,hi,k)
    combat_rules(a['combat_rules'])
    return result

def migrate(data):
    result=copy.deepcopy(DEFAULTS)
    if not isinstance(data,dict):return result
    for k in DEFAULTS:
        if k in data:
            if isinstance(DEFAULTS[k],dict) and isinstance(data[k],dict):result[k].update({n:v for n,v in data[k].items() if n in DEFAULTS[k]})
            else:result[k]=data[k]
    return validate(result)

class Settings:
    def __init__(self,path=None):
        self.path=Path(path) if path else None;self.data=copy.deepcopy(DEFAULTS)
        if self.path and self.path.exists():
            try:self.data=migrate(json.loads(self.path.read_text(encoding='utf-8')))
            except (ValueError,OSError):pass
    def save(self,data):
        value=validate(data)
        if self.path:
            tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2),encoding='utf-8');tmp.replace(self.path)
        self.data=value;return value
