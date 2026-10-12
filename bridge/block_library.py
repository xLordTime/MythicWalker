"""Persistent user blocks; defaults ship identically in web and EXE."""
import json
import re
from pathlib import Path
from botlang import compile_bot

class BlockLibrary:
    def __init__(self, defaults, path=None):
        self.defaults = {b['name']:b['source'] for b in defaults}
        self.path = Path(path) if path else None
        self.custom = {}
        if self.path and self.path.exists():
            try:
                value=json.loads(self.path.read_text(encoding='utf-8'))
                self.validate(value);self.custom=value
            except (ValueError,OSError): pass

    def validate(self, value):
        if not isinstance(value,dict) or len(value)>90:raise ValueError('Maximal 90 eigene Bibliotheksblöcke.')
        if any(not isinstance(name,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}',name) for name in value):raise ValueError('Ungültiger Blockname.')
        if any(not isinstance(source,str) or len(source)>16000 for source in value.values()):raise ValueError('Blockinhalt: maximal 16 KB.')
        if sum(len(v) for v in value.values() if isinstance(v,str))>262144:raise ValueError('Bibliothek zu groß (max. 256 KB).')
        try:compile_bot('sleep 0', {**self.defaults,**value})
        except ValueError:
            from expert import compile_expert
            for name in value:compile_expert('call '+name,{**self.defaults,**value})

    def update(self,value):
        self.validate(value)
        if self.path:
            tmp=self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(self.path)
        self.custom=dict(value)
        return self.custom

    def merged(self):return {**self.defaults,**self.custom}
