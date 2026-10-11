import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from version import VERSION, CHANNEL, RELEASE_TAG
path=Path(sys.argv[1])
data=path.read_bytes()
if not data.startswith(b'MZ'):raise SystemExit('Keine Windows-EXE.')
(path.parent/'bridge-release.json').write_text(json.dumps({'version':VERSION,'tag':RELEASE_TAG,'channel':CHANNEL,'filename':'MythicWalker.exe','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)},indent=2),encoding='utf-8')
print('Release manifest:',VERSION,len(data),'bytes')
