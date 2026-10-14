"""Local-only vault and read-only Wiz Q compatibility (MIT, see notices)."""
import base64
import ctypes
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import sys
import time
import uuid
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

REGIONS = {'de':'Deutschland','us':'USA','fr':'Frankreich','it':'Italien',
           'gb':'Großbritannien','pl':'Polen','es':'Spanien','gr':'Griechenland'}
SERVERS = {r: ('login.us.wizard101.com' if r == 'us' else f'login-{r}.eu.wizard101.com') for r in REGIONS}

class LauncherError(ValueError):
    """Only fixed, non-secret messages may cross the local API."""


def dpapi(data, decrypt=False):
    if sys.platform != 'win32':
        raise LauncherError('Der Kontotresor benötigt Windows.')
    class Blob(ctypes.Structure):
        _fields_ = [('size',W.DWORD),('data',ctypes.POINTER(ctypes.c_byte))]
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]; kernel.LocalFree.restype = ctypes.c_void_p
    buf = ctypes.create_string_buffer(data)
    source = Blob(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_byte))); target = Blob()
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,W.DWORD,ctypes.POINTER(Blob)]
    fn.restype = W.BOOL
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):
        raise LauncherError('Windows konnte den Tresor nicht öffnen oder speichern. Derselbe Windows-Benutzer ist erforderlich.')
    try:return ctypes.string_at(target.data,target.size)
    finally:kernel.LocalFree(target.data)


def read_json(path):
    if path.stat().st_size > 2*1024*1024:
        raise LauncherError('Lokale Datei ist zu groß (maximal 2 MB).')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def account_row(row, ident=None):
    if not isinstance(row,dict):raise LauncherError('Ungültige Kontodaten.')
    result = {}
    for key,limit in [('name',80),('username',128),('password',256)]:
        v = row.get(key)
        if not isinstance(v,str) or not v.strip() or len(v)>limit or any(ord(c)<32 for c in v):
            raise LauncherError('Name, Benutzername und Passwort prüfen; keine Steuerzeichen verwenden.')
        result[key] = v if key == 'password' else v.strip()
    region = row.get('region','de')
    if region not in REGIONS:raise LauncherError('Unbekannte Region.')
    result.update(id=ident or uuid.uuid4().hex,region=region)
    return result


class Vault:
    def __init__(self, base=None, protector=dpapi):
        base = Path(base) if base is not None else Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))
        self.root = base/'WizQLauncher'
        self.path = self.root/'data'/'mythic-accounts.dpapi'
        self.settings_path = self.root/'mythic-launcher.json'
        self.protector = protector
        self.rows = None
        self.settings = {'paths':{},'login_wait':5}
        self.imported = False

    def unlock(self):
        self.root.joinpath('data').mkdir(parents=True,exist_ok=True)
        if self.path.exists():
            if self.path.stat().st_size > 2*1024*1024:raise LauncherError('Tresor ist zu groß.')
            data = json.loads(self.protector(self.path.read_bytes(),True))
            if data.get('version') != 1:raise LauncherError('Unbekanntes Tresorformat.')
            rows = data['accounts']
            if not isinstance(rows,list) or len(rows)>100:raise LauncherError('Ungültiger Tresor.')
            validated = [account_row(r,r['id']) for r in rows]
            if any(not isinstance(r['id'],str) or len(r['id'])!=32 for r in validated):raise LauncherError('Ungültige Konto-ID.')
            self.rows = validated;self.imported = bool(data.get('wizq_imported'))
        else:self.rows = []
        if self.settings_path.exists():
            config = read_json(self.settings_path)
            self.settings = {'paths':{r:p for r,p in config.get('paths',{}).items() if r in REGIONS and isinstance(p,str)},
                             'login_wait':max(2,min(30,int(config.get('login_wait',5))))}
        elif (self.root/'config.json').exists():
            config = read_json(self.root/'config.json')
            for r in REGIONS:
                p = config.get('region_install_'+r) or config.get('default_install' if r=='de' else 'default_install_us' if r=='us' else '')
                if isinstance(p,str) and p:self.settings['paths'][r] = p
        if not self.path.exists():self.save()

    def require(self):
        if self.rows is None:raise LauncherError('Tresor zuerst lokal entsperren.')

    def save(self):
        self.require()
        raw = json.dumps({'version':1,'accounts':self.rows,'wizq_imported':self.imported},ensure_ascii=False).encode()
        encrypted = self.protector(raw)
        self._atomic(self.path,encrypted)

    @staticmethod
    def _atomic(path, data):
        path.parent.mkdir(parents=True,exist_ok=True)
        temp = path.with_suffix(path.suffix+'.tmp')
        try:
            with temp.open('wb') as stream:
                stream.write(data);stream.flush();os.fsync(stream.fileno())
            temp.replace(path)
        finally:
            if temp.exists():temp.unlink()

    def lock(self):self.rows = None

    def public(self):
        self.require()
        return [{k:v for k,v in r.items() if k != 'password'} for r in self.rows]

    def put(self, row):
        self.require()
        ident = row.get('id'); existing = next((r for r in self.rows if r['id']==ident),None)
        if ident and existing is None:raise LauncherError('Konto nicht gefunden.')
        candidate = dict(row)
        if existing and not candidate.get('password'):candidate['password'] = existing['password']
        clean = account_row(candidate,ident)
        if any(r['id']!=ident and r['username']==clean['username'] and r['region']==clean['region'] for r in self.rows):
            raise LauncherError('Dieses Konto ist für die Region bereits vorhanden.')
        if not existing and len(self.rows)>=100:raise LauncherError('Maximal 100 Konten.')
        previous = self.rows
        self.rows = [clean if r['id']==ident else r for r in self.rows] if existing else self.rows+[clean]
        try:self.save()
        except Exception:self.rows = previous;raise

    def delete(self, ident):
        self.require()
        previous = self.rows
        self.rows = [r for r in self.rows if r['id']!=ident]
        if len(previous)==len(self.rows):raise LauncherError('Konto nicht gefunden.')
        try:self.save()
        except Exception:self.rows=previous;raise

    def import_wizq(self, password=''):
        self.require()
        path = self.root/'data'/'accounts.enc.json'
        if not path.exists():raise LauncherError('Keine Wiz-Q-Kontodatei in diesem lokalen Profil gefunden.')
        encrypted = read_json(path)
        config = read_json(self.root/'config.json') if (self.root/'config.json').exists() else {}
        try:
            if isinstance(encrypted,list):payload=encrypted
            else:
                secret = password
                mode = config.get('master_password_mode','password')
                expires = int(config.get('master_password_secret_expires',0) or 0)
                blob = config.get('master_password_secret_b64')
                if not secret and blob and (not expires or expires>time.time()):
                    raw = self.protector(base64.b64decode(blob,validate=True),True)
                    secret = raw if mode=='local' else raw.decode('utf-8')
                if not secret and mode=='placeholder':secret='0'
                if not secret:raise LauncherError('Wiz-Q-Masterpasswort eingeben; es wird nicht gespeichert.')
                if isinstance(secret,bytes):key=secret
                else:
                    count=int(encrypted.get('iterations',390000))
                    if not 100000<=count<=2000000:raise LauncherError('Nicht unterstützte Schlüsselableitung.')
                    salt=base64.b64decode(encrypted['salt'],validate=True)
                    if not 8<=len(salt)<=64:raise LauncherError('Ungültiges Salz.')
                    kdf=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=count)
                    key=base64.urlsafe_b64encode(kdf.derive(secret.encode('utf-8')))
                payload=json.loads(Fernet(key).decrypt(encrypted['data'].encode('ascii')))
            if not isinstance(payload,list) or len(payload)>100:raise LauncherError('Maximal 100 Konten pro Import.')
            clean=[account_row(r) for r in payload]
        except LauncherError:raise
        except (InvalidToken,ValueError,KeyError,TypeError,UnicodeError):
            raise LauncherError('Import fehlgeschlagen. Masterpasswort und Wiz-Q-Dateiformat prüfen.') from None
        previous,previous_imported=self.rows,self.imported
        known={(r['username'],r['region']) for r in self.rows};added=[]
        for r in clean:
            key=(r['username'],r['region'])
            if key not in known:added.append(r);known.add(key)
        if len(self.rows)+len(added)>100:raise LauncherError('Der Tresor darf maximal 100 Konten enthalten.')
        self.rows=self.rows+added;self.imported=True
        try:self.save()
        except Exception:self.rows,self.imported=previous,previous_imported;raise
        return len(added)

    def save_settings(self, paths, wait):
        self.require()
        if not isinstance(paths,dict) or set(paths)-set(REGIONS):raise LauncherError('Ungültige Regionen.')
        if any(not isinstance(p,str) or len(p)>1000 or any(ord(c)<32 for c in p) for p in paths.values()):raise LauncherError('Installationspfad prüfen.')
        if type(wait) is not int or not 2<=wait<=30:raise LauncherError('Login-Wartezeit: 2–30 Sekunden.')
        updated={'paths':{r:p.strip() for r,p in paths.items()},'login_wait':wait}
        self._atomic(self.settings_path,json.dumps(updated,ensure_ascii=False,indent=2).encode())
        self.settings=updated
