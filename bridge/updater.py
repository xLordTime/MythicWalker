"""Public GitHub release updates, installed alongside the running executable."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

MAX_EXE = 100 * 1024 * 1024

def version_tuple(value):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-beta\.(\d+))?',str(value))
    if not match:raise ValueError('Ungültige Release-Version.')
    return tuple(map(int,match.groups()[:3]))

def release_rank(value):
    base=version_tuple(value)
    match=re.search(r'-beta\.(\d+)$',str(value))
    return base+(0,int(match[1])) if match else base+(1,0)

def repository(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',value):
        raise ValueError('Ungültiges GitHub-Repository.')
    if any(part in {'.','..'} for part in value.split('/')):raise ValueError('Ungültiges GitHub-Repository.')
    return value

def read_url(url,limit):
    request=urllib.request.Request(url,headers={'User-Agent':'MythicWalker-Bridge','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request,timeout=20) as response:
        if not response.url.startswith('https://'): raise ValueError('Update benötigt HTTPS.')
        data=response.read(limit+1)
    if len(data)>limit: raise ValueError('Update-Datei zu groß.')
    return data

def release_asset(release,name,repo):
    assets=[a for a in release.get('assets',[]) if a.get('name')==name]
    if len(assets)!=1: raise ValueError('Release-Datei fehlt: '+name)
    url=assets[0].get('browser_download_url','')
    if not url.startswith(f'https://github.com/{repo}/releases/download/'):
        raise ValueError('Release-Datei stammt nicht aus dem Update-Repository.')
    return url

def check_and_install(repo,current,install_root,report,fetch=read_url,channel='stable'):
    repo=repository(repo)
    report('Updates prüfen','GitHub · '+repo)
    if channel=='beta':
        candidates=json.loads(fetch(f'https://api.github.com/repos/{repo}/releases?per_page=30',1024*1024))
        valid=[]
        for item in candidates:
            if item.get('draft'):continue
            try:release_rank(item.get('tag_name'))
            except ValueError:continue
            valid.append(item)
        if not valid:return None
        release=max(valid,key=lambda item:release_rank(item['tag_name']))
    else:
        release=json.loads(fetch(f'https://api.github.com/repos/{repo}/releases/latest',1024*1024))
        if release.get('draft') or release.get('prerelease'):return None
    latest=release.get('tag_name'); numbers=version_tuple(latest)
    if release_rank(latest)<=release_rank(current):
        report('Bridge aktuell','Version '+current);return None
    manifest=json.loads(fetch(release_asset(release,'bridge-release.json',repo),16000))
    if version_tuple(manifest.get('version'))!=numbers or manifest.get('filename')!='MythicWalker.exe' or not re.fullmatch(r'[a-f0-9]{64}',str(manifest.get('sha256'))):
        raise ValueError('Ungültiges Update-Manifest.')
    folder=Path(install_root)/'versions'/str(latest).removeprefix('v');folder.mkdir(parents=True,exist_ok=True)
    destination=folder/'MythicWalker.exe'
    def valid(data):return data.startswith(b'MZ') and len(data)<=MAX_EXE and hashlib.sha256(data).hexdigest()==manifest['sha256']
    if destination.exists() and valid(destination.read_bytes()): return destination
    report('Update laden','Version '+str(latest))
    payload=fetch(release_asset(release,'MythicWalker.exe',repo),MAX_EXE)
    if not valid(payload): raise ValueError('Update-Prüfsumme oder EXE-Format stimmt nicht.')
    tmp=folder/'MythicWalker.download';tmp.write_bytes(payload);tmp.replace(destination)
    report('Update bereit','Version '+str(latest))
    return destination

def launch_update(path):
    subprocess.Popen([str(path),'--updated'],cwd=str(path.parent),close_fds=True)
