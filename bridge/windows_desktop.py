"""Small Win32 helpers for clipboard ownership and dashboard window focus."""
import ctypes
from ctypes import wintypes as W


def copy_text(value, owner):
    user=ctypes.WinDLL('user32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GlobalAlloc.argtypes=[W.UINT,ctypes.c_size_t];kernel.GlobalAlloc.restype=W.HGLOBAL
    kernel.GlobalLock.argtypes=[W.HGLOBAL];kernel.GlobalLock.restype=ctypes.c_void_p
    kernel.GlobalUnlock.argtypes=[W.HGLOBAL];kernel.GlobalFree.argtypes=[W.HGLOBAL]
    user.OpenClipboard.argtypes=[W.HWND];user.SetClipboardData.argtypes=[W.UINT,W.HANDLE];user.SetClipboardData.restype=W.HANDLE
    payload=(value+'\0').encode('utf-16-le');handle=kernel.GlobalAlloc(2,len(payload))
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    transferred=False
    try:
        address=kernel.GlobalLock(handle)
        if not address:raise ctypes.WinError(ctypes.get_last_error())
        try:ctypes.memmove(address,payload,len(payload))
        finally:kernel.GlobalUnlock(handle)
        if not user.OpenClipboard(owner):raise RuntimeError('Zwischenablage belegt. Erneut rechtsklicken.')
        try:
            if not user.EmptyClipboard() or not user.SetClipboardData(13,handle):raise ctypes.WinError(ctypes.get_last_error())
            transferred=True
        finally:user.CloseClipboard()
    finally:
        if not transferred:kernel.GlobalFree(handle)


def focus_dashboard():
    user=ctypes.WinDLL('user32',use_last_error=True)
    callback_type=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    user.EnumWindows.argtypes=[callback_type,W.LPARAM]
    user.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,ctypes.c_int]
    user.ShowWindow.argtypes=[W.HWND,ctypes.c_int];user.SetForegroundWindow.argtypes=[W.HWND]
    found=[]
    def visit(hwnd,_):
        title=ctypes.create_unicode_buffer(512);user.GetWindowTextW(hwnd,title,len(title))
        if title.value.startswith('Mythic Walker · Web Client'):found.append(hwnd)
        return True
    user.EnumWindows(callback_type(visit),0)
    if not found:return False
    user.ShowWindow(found[0],9)
    return bool(user.SetForegroundWindow(found[0]))
