"""Persistent user blocks; defaults ship identically in web and EXE."""
import json
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
        if sum(len(v) for v in value.values() if isinstance(v,str))>262144:raise ValueError('Bibliothek zu groß (max. 256 KB).')
        compile_bot('sleep 0', {**self.defaults,**value})

    def update(self,value):
        self.validate(value)
        if self.path:
            tmp=self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(self.path)
        self.custom=dict(value)
        return self.custom

    def merged(self):return {**self.defaults,**self.custom}
