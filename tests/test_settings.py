import asyncio
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from settings import Settings, DEFAULTS, validate, combo
from server import Bridge
from adapter import DemoAdapter
from hotkeys import key_code

class SettingsTests(unittest.TestCase):
    def test_bad_import_does_not_overwrite_saved_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'user-settings.json';settings=Settings(path)
            value=copy.deepcopy(DEFAULTS);value['bindings']['hook']='Alt+H'
            settings.save(value);before=path.read_bytes()
            for bad in [float('nan'),True,0,11]:
                invalid=copy.deepcopy(value);invalid['poll_seconds']=bad
                with self.assertRaises(ValueError):settings.save(invalid)
                self.assertEqual(path.read_bytes(),before)
            self.assertEqual(Settings(path).data['bindings']['hook'],'Alt+H')
    def test_binding_conflicts_and_reserved_keys(self):
        self.assertEqual(combo(' shift + ctrl + h '),'Ctrl+Shift+H')
        for value in ['H','Ctrl+F12','Win+H','Ctrl+Ctrl+H','Ctrl+Escape']:
            with self.assertRaises(ValueError):combo(value)
        invalid=copy.deepcopy(DEFAULTS);invalid['bindings']['hook']=invalid['bindings']['scan']
        with self.assertRaises(ValueError):validate(invalid)
        invalid['bindings']['hook']='';self.assertEqual(validate(invalid)['bindings']['hook'],'')
        self.assertEqual(key_code('F10'),0x79)
        self.assertEqual(key_code('W'),0x57)

class ShortcutTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bridge=Bridge(DemoAdapter(),'token',[],True)
        class Socket:
            closed=False
            async def send_json(self,data):pass
        self.bridge.ws=Socket();self.bridge.session_generation=1
        self.bridge.settings.data['global_hotkeys']=True
        await self.bridge.dispatch('hook',{'ids':['9001','9002']})
    async def test_selected_clients_and_stale_session(self):
        b=self.bridge
        await b.dispatch('shortcut_context',{'ids':['9002'],'source':'mass sendkey W 0.2'})
        b.adapter.execute=AsyncMock(wraps=b.adapter.execute)
        await b.shortcut('forward',1)
        b.adapter.execute.assert_awaited_once_with('key',{'ids':['9002'],'key':'W','seconds':0.2})
        await b.shortcut('forward',0)
        self.assertEqual(b.adapter.execute.await_count,1)
    async def test_run_stop_and_context_validation(self):
        b=self.bridge
        await b.dispatch('shortcut_context',{'ids':['9001'],'source':'sleep 60\nmass sendkey W 0.1'})
        await b.shortcut('run_script',1);self.assertFalse(b.script_task.done())
        b.hotkey_busy=True
        await b.shortcut('stop',1);self.assertIsNone(b.script_task)
        for args in [{'ids':['9001','9001'],'source':''},{'ids':['9001'],'source':'a'*16001}]:
            with self.assertRaises(ValueError):await b.dispatch('shortcut_context',args)

class NativeRegistrationTests(unittest.TestCase):
    def test_thread_registers_reports_conflicts_and_unregisters(self):
        import hotkeys
        from unittest.mock import patch
        registered=[];removed=[]
        class Function:
            def __init__(self,fn):self.fn=fn
            def __call__(self,*args):return self.fn(*args)
        class User:
            RegisterHotKey=Function(lambda hwnd,ident,mods,key:registered.append((ident,mods,key)) or ident!=2)
            UnregisterHotKey=Function(lambda hwnd,ident:removed.append(ident) or 1)
            PeekMessageW=Function(lambda *args:0)
        with patch.object(hotkeys.sys,'platform','win32'),patch.object(hotkeys.ctypes,'WinDLL',return_value=User(),create=True):
            manager=hotkeys.Hotkeys()
            status=manager.start({'hook':'Ctrl+Alt+F3','stop':'Alt+S'},lambda action:None)
            self.assertEqual(status['active'],['hook'])
            self.assertIn('stop',status['errors'])
            self.assertEqual(registered[0],(1,0x4003,0x72))
            manager.stop();self.assertEqual(removed,[1]);self.assertEqual(manager.status['active'],[])
