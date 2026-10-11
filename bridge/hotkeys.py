"""Registered hotkeys are active only while a hooked game window is foreground."""
import ctypes
from ctypes import wintypes
import sys
import threading

def key_code(key):
    if key.startswith('F') and key[1:].isdigit():return 0x70+int(key[1:])-1
    return {'SPACE':0x20,'ENTER':0x0D,'ESC':0x1B,'TAB':0x09}.get(key,ord(key) if len(key)==1 else 0)

class Hotkeys:
    def __init__(self):
        self.thread=None;self.stop_event=threading.Event();self.status=self.empty()
    def empty(self):return {'supported':sys.platform=='win32','active':[],'errors':{},'game_only':True}
    def stop(self):
        self.stop_event.set()
        if self.thread:self.thread.join(timeout=2)
        self.thread=None;self.status=self.empty()
    def start(self,bindings,callback,window_handles=None,status_callback=None):
        self.stop()
        if sys.platform!='win32':return self.status
        self.stop_event.clear();ready=threading.Event();handles=set(window_handles or [])
        def worker():
            registered={}
            try:
                user=ctypes.WinDLL('user32',use_last_error=True)
                user.RegisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int,wintypes.UINT,wintypes.UINT];user.RegisterHotKey.restype=wintypes.BOOL
                user.UnregisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int]
                user.PeekMessageW.argtypes=[ctypes.POINTER(wintypes.MSG),wintypes.HWND,wintypes.UINT,wintypes.UINT,wintypes.UINT]
                if window_handles is not None:user.GetForegroundWindow.restype=wintypes.HWND
                focused=None;msg=wintypes.MSG()
                while not self.stop_event.is_set():
                    enabled=window_handles is None or user.GetForegroundWindow() in handles
                    if focused!=enabled:
                        for ident in registered:user.UnregisterHotKey(None,ident)
                        registered.clear();self.status['active']=[];self.status['errors']={};focused=enabled
                        if enabled:
                            for ident,(action,binding) in enumerate(bindings.items(),1):
                                if not binding:continue
                                parts=binding.split('+');mods=0x4000
                                for name in parts[:-1]:mods|={'Ctrl':2,'Alt':1,'Shift':4}[name]
                                if user.RegisterHotKey(None,ident,mods,key_code(parts[-1])):registered[ident]=action;self.status['active'].append(action)
                                else:self.status['errors'][action]='Belegt oder von Windows abgelehnt.'
                        if status_callback:status_callback({**self.status,'active':list(self.status['active']),'errors':dict(self.status['errors'])})
                    ready.set()
                    while user.PeekMessageW(ctypes.byref(msg),None,0,0,1):
                        if enabled and msg.message==0x0312 and msg.wParam in registered:callback(registered[msg.wParam])
                    self.stop_event.wait(.03)
            except Exception as exc:
                self.status['errors']['system']=str(exc);self.status['active']=[];ready.set()
            finally:
                for ident in registered:user.UnregisterHotKey(None,ident)
        self.thread=threading.Thread(target=worker,name='MythicHotkeys',daemon=True);self.thread.start();ready.wait(2)
        return self.status
