import asyncio
import contextlib
import enum
import importlib.util
import re
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge'))
from fishing import Fishing, PatchJournal, CoreSession, options, CONFIG
from adapter import WizAdapter, DemoAdapter
from server import Bridge

class Reader:
    def __init__(self):self.memory={};self.original={};self.patterns=[];self.fail_at=None;self.bad_restore=False;self.ambiguous=False
    async def pattern_scan(self,pattern,**kwargs):
        if pattern not in self.patterns:self.patterns.append(pattern)
        address=1000+self.patterns.index(pattern)*128
        if address not in self.memory:
            tokens=re._parser.parse(pattern,0)
            data=bytes(arg if str(op)=='LITERAL' else 0x11 for op,arg in tokens)
            self.memory[address]=(data+b'\x55'*64)[:64];self.original[address]=self.memory[address]
        return [address,address+64] if self.ambiguous else [address]
    async def read_bytes(self,address,size):return self.memory.setdefault(address,b'\x01'*64)[:size]
    async def write_bytes(self,address,value):
        old=self.memory.setdefault(address,b'\x01'*64);self.memory[address]=value+old[len(value):]
        if self.fail_at==address:self.fail_at=None;raise RuntimeError('partial write')
        if self.bad_restore and address in self.original and value==self.original[address][:len(value)]:self.memory[address]=b'\x00'*len(value)+old[len(value):]

class Status(enum.IntEnum):waiting=0;unknown2=2;escaped=9
class Window:
    def __init__(self,name):self.name=name
    async def is_visible(self):return True
    async def get_child_by_name(self,name):return Window(name)
    async def read_base_address(self):return 80000 if self.name=='OpenFishingButton' else 90000

class Client:
    process_id=42;window_handle=4096
    def __init__(self):
        self.reader=Reader();self._pymem=self.reader;self.open=False;self.caught=False;self.bitten=False;self.closed=False;self.keys=[];self.clicked=[]
        self.root_window=types.SimpleNamespace(get_windows_with_name=self.windows);self.mouse_handler=self
        self.game_client=types.SimpleNamespace(fishing_manager=self.manager)
        self.fish=types.SimpleNamespace(template=AsyncMock(return_value=types.SimpleNamespace(rank=AsyncMock(return_value=2),school_name=AsyncMock(return_value='Life'))),size=AsyncMock(return_value=10),is_chest=AsyncMock(return_value=False),status_code=self.status,template_id=AsyncMock(return_value=7),write_status_code=AsyncMock())
    async def status(self):return Status.unknown2 if self.bitten else Status.waiting
    async def manager(self):return types.SimpleNamespace(fish_list=AsyncMock(return_value=[self.fish]))
    async def windows(self,name):
        visible=(name=='FishingWindow' and self.open) or (name=='CaughtFishModalWindow' and self.caught) or name in ('OpenFishingButton','CloseFishingButton')
        return [Window(name)] if visible else []
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    async def click_window_with_name(self,name):
        self.clicked.append(name)
        if name=='OpenFishingButton':self.open=True
        if name=='CloseFishingButton':self.open=False
    async def click_window(self,window):
        self.clicked.append(window.name)
        if window.name=='Icon1':self.bitten=True
        if window.name=='exit':self.caught=False
    async def send_key(self,key):self.keys.append(key);self.caught=True
    def is_running(self):return True
    async def close(self):self.closed=True

@contextlib.contextmanager
def original_core(client):
    # Execute the entire vendored source with only external OS/game APIs mocked.
    wiz=types.ModuleType('wizwalker');wiz.__file__='mock-wizwalker';wiz.ClientHandler=object;wiz.Client=object;wiz.Keycode=types.SimpleNamespace(SPACEBAR=32,V=86);wiz.PatternFailed=RuntimeError
    mem=types.ModuleType('wizwalker.memory');mem.MemoryReader=lambda pymem:pymem;mem.Window=Window
    fish=types.ModuleType('wizwalker.memory.memory_objects.fish');fish.Fish=object;fish.FishStatusCode=Status
    log=types.ModuleType('loguru');log.logger=types.SimpleNamespace()
    process=types.ModuleType('memobj.process');process.WindowsProcess=object
    dll=types.SimpleNamespace(**{name:types.SimpleNamespace() for name in ['CreateRemoteThread','WaitForSingleObject','CloseHandle','GetExitCodeThread','VirtualProtectEx','FlushInstructionCache']})
    spec=importlib.util.spec_from_file_location('test_native_fishcore',ROOT/'bridge/vendor/fishbot_de.py');core=importlib.util.module_from_spec(spec)
    import ctypes,vendor
    with patch.dict(sys.modules,{'wizwalker':wiz,'wizwalker.memory':mem,'wizwalker.memory.memory_objects.fish':fish,'loguru':log,'memobj.process':process,'test_native_fishcore':core}),patch.object(ctypes,'windll',types.SimpleNamespace(kernel32=dll),create=True),patch('fishing.native_flush',return_value=lambda a,n:None):
        spec.loader.exec_module(core)
        with patch.object(vendor,'fishbot_de',core,create=True):yield core

class FishingTests(unittest.IsolatedAsyncioTestCase):
    def bridge(self,c):
        a=WizAdapter.__new__(WizAdapter);a.handler=types.SimpleNamespace(clients=[c]);a.hooked={'42'};a.errors={};a.freecam=set();a.original_speeds={};a.fishing_patches={}
        b=Bridge(a,'test',[],False);b.send=AsyncMock();b.log=AsyncMock();return b
    def originals(self,c):
        for address,value in c.reader.original.items():self.assertEqual(c.reader.memory[address],value,hex(address))
    async def test_complete_original_core_all_31_patches_popup_skip_and_restore(self):
        c=Client();b=self.bridge(c)
        with original_core(c):
            await b.fishing.start(['42'],{'max_catches':1});await asyncio.wait_for(b.fishing.task,3)
        self.assertEqual(len(c.reader.patterns),31);self.assertEqual(b.fishing.data['catches'],1);self.assertIsNone(b.fishing.data['error']);self.assertTrue(b.fishing.data['restored'])
        self.assertIn('Icon1',c.clicked);self.assertIn(32,c.keys);self.assertEqual(c.reader.memory[80000+0x2b0][:1],b'\x00');self.originals(c)
        await b.adapter.unhook(['42']);self.assertTrue(c.closed)
    async def test_popup_enabled_option_uses_normal_catch_window(self):
        c=Client();b=self.bridge(c)
        with original_core(c):
            await b.fishing.start(['42'],{'max_catches':1,'skip_popup':False});await asyncio.wait_for(b.fishing.task,3)
        self.assertEqual(len(c.reader.patterns),30);self.assertIn('exit',c.clicked);self.assertFalse(c.caught);self.originals(c)
    async def test_original_100_fish_basket_trigger_and_restart(self):
        c=Client();b=self.bridge(c)
        with original_core(c) as core:
            core.sell_basket=AsyncMock(wraps=core.sell_basket)
            await b.fishing.start(['42'],{'max_catches':101,'game_state_wait':.001});await asyncio.wait_for(b.fishing.task,5)
            self.assertEqual(b.fishing.data['catches'],101);core.sell_basket.assert_awaited_once_with(c);self.originals(c)
            await b.fishing.start(['42'],{'max_catches':1});await asyncio.wait_for(b.fishing.task,3)
            self.assertEqual(b.fishing.data['catches'],1);self.assertIsNone(b.fishing.data['error']);self.originals(c)
    async def test_stop_waits_for_key_completion(self):
        c=Client();b=self.bridge(c);started=asyncio.Event();finished=asyncio.Event()
        async def reel(key):started.set();await asyncio.sleep(.02);finished.set()
        c.send_key=reel
        with original_core(c):
            await b.fishing.start(['42'],{});await started.wait();await b.dispatch('unhook',{'ids':['42']})
        self.assertTrue(finished.is_set());self.assertTrue(c.closed);self.originals(c)
    async def test_failed_setup_rolls_back_partial_write(self):
        c=Client();c.reader.fail_at=1128;b=self.bridge(c)
        with original_core(c):await b.fishing.start(['42'],{});await b.fishing.task
        self.assertIn('partial write',b.fishing.data['error']);self.assertTrue(b.fishing.data['restored']);self.originals(c)
    async def test_failed_restore_blocks_unhook_and_can_retry(self):
        c=Client();b=self.bridge(c);c.reader.memory[100]=b'ABCDEF';j=PatchJournal(c.reader);await j.write(100,b'\x90'*6)
        c.reader.original[100]=b'ABCDEF';c.reader.bad_restore=True;b.adapter.fishing_patches['42']=j
        with self.assertRaisesRegex(RuntimeError,'wiederhergestellt'):await b.adapter.unhook(['42'])
        self.assertFalse(c.closed);self.assertTrue(j.entries)
        c.reader.bad_restore=False;await b.adapter.unhook(['42']);self.assertTrue(c.closed);self.assertFalse(j.entries)
    async def test_original_basket_cleanup_and_fish_filter(self):
        c=Client()
        with original_core(c) as core:
            session=CoreSession(core,c,lambda *args:None)
            try:
                core.reset_cleanup_state();core.RANK=2;core.SCHOOL='Life';core.ID=7
                fish=await core.banish_config(await c.manager());self.assertEqual(fish,[c.fish])
                core.ID=8;self.assertEqual(await core.banish_config(await c.manager()),[]);c.fish.write_status_code.assert_awaited_with(Status.escaped)
                await core.sell_basket(c);self.assertEqual(c.keys,[86,86])
            finally:session.release()
    async def test_partial_speed_attach_restored_even_if_upstream_drops_reference(self):
        c=Client();b=self.bridge(c);memory={200:b'A'*14}
        class Process:
            def read_memory(self,a,n):return memory[a][:n]
            def write_memory(self,a,v):memory[a]=v
            def free_memory(self,a):pass
        class Speed:
            def __init__(self,client):self._process=Process();self._mem_base=999;self._gettickcount_addr=200;self._gettickcount64_addr=None;self._qpc_addr=None;self._timegettime_addr=None
            def _get_process(self):return self._process
            def _make_writable(self,*args):pass
            def _flush_cache(self,*args):pass
            def attach(self):self._get_process().write_memory(200,b'Z'*14);raise RuntimeError('partial speed attach')
            def cleanup(self):self._mem_base=None
        with original_core(c) as core:
            core.Speedhack=Speed
            await b.fishing.start(['42'],{'max_catches':1,'speed_enabled':True});await b.fishing.task
        self.assertEqual(memory[200],b'A'*14);self.assertTrue(b.fishing.data['restored']);self.originals(c)
    async def test_conflicting_commands_and_demo_rejected(self):
        b=Bridge(DemoAdapter(),'test',[],True)
        with self.assertRaisesRegex(ValueError,'Live'):await b.dispatch('fishing_start',{'ids':['9001']})
        c=Client();b=self.bridge(c);b.fishing.task=asyncio.create_task(asyncio.sleep(20))
        try:
            for op in ['run_script','teleport','freecam','automation']:
                with self.subTest(op=op),self.assertRaisesRegex(ValueError,'Fisch-Bot'):await b.dispatch(op,{})
        finally:b.fishing.task.cancel()
    def test_options_match_original_defaults_and_validate(self):
        c=Client()
        with original_core(c) as core:
            for key,(name,value) in CONFIG.items():self.assertEqual(options({})[key],getattr(core,name))
        for value in [{'minutes':-1},{'rank':2.2},{'skip_popup':1},{'size_min':100,'size_max':2},{'size_max':float('nan')},{'speed':11},{'school':[]},{'extra':1}]:
            with self.subTest(value=value),self.assertRaises(ValueError):options(value)
    def test_original_source_parity_except_documented_popup_toggle_fix(self):
        import hashlib
        source=(ROOT/'bridge/vendor/fishbot_de.py').read_text().replace('            # The disabled popup option must retain the normal game window.\n            if operation is skip_caught_fish_window and not SKIP_CAUGHT_FISH_POPUP:\n                continue\n','')
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),'9d374d1d548cd34e88f6bc07a6081ab47201ba6b2c1f4308e11ebf47d989d9f6')
    @unittest.skipUnless(sys.platform=='win32','Windows native dependencies')
    def test_real_windows_core_import(self):
        subprocess.run([sys.executable,'-c','from vendor import fishbot_de; from memobj.process.windows.module import WindowsModule; import os; m=WindowsModule(name="kernel32.dll",base_address=0,executable_path=os.path.join(os.environ["WINDIR"],"System32","kernel32.dll"),size=0,process=None); assert m.get_symbol_with_name("GetTickCount")>0; print(fishbot_de.Speedhack.__name__)'],cwd=ROOT/'bridge',check=True,capture_output=True,text=True)
