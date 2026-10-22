"""Native Windows folder picker, on a worker thread, with cooperative shutdown."""
import ctypes
from ctypes import wintypes as W
from pathlib import Path
import sys
from sound_files import SoundError


def choose_folder(initial='', owner=0, cancel=None):
    if sys.platform!='win32':raise SoundError('Ordnerdialog benötigt die Windows-Bridge. Pfad stattdessen einfügen.')
    shell=ctypes.WinDLL('shell32',use_last_error=True)
    ole=ctypes.WinDLL('ole32',use_last_error=True)
    user=ctypes.WinDLL('user32',use_last_error=True)
    CALLBACK=ctypes.WINFUNCTYPE(ctypes.c_int,W.HWND,W.UINT,ctypes.c_ssize_t,ctypes.c_ssize_t)
    TIMER=ctypes.WINFUNCTYPE(None,W.HWND,W.UINT,ctypes.c_size_t,W.DWORD)
    class Browse(ctypes.Structure):
        _fields_=[('owner',W.HWND),('root',ctypes.c_void_p),('display',W.LPWSTR),('title',W.LPCWSTR),
                  ('flags',W.UINT),('callback',CALLBACK),('param',ctypes.c_ssize_t),('image',ctypes.c_int)]
    ole.OleInitialize.argtypes=[ctypes.c_void_p];ole.OleInitialize.restype=ctypes.c_long
    ole.OleUninitialize.argtypes=[];ole.OleUninitialize.restype=None
    ole.CoTaskMemFree.argtypes=[ctypes.c_void_p];ole.CoTaskMemFree.restype=None
    shell.SHBrowseForFolderW.argtypes=[ctypes.POINTER(Browse)];shell.SHBrowseForFolderW.restype=ctypes.c_void_p
    shell.SHGetPathFromIDListEx.argtypes=[ctypes.c_void_p,W.LPWSTR,W.DWORD,W.DWORD];shell.SHGetPathFromIDListEx.restype=W.BOOL
    user.SendMessageW.argtypes=[W.HWND,W.UINT,ctypes.c_size_t,ctypes.c_ssize_t];user.SendMessageW.restype=ctypes.c_ssize_t
    user.SetTimer.argtypes=[W.HWND,ctypes.c_size_t,W.UINT,TIMER];user.SetTimer.restype=ctypes.c_size_t
    user.KillTimer.argtypes=[W.HWND,ctypes.c_size_t];user.KillTimer.restype=W.BOOL
    user.PostMessageW.argtypes=[W.HWND,W.UINT,ctypes.c_size_t,ctypes.c_ssize_t];user.PostMessageW.restype=W.BOOL
    user.SetForegroundWindow.argtypes=[W.HWND];user.SetForegroundWindow.restype=W.BOOL
    if ole.OleInitialize(None)<0:raise SoundError('Windows-Ordnerdialog nicht verfügbar. Pfad stattdessen einfügen.')
    opened=False;timer_id=0;dialog=None;pidl=None;timer_error=False
    try:
        start=None
        if isinstance(initial,str) and initial and not initial.startswith(('\\\\','//')):
            p=Path(initial)
            if p.is_absolute() and p.is_dir():start=ctypes.create_unicode_buffer(str(p))
        @TIMER
        def tick(hwnd,message,ident,time):
            if cancel is not None and cancel.is_set():user.PostMessageW(hwnd,0x0010,0,0)
        @CALLBACK
        def callback(hwnd,message,param,data):
            nonlocal opened,timer_id,dialog,timer_error
            if message==1:  # BFFM_INITIALIZED
                opened=True;dialog=hwnd
                if start is not None:user.SendMessageW(hwnd,0x400+103,1,ctypes.cast(start,ctypes.c_void_p).value)
                timer_id=user.SetTimer(hwnd,0x4d57,100,tick)
                if not timer_id:
                    timer_error=True;user.PostMessageW(hwnd,0x0010,0,0)
                user.SetForegroundWindow(hwnd)
            return 0
        display=ctypes.create_unicode_buffer(260)
        # File-system folders, editable/resizable dialog, no new-folder button.
        info=Browse(owner,None,ctypes.cast(display,W.LPWSTR),'Wizard101-Ordner wählen (auch Bin oder Data/GameData möglich)',0x251,callback,0,0)
        pidl=shell.SHBrowseForFolderW(ctypes.byref(info))
        if not opened or timer_error:raise SoundError('Windows-Ordnerdialog konnte nicht geöffnet werden. Pfad stattdessen einfügen.')
        if not pidl:return None
        result=ctypes.create_unicode_buffer(32768)
        if not shell.SHGetPathFromIDListEx(pidl,result,len(result),0):raise SoundError('Einen lokalen Dateiordner auswählen.')
        return result.value
    finally:
        if dialog and timer_id:user.KillTimer(dialog,timer_id)
        if pidl:ole.CoTaskMemFree(pidl)
        ole.OleUninitialize()
