"""Small native Win32 status widget, without a bundled browser/GUI framework."""
import ctypes
from ctypes import wintypes as W
import queue

class StatusWidget:
    def __init__(self,version):
        self.version=version;self.events=queue.Queue();self.title='Bridge startet';self.detail='Bitte einen Moment …'
        self.steps=[];self.browser=lambda:None;self.stop=lambda:None;self.closing=False
    def report(self,title,detail=''):
        self.events.put(('status',title,str(detail)[:220]))
    def finish(self):self.events.put(('finish','',''))
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
        gdi.CreateSolidBrush.argtypes=[W.DWORD];gdi.CreateSolidBrush.restype=W.HBRUSH
        gdi.SelectObject.argtypes=[W.HDC,W.HANDLE];gdi.SelectObject.restype=W.HANDLE
        gdi.SetTextColor.argtypes=[W.HDC,W.DWORD];gdi.SetBkMode.argtypes=[W.HDC,ctypes.c_int]
        gdi.GetStockObject.argtypes=[ctypes.c_int];gdi.GetStockObject.restype=W.HANDLE
        gdi.DeleteObject.argtypes=[W.HANDLE]
        bg=gdi.CreateSolidBrush(0x24191A);button=gdi.CreateSolidBrush(0x49312F)
        def text(hdc,value,x,y,width,height,color=0xF7EDEE):
            gdi.SetTextColor(hdc,color);rect=W.RECT(x,y,x+width,y+height);user.DrawTextW(hdc,value,-1,ctypes.byref(rect),0x10|0x800)
        @CALLBACK
        def proc(hwnd,msg,wp,lp):
            if msg==0x000F:
                paint=PAINT();hdc=user.BeginPaint(hwnd,ctypes.byref(paint));rect=W.RECT(0,0,360,250);user.FillRect(hdc,ctypes.byref(rect),bg)
                gdi.SetBkMode(hdc,1);gdi.SelectObject(hdc,gdi.GetStockObject(17))
                text(hdc,'✧  MYTHIC WALKER  ·  '+self.version,20,16,320,22,0xFFADBC)
                text(hdc,self.title,20,50,320,28);text(hdc,self.detail,20,80,320,45,0xB0989B)
                for i,step in enumerate(self.steps[-3:]):text(hdc,'✓  '+step,20,132+i*19,320,19,0xC5DC8D)
                for left,label in [(20,'Dashboard öffnen'),(202,'Beenden')]:
                    rect=W.RECT(left,204,left+138,237);user.FillRect(hdc,ctypes.byref(rect),button);text(hdc,label,left+12,213,120,22)
                user.EndPaint(hwnd,ctypes.byref(paint));return 0
            if msg==0x0113:
                while True:
                    try:kind,title,detail=self.events.get_nowait()
                    except queue.Empty:break
                    if kind=='finish':user.DestroyWindow(hwnd);return 0
                    if title!=self.title and self.title not in ('Bridge startet','Fehler'):self.steps.append(self.title);self.steps=self.steps[-6:]
                    self.title,self.detail=title,detail
                user.InvalidateRect(hwnd,None,False);return 0
            if msg==0x0202:
                x,y=lp&0xffff,(lp>>16)&0xffff
                if 204<=y<=237:
                    if 20<=x<=158:self.browser()
                    elif 202<=x<=340:self.stop()
                return 0
            if msg==0x0010:self.stop();return 0
            if msg==0x0002:user.PostQuitMessage(0);return 0
            return user.DefWindowProcW(hwnd,msg,wp,lp)
        instance=kernel.GetModuleHandleW(None);name='MythicWalkerStatus'
        wc=WC(0,proc,0,0,instance,None,None,bg,None,name)
        if not user.RegisterClassW(ctypes.byref(wc)):raise ctypes.WinError(ctypes.get_last_error())
        work=W.RECT();user.SystemParametersInfoW(48,0,ctypes.byref(work),0)
        hwnd=user.CreateWindowExW(0x08000088,name,'Mythic Walker',0x80000000,work.right-378,work.bottom-268,360,250,None,None,instance,None)
        if not hwnd:raise ctypes.WinError(ctypes.get_last_error())
        user.SetTimer(hwnd,1,150,None);user.ShowWindow(hwnd,4)
        message=W.MSG()
        try:
            while user.GetMessageW(ctypes.byref(message),None,0,0)>0:user.TranslateMessage(ctypes.byref(message));user.DispatchMessageW(ctypes.byref(message))
        finally:gdi.DeleteObject(button);gdi.DeleteObject(bg)
