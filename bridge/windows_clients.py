"""Pointer-safe discovery of Wizard101's actual game windows (not its launcher)."""
import ctypes
from ctypes import wintypes


def wizard_windows(api=None, callback_type=None):
    api = api or ctypes.WinDLL('user32', use_last_error=True)
    callback_type = callback_type or ctypes.WINFUNCTYPE
    callback_signature = callback_type(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    api.EnumWindows.argtypes = [callback_signature, wintypes.LPARAM]
    api.EnumWindows.restype = wintypes.BOOL
    api.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    api.GetClassNameW.restype = ctypes.c_int
    handles = []

    def visit(handle, _):
        name = ctypes.create_unicode_buffer(256)
        if api.GetClassNameW(handle, name, len(name)) and name.value == 'Wizard Graphical Client':
            handles.append(handle)
        return True

    callback = callback_signature(visit)
    if not api.EnumWindows(callback, 0):
        raise OSError('Windows-Fenstersuche fehlgeschlagen.')
    return handles
