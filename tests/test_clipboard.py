import ctypes
from ctypes import wintypes as W
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from windows_desktop import copy_text

@unittest.skipUnless(sys.platform=='win32','Windows clipboard ownership')
class ClipboardTests(unittest.TestCase):
    def test_unicode_copy_with_owned_window(self):
        user=ctypes.WinDLL('user32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        user.CreateWindowExW.argtypes=[W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.HWND,W.HMENU,W.HINSTANCE,ctypes.c_void_p]
        user.CreateWindowExW.restype=W.HWND;user.DestroyWindow.argtypes=[W.HWND]
        user.GetClipboardData.argtypes=[W.UINT];user.GetClipboardData.restype=W.HANDLE
        user.OpenClipboard.argtypes=[W.HWND]
        kernel.GlobalLock.argtypes=[W.HGLOBAL];kernel.GlobalLock.restype=ctypes.c_void_p
        kernel.GlobalUnlock.argtypes=[W.HGLOBAL]
        hwnd=user.CreateWindowExW(0,'STATIC','Mythic clipboard fixture',0,0,0,1,1,None,None,None,None)
        self.assertTrue(hwnd)
        try:
            expected='Pairing-Fixture-äöü';copy_text(expected,hwnd)
            self.assertTrue(user.OpenClipboard(hwnd))
            try:
                handle=user.GetClipboardData(13);self.assertTrue(handle)
                address=kernel.GlobalLock(handle);self.assertTrue(address)
                try:self.assertEqual(ctypes.wstring_at(address),expected)
                finally:kernel.GlobalUnlock(handle)
            finally:user.CloseClipboard()
        finally:user.DestroyWindow(hwnd)
