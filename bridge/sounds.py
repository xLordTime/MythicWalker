"""Paired, local-only sound file commands; long disk operations run as jobs."""
import asyncio
import base64
import ctypes
from ctypes import wintypes as W
import os
from pathlib import Path
import sys
import threading
from sound_files import SoundStore, SoundError, MAX_AUDIO
from sound_picker import choose_folder


def require_game_closed():
    if sys.platform!='win32':raise SoundError('Dateiänderungen benötigen die Windows-Bridge.')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    class Entry(ctypes.Structure):
        _fields_=[('size',W.DWORD),('usage',W.DWORD),('pid',W.DWORD),('heap',ctypes.c_size_t),('module',W.DWORD),('threads',W.DWORD),('parent',W.DWORD),('priority',W.LONG),('flags',W.DWORD),('name',W.WCHAR*260)]
    kernel.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD];kernel.CreateToolhelp32Snapshot.restype=W.HANDLE
    kernel.Process32FirstW.argtypes=[W.HANDLE,ctypes.POINTER(Entry)];kernel.Process32FirstW.restype=W.BOOL
    kernel.Process32NextW.argtypes=[W.HANDLE,ctypes.POINTER(Entry)];kernel.Process32NextW.restype=W.BOOL
    kernel.CloseHandle.argtypes=[W.HANDLE];kernel.CloseHandle.restype=W.BOOL
    snap=kernel.CreateToolhelp32Snapshot(2,0)
    if snap==ctypes.c_void_p(-1).value:raise SoundError('Windows-Prozessliste nicht lesbar. Keine Dateiänderung.')
    try:
        entry=Entry();entry.size=ctypes.sizeof(entry)
        if not kernel.Process32FirstW(snap,ctypes.byref(entry)):raise SoundError('Windows-Prozessliste nicht lesbar.')
        while True:
            name=entry.name.casefold()
            if name in {'wizardgraphicalclient.exe','wizard101.exe','wizardlauncher.exe','patchclient.exe'}:
                raise SoundError('Alle Wizard101-Clients und den offiziellen Launcher vollständig schließen. Danach erneut anwenden.')
            if not kernel.Process32NextW(snap,ctypes.byref(entry)):
                if ctypes.get_last_error()!=18:raise SoundError('Prozessprüfung unvollständig. Keine Dateiänderung.')
                break
    finally:kernel.CloseHandle(snap)


class Sounds:
    def __init__(self,bridge,root=None,guard=None,picker=None):
        self.bridge=bridge;self.lock=asyncio.Lock();self.job=None;self.seq=0
        self.picker=picker or choose_folder;self.picker_cancel=threading.Event()
        self.status={'running':False,'message':'Bereit.','id':0,'result':None,'error':None}
        self.store=SoundStore(root or Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'MythicWalker'/'sounds',guard or require_game_closed)

    @property
    def running(self):return bool(self.job and not self.job.done())

    def progress(self,message):self.status={**self.status,'message':message}

    async def dispatch(self,op,args):
        if op=='sound_status':return dict(self.status)
        if getattr(self.bridge,'shutting_down',False):raise SoundError('Bridge wird beendet. Keine neue Dateioperation möglich.')
        if self.bridge.demo:raise SoundError('Sound-Dateien benötigen die Live-Bridge.')
        async with self.lock:
            if getattr(self.bridge,'shutting_down',False):raise SoundError('Bridge wird beendet. Keine neue Dateioperation möglich.')
            if self.running:raise SoundError('Eine Sound-Dateioperation läuft. Status abwarten.')
            if op=='sound_detect':
                from launcher_native import installations
                return {'paths':await asyncio.to_thread(installations)}
            if op=='sound_config':return await asyncio.to_thread(self.store.configure,args.get('path'))
            if op=='sound_archives':return await asyncio.to_thread(self.store.archives)
            if op=='sound_changes':return await asyncio.to_thread(self.store.changes)
            if op=='sound_files':return await asyncio.to_thread(self.store.files,args.get('archive'),args.get('query',''),args.get('offset',0))
            if op=='sound_inspect':return await asyncio.to_thread(self.store.inspect,args.get('archive'),args.get('name'))
            if op not in ('sound_apply','sound_restore','sound_search','sound_choose_folder'):raise SoundError('Unbekannter Sound-Befehl.')
            search=op=='sound_search';browse=op=='sound_choose_folder';writes=not search and not browse
            if writes and self.bridge.launcher and self.bridge.launcher.progress['running']:raise SoundError('Launcher-Startvorgang zuerst stoppen.')
            restore=op=='sound_restore';data=b''
            if not restore and writes:
                raw=args.get('data')
                if not isinstance(raw,str) or len(raw)>4*MAX_AUDIO//3+4:raise SoundError('Sound zu groß (3 MB).')
                try:data=base64.b64decode(raw,validate=True)
                except Exception as exc:raise SoundError('Sound-Übertragung ungültig.') from exc
            expected=args.get('expected')
            if writes and (not isinstance(expected,str) or len(expected)!=64):raise SoundError('Zuerst Original-Sound prüfen.')
            query=args.get('query','')
            if search and (not isinstance(query,str) or len(query)>150):raise SoundError('Suche ungültig.')
            if writes:self.store.guard()
            if browse:self.picker_cancel.clear()
            self.seq+=1
            self.status={'running':True,'message':'Ordnerdialog auf deinem PC öffnen …' if browse else 'Sound-Suche wird vorbereitet …' if search else 'Dateioperation wird vorbereitet …','kind':'folder' if browse else 'search' if search else 'restore' if restore else 'apply','id':self.seq,'result':None,'error':None}
            async def run():
                try:
                    if browse:
                        initial=str(self.store.game) if self.store.game else args.get('path','')
                        owner=getattr(getattr(self.bridge,'widget',None),'hwnd',0)
                        chosen=await asyncio.to_thread(self.picker,initial,owner,self.picker_cancel)
                        if chosen and not self.picker_cancel.is_set():
                            result=await asyncio.to_thread(self.store.configure,chosen);message=f"Ordner übernommen. {len(result['archives'])} WAD-Archive gefunden."
                        else:result={'cancelled':True};message='Ordnerauswahl abgebrochen. Der bisherige Ordner bleibt erhalten.'
                    elif search:
                        result=await asyncio.to_thread(self.store.search,query,self.progress)
                        message=f"{result['total']} Treffer in {result['archives']} Archiven."
                    else:
                        result=await asyncio.to_thread(self.store.replace,args.get('archive'),args.get('name'),data,expected,args.get('label',''),restore,self.progress)
                        message='Original wiederhergestellt.' if restore else 'Sound ersetzt. Spiel jetzt neu starten.'
                    self.status={**self.status,'running':False,'message':message,'result':result}
                except Exception as exc:
                    message=str(exc) if isinstance(exc,SoundError) else 'Ordnerauswahl fehlgeschlagen. Pfad stattdessen einfügen.' if browse else 'Sound-Suche fehlgeschlagen. Installation und Leserechte prüfen.' if search else 'Dateioperation fehlgeschlagen. Speicherplatz, Schreibrechte und Sicherungsjournal prüfen.'
                    self.status={**self.status,'running':False,'message':message,'error':message}
            self.job=asyncio.create_task(run())
            return {'started':True,'id':self.seq}

    async def close(self):
        # Finish the atomic operation before exiting; never abandon a worker thread.
        self.picker_cancel.set()
        if self.job:await asyncio.shield(self.job)
