"""Wiz-Q-compatible launch arguments and PID-bound login; no remote services."""
import ctypes
from ctypes import wintypes as W
import os
from pathlib import Path
import subprocess
import sys
import time
from launcher_vault import REGIONS, SERVERS, LauncherError


def installations():
    found={}
    roots=[Path(os.environ.get(k,default))/'KingsIsle Entertainment' for k,default in [('PROGRAMDATA',r'C:\ProgramData'),('ProgramFiles(x86)',r'C:\Program Files (x86)'),('PROGRAMFILES',r'C:\Program Files')]]
    for root in roots:
        for r in REGIONS:
            p=root/('Wizard101' if r=='us' else f'Wizard101({r.upper()})')
            if (p/'Bin'/'WizardGraphicalClient.exe').is_file():found.setdefault(r,str(p))
    if sys.platform=='win32':
        import winreg
        for hive,sub in [(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'),(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),(winreg.HKEY_CURRENT_USER,r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall')]:
            try:
                with winreg.OpenKey(hive,sub) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            with winreg.OpenKey(key,winreg.EnumKey(key,i)) as entry:
                                name=winreg.QueryValueEx(entry,'DisplayName')[0]
                                path=Path(winreg.QueryValueEx(entry,'InstallLocation')[0])
                                if 'wizard101' not in name.lower() or not (path/'Bin'/'WizardGraphicalClient.exe').is_file():continue
                                r=next((r for r in REGIONS if r!='us' and f'({r})' in (name+' '+path.name).lower()),'us')
                                found.setdefault(r,str(path))
                        except OSError:continue
            except OSError:continue
    return found


def launch_args(region, directory):
    if region not in REGIONS:raise LauncherError('Unbekannte Region.')
    p=Path(directory)
    # Never execute remote UNC/WebDAV paths or arbitrary web-provided commands.
    if not p.is_absolute() or str(p).startswith(('\\\\','//')):raise LauncherError('Einen lokalen, absoluten Installationsordner wählen.')
    exe=p/'Bin'/'WizardGraphicalClient.exe'
    if not exe.is_file():raise LauncherError('Bin/WizardGraphicalClient.exe fehlt im gewählten Ordner.')
    return [str(exe),'-L',SERVERS[region],'12000','-A',region]


class NativeLauncher:
    def start(self, region, directory):
        if sys.platform!='win32':raise LauncherError('Spielstart benötigt Windows.')
        args=launch_args(region,directory)
        return subprocess.Popen(args,cwd=str(Path(directory)/'Bin'),shell=False)

    def login(self, process, account, wait, cancel):
        user=ctypes.WinDLL('user32',use_last_error=True)
        callback=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
        user.EnumWindows.argtypes=[callback,W.LPARAM];user.EnumWindows.restype=W.BOOL
        user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
        user.GetClassNameW.argtypes=[W.HWND,W.LPWSTR,ctypes.c_int]
        user.SendMessageTimeoutW.argtypes=[W.HWND,W.UINT,ctypes.c_size_t,ctypes.c_ssize_t,W.UINT,W.UINT,ctypes.POINTER(ctypes.c_size_t)]
        user.SendMessageTimeoutW.restype=ctypes.c_ssize_t
        def owned(hwnd):
            pid=W.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            name=ctypes.create_unicode_buffer(64);user.GetClassNameW(hwnd,name,64)
            return process.poll() is None and pid.value==process.pid and name.value=='Wizard Graphical Client'
        deadline=time.monotonic()+45;handle=None
        while time.monotonic()<deadline and not cancel.is_set():
            if process.poll() is not None:raise LauncherError('Das gestartete Spiel wurde vor dem Login beendet.')
            matches=[]
            def visit(hwnd,_):
                if owned(hwnd):matches.append(hwnd)
                return True
            user.EnumWindows(callback(visit),0)
            if matches:handle=matches[0];break
            cancel.wait(.25)
        if cancel.is_set():return False
        if not handle:raise LauncherError('Kein Fenster für den gestarteten Prozess gefunden (45 Sekunden).')
        if cancel.wait(wait):return False
        # Same WM_CHAR sequence as Wiz Q / WizWalker; never clipboard, command-line
        # credentials, account window titles, or keys sent to the foreground window.
        deadline=time.monotonic()+10
        for text in [account['username'],'\t',account['password'],'\r']:
            encoded=text.encode('utf-16-le')
            for i in range(0,len(encoded),2):
                if cancel.is_set():return False
                if time.monotonic()>deadline or not owned(handle):raise LauncherError('Login abgebrochen: Spielfenster nicht mehr bereit.')
                result=ctypes.c_size_t()
                if not user.SendMessageTimeoutW(handle,0x102,int.from_bytes(encoded[i:i+2],'little'),0,2,500,ctypes.byref(result)):
                    raise LauncherError('Spielfenster antwortet nicht. Login manuell prüfen.')
        return True
