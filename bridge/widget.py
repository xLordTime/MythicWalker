"""Small native Win32 status widget, without a bundled browser/GUI framework."""
import ctypes
from ctypes import wintypes as W
import queue
from pathlib import Path
import sys
from hotkeys import key_code
from settings import DEFAULTS, combo

class StatusWidget:
    def __init__(self,version):
        self.version=version;self.events=queue.Queue();self.title='Bridge startet';self.detail='Bitte einen Moment …'
        self.steps=[];self.browser=lambda:None;self.launcher=lambda:None;self.copy_pairing=lambda:None;self.stop=lambda:None;self.closing=False
        self.launcher_enabled=False;self.config=dict(DEFAULTS['widget']);self.hidden=False;self.smoke_toggles=0;self.smoke_pairing=0
    def report(self,title,detail=''):
        self.events.put(('status',title,str(detail)[:220]))
    def finish(self):self.events.put(('finish','',''))
    def configure(self,config):self.events.put(('configure',dict(config),''))
    def visibility(self,action):self.events.put(('visibility',action,''))
    def run(self):
        user=ctypes.WinDLL('user32',use_last_error=True);gdi=ctypes.WinDLL('gdi32');kernel=ctypes.WinDLL('kernel32')
        ptr=ctypes.c_void_p
        CALLBACK=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,W.HWND,W.UINT,ctypes.c_size_t,ctypes.c_ssize_t)
        class WC(ctypes.Structure):
            _fields_=[('style',W.UINT),('proc',CALLBACK),('clsExtra',ctypes.c_int),('wndExtra',ctypes.c_int),('instance',W.HINSTANCE),('icon',W.HICON),('cursor',W.HANDLE),('background',W.HBRUSH),('menu',W.LPCWSTR),('name',W.LPCWSTR)]
        class PAINT(ctypes.Structure):
            _fields_=[('hdc',W.HDC),('erase',W.BOOL),('rect',W.RECT),('restore',W.BOOL),('inc',W.BOOL),('reserved',ctypes.c_byte*32)]
        signatures={
            'DefWindowProcW':([W.HWND,W.UINT,ctypes.c_size_t,ctypes.c_ssize_t],ctypes.c_ssize_t),
            'CreateWindowExW':([W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.HWND,W.HMENU,W.HINSTANCE,ptr],W.HWND),
            'RegisterClassW':([ctypes.POINTER(WC)],W.ATOM),'BeginPaint':([W.HWND,ctypes.POINTER(PAINT)],W.HDC),
            'EndPaint':([W.HWND,ctypes.POINTER(PAINT)],W.BOOL),'DrawTextW':([W.HDC,W.LPCWSTR,ctypes.c_int,ctypes.POINTER(W.RECT),W.UINT],ctypes.c_int),
            'FillRect':([W.HDC,ctypes.POINTER(W.RECT),W.HBRUSH],ctypes.c_int),'InvalidateRect':([W.HWND,ptr,W.BOOL],W.BOOL),
            'SetTimer':([W.HWND,ctypes.c_size_t,W.UINT,ptr],ctypes.c_size_t),'ShowWindow':([W.HWND,ctypes.c_int],W.BOOL),
            'DestroyWindow':([W.HWND],W.BOOL),'GetMessageW':([ctypes.POINTER(W.MSG),W.HWND,W.UINT,W.UINT],W.BOOL),
            'TranslateMessage':([ctypes.POINTER(W.MSG)],W.BOOL),'DispatchMessageW':([ctypes.POINTER(W.MSG)],ctypes.c_ssize_t),
            'SystemParametersInfoW':([W.UINT,W.UINT,ptr,W.UINT],W.BOOL)}
        for name,(args,result) in signatures.items():fn=getattr(user,name);fn.argtypes=args;fn.restype=result
        kernel.GetModuleHandleW.argtypes=[W.LPCWSTR];kernel.GetModuleHandleW.restype=W.HMODULE
        user.LoadImageW.argtypes=[W.HINSTANCE,W.LPCWSTR,W.UINT,ctypes.c_int,ctypes.c_int,W.UINT];user.LoadImageW.restype=W.HANDLE
        user.DrawIconEx.argtypes=[W.HDC,ctypes.c_int,ctypes.c_int,W.HICON,ctypes.c_int,ctypes.c_int,W.UINT,W.HBRUSH,W.UINT];user.DrawIconEx.restype=W.BOOL
        user.DestroyIcon.argtypes=[W.HICON];user.DestroyIcon.restype=W.BOOL
        user.LoadCursorW.argtypes=[W.HINSTANCE,ctypes.c_void_p];user.LoadCursorW.restype=W.HANDLE
        user.SetCursor.argtypes=[W.HANDLE];user.SetCursor.restype=W.HANDLE
        user.GetCursor.argtypes=[];user.GetCursor.restype=W.HANDLE
        arrow=user.LoadCursorW(None,ctypes.c_void_p(32512))
        if not arrow:raise ctypes.WinError(ctypes.get_last_error())
        icon_path=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'assets'/'mythicwalker.ico'
        app_icon=user.LoadImageW(None,str(icon_path),1,32,32,0x10)
        if not app_icon:raise ctypes.WinError(ctypes.get_last_error())
        gdi.CreateSolidBrush.argtypes=[W.DWORD];gdi.CreateSolidBrush.restype=W.HBRUSH
        gdi.SelectObject.argtypes=[W.HDC,W.HANDLE];gdi.SelectObject.restype=W.HANDLE
        gdi.SetTextColor.argtypes=[W.HDC,W.DWORD];gdi.SetBkMode.argtypes=[W.HDC,ctypes.c_int]
        gdi.GetStockObject.argtypes=[ctypes.c_int];gdi.GetStockObject.restype=W.HANDLE
        gdi.DeleteObject.argtypes=[W.HANDLE]
        user.RegisterHotKey.argtypes=[W.HWND,ctypes.c_int,W.UINT,W.UINT];user.RegisterHotKey.restype=W.BOOL
        user.UnregisterHotKey.argtypes=[W.HWND,ctypes.c_int];user.UnregisterHotKey.restype=W.BOOL
        user.SetWindowPos.argtypes=[W.HWND,W.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.UINT];user.SetWindowPos.restype=W.BOOL
        user.SendMessageW.argtypes=[W.HWND,W.UINT,ctypes.c_size_t,ctypes.c_ssize_t];user.SendMessageW.restype=ctypes.c_ssize_t
        user.RegisterWindowMessageW.argtypes=[W.LPCWSTR];user.RegisterWindowMessageW.restype=W.UINT
        # The V1 notification layout is sufficient for icon, callback and tooltip.
        class TRAY(ctypes.Structure):
            _fields_=[('size',W.DWORD),('hwnd',W.HWND),('ident',W.UINT),('flags',W.UINT),('message',W.UINT),('icon',W.HICON),('tip',W.WCHAR*64)]
        shell=ctypes.WinDLL('shell32',use_last_error=True)
        shell.Shell_NotifyIconW.argtypes=[W.DWORD,ctypes.POINTER(TRAY)];shell.Shell_NotifyIconW.restype=W.BOOL
        hotkey_id=0x5A10;hotkey_registered=False;tray_ready=False;tray=None
        taskbar_created=user.RegisterWindowMessageW('TaskbarCreated')
        def show(action):
            hidden=not self.hidden if action=='toggle' else action=='hide'
            if hidden and not tray_ready and not hotkey_registered:
                self.report('Widget bleibt sichtbar','Tray und Shortcut nicht verfügbar.');return
            self.hidden=hidden
            user.ShowWindow(hwnd,0 if self.hidden else 4)
        def configure(config):
            nonlocal hotkey_registered
            binding=combo(config['hotkey'])
            if hotkey_registered:user.UnregisterHotKey(hwnd,hotkey_id)
            hotkey_registered=False;self.config=dict(config)
            if binding:
                parts=binding.split('+');mods=0x4000
                for name in parts[:-1]:mods|={'Ctrl':2,'Alt':1,'Shift':4}[name]
                hotkey_registered=bool(user.RegisterHotKey(hwnd,hotkey_id,mods,key_code(parts[-1])))
                if not hotkey_registered:self.report('Widget-Shortcut belegt','Andere Taste in Settings wählen. Tray-Symbol zeigt das Widget wieder.')
            user.SetWindowPos(hwnd,W.HWND(-1 if config['topmost'] else -2),0,0,0,0,0x13)
        bg=gdi.CreateSolidBrush(0x24191A);button=gdi.CreateSolidBrush(0x49312F)
        def text(hdc,value,x,y,width,height,color=0xF7EDEE):
            gdi.SetTextColor(hdc,color);rect=W.RECT(x,y,x+width,y+height);user.DrawTextW(hdc,value,-1,ctypes.byref(rect),0x10|0x800)
        @CALLBACK
        def proc(hwnd,msg,wp,lp):
            nonlocal tray_ready
            if msg==taskbar_created and tray is not None:
                tray_ready=bool(shell.Shell_NotifyIconW(0,ctypes.byref(tray)))
                if not tray_ready:show('show')
                return 0
            if msg==0x8001 and lp in (0x0202,0x0205):show('show');return 0
            if msg==0x0312 and wp==hotkey_id:show('toggle');return 0
            if msg==0x0020 and (lp&0xffff)==1:
                user.SetCursor(arrow);return 1
            if msg==0x000F:
                paint=PAINT();hdc=user.BeginPaint(hwnd,ctypes.byref(paint));rect=W.RECT(0,0,360,250);user.FillRect(hdc,ctypes.byref(rect),bg)
                gdi.SetBkMode(hdc,1);gdi.SelectObject(hdc,gdi.GetStockObject(17))
                user.DrawIconEx(hdc,18,13,app_icon,28,28,0,None,3)
                text(hdc,'MYTHIC WALKER  ·  '+self.version,57,18,247,22,0xFFADBC)
                text(hdc,'−',320,16,25,24,0xFFADBC)
                text(hdc,self.title,20,50,320,28);text(hdc,self.detail,20,80,320,45,0xB0989B)
                for i,step in enumerate(self.steps[-2:]):text(hdc,'✓  '+step,20,132+i*19,320,19,0xC5DC8D)
                text(hdc,'Launcher lokal öffnen  ↗' if self.launcher_enabled else 'Launcher aus · In Settings aktivieren',20,182,320,20,0xFFADBC)
                for left,label in [(20,'Dashboard öffnen'),(202,'Beenden')]:
                    rect=W.RECT(left,204,left+138,237);user.FillRect(hdc,ctypes.byref(rect),button);text(hdc,label,left+12,213,120,22)
                user.EndPaint(hwnd,ctypes.byref(paint));return 0
            if msg==0x0113:
                while True:
                    try:kind,title,detail=self.events.get_nowait()
                    except queue.Empty:break
                    if kind=='finish':user.DestroyWindow(hwnd);return 0
                    if kind=='configure':configure(title);continue
                    if kind=='visibility':show(title);continue
                    if kind=='smoke':
                        if user.SendMessageW(hwnd,0x0020,0,1)!=1 or user.GetCursor()!=arrow:raise RuntimeError('Widget cursor is not the arrow cursor')
                        user.SendMessageW(hwnd,0x0205,0,(220<<16)|50)
                        if self.smoke_pairing!=1:raise RuntimeError('Dashboard right click did not call pairing copy')
                        user.SendMessageW(hwnd,0x0312,hotkey_id,0)
                        if not self.hidden:raise RuntimeError('Hotkey did not hide widget')
                        self.smoke_toggles+=1
                        user.SendMessageW(hwnd,0x0312,hotkey_id,0)
                        if self.hidden:raise RuntimeError('Hotkey did not show widget')
                        self.smoke_toggles+=1;continue
                    if title!=self.title and self.title not in ('Bridge startet','Fehler'):self.steps.append(self.title);self.steps=self.steps[-6:]
                    self.title,self.detail=title,detail
                user.InvalidateRect(hwnd,None,False);return 0
            if msg==0x0202:
                x,y=lp&0xffff,(lp>>16)&0xffff
                if 314<=x<=348 and 10<=y<=43:show('hide');return 0
                if 20<=x<=340 and 181<=y<=201:self.launcher();return 0
                if 204<=y<=237:
                    if 20<=x<=158:self.browser()
                    elif 202<=x<=340:self.stop()
                return 0
            if msg==0x0205:
                x,y=lp&0xffff,(lp>>16)&0xffff
                if 20<=x<=158 and 204<=y<=237:self.copy_pairing()
                return 0
            if msg==0x0010:self.stop();return 0
            if msg==0x0002:user.PostQuitMessage(0);return 0
            return user.DefWindowProcW(hwnd,msg,wp,lp)
        instance=kernel.GetModuleHandleW(None);name='MythicWalkerStatus'
        wc=WC(0,proc,0,0,instance,app_icon,arrow,bg,None,name)
        if not user.RegisterClassW(ctypes.byref(wc)):raise ctypes.WinError(ctypes.get_last_error())
        work=W.RECT();user.SystemParametersInfoW(48,0,ctypes.byref(work),0)
        hwnd=user.CreateWindowExW(0x08000088,name,'Mythic Walker',0x80000000,work.right-378,work.bottom-268,360,250,None,None,instance,None)
        if not hwnd:raise ctypes.WinError(ctypes.get_last_error())
        self.hwnd=hwnd
        tray=TRAY(ctypes.sizeof(TRAY),hwnd,1,7,0x8001,app_icon,'Mythic Walker · Klicken zum Anzeigen')
        tray_ready=bool(shell.Shell_NotifyIconW(0,ctypes.byref(tray)))
        # Load queued preferences before choosing the initial visibility.
        pending=[]
        while not self.events.empty():
            event=self.events.get_nowait()
            if event[0]=='configure':self.config=event[1]
            else:pending.append(event)
        for event in pending:self.events.put(event)
        configure(self.config)
        user.SetTimer(hwnd,1,150,None);show('hide' if self.config['start_hidden'] else 'show')
        message=W.MSG()
        try:
            while user.GetMessageW(ctypes.byref(message),None,0,0)>0:user.TranslateMessage(ctypes.byref(message));user.DispatchMessageW(ctypes.byref(message))
        finally:
            if hotkey_registered:user.UnregisterHotKey(hwnd,hotkey_id)
            if tray is not None:shell.Shell_NotifyIconW(2,ctypes.byref(tray))
            gdi.DeleteObject(button);gdi.DeleteObject(bg);user.DestroyIcon(app_icon)
