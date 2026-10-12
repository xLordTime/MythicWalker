import asyncio
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from fishing import Fishing, PatchJournal, DISTANCE_PATCHES, options
from adapter import WizAdapter, DemoAdapter
from server import Bridge

class Reader:
    def __init__(self):
        self.memory={100+i*32:b'\x0f\x84\x01\x02\x03\x04' for i in range(6)}
        self.original=dict(self.memory);self.writes=[];self.fail_at=None;self.bad_restore=False;self.ambiguous=False
    async def pattern_scan(self,pattern,**kwargs):
        i=[p for _,p in DISTANCE_PATCHES].index(pattern)
        return [100+i*32,9000] if self.ambiguous and i==5 else [100+i*32]
    async def read_bytes(self,address,size):return self.memory[address][:size]
    async def write_bytes(self,address,value):
        self.writes.append((address,value));self.memory[address]=value
        if value==b'\x90'*6 and address==self.fail_at:raise RuntimeError('partial write')
        if self.bad_restore and value!=b'\x90'*6:self.memory[address]=b'wrong!'

class Window:
    def __init__(self,name):self.name=name
    async def is_visible(self):return True
    async def get_child_by_name(self,name):return Window(name)

class Client:
    process_id=42;_pymem=None
    def __init__(self):
        self.reader=Reader();self.open=False;self.caught=False;self.bitten=False;self.zone='House';self.closed=False;self.cast_event=asyncio.Event()
        self.root_window=types.SimpleNamespace(get_windows_with_name=self.windows)
        self.mouse_handler=self
        self.game_client=types.SimpleNamespace(fishing_manager=self.manager)
        self.fish=types.SimpleNamespace(template=AsyncMock(return_value=types.SimpleNamespace()),size=AsyncMock(return_value=10),is_chest=AsyncMock(return_value=False),status_code=self.status)
    async def status(self):return 2 if self.bitten else 0
    async def manager(self):return types.SimpleNamespace(fish_list=AsyncMock(return_value=[self.fish]))
    async def windows(self,name):
        visible=(name=='FishingWindow' and self.open) or (name=='CaughtFishModalWindow' and self.caught)
        return [Window(name)] if visible else []
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    async def click_window_with_name(self,name):
        if name=='OpenFishingButton':self.open=True
        if name=='CloseFishingButton':self.open=False
    async def click_window(self,window):
        if window.name=='Icon1':self.bitten=True;self.cast_event.set()
        if window.name=='exit':self.caught=False
    async def send_key(self,key):self.caught=True
    async def zone_name(self):return self.zone
    async def is_loading(self):return False
    async def in_battle(self):return False
    def is_running(self):return True
    async def close(self):self.closed=True

class FishingTests(unittest.IsolatedAsyncioTestCase):
    def modules(self,client):
        wiz=types.ModuleType('wizwalker');wiz.Keycode=types.SimpleNamespace(SPACEBAR=32)
        mem=types.ModuleType('wizwalker.memory');mem.MemoryReader=lambda pymem:client.reader
        fish=types.ModuleType('wizwalker.memory.memory_objects.fish');fish.FishStatusCode=types.SimpleNamespace(escaped=9,unknown2=2)
        return patch.dict(sys.modules,{'wizwalker':wiz,'wizwalker.memory':mem,'wizwalker.memory.memory_objects.fish':fish})
    def bridge(self,client):
        a=WizAdapter.__new__(WizAdapter);a.handler=types.SimpleNamespace(clients=[client]);a.hooked={'42'};a.errors={};a.freecam=set();a.original_speeds={};a.fishing_patches={}
        b=Bridge(a,'test',[],False);b.send=AsyncMock();b.log=AsyncMock();return b
    async def test_original_bytes_restored_and_second_run(self):
        reader=Reader();journal=PatchJournal(reader)
        for _ in range(2):
            await journal.apply_distance();self.assertEqual(len(journal.entries),6)
            await journal.restore();self.assertFalse(journal.entries);self.assertEqual(reader.memory,reader.original)
    async def test_ambiguous_signature_writes_nothing(self):
        r=Reader();r.ambiguous=True;j=PatchJournal(r)
        with self.assertRaisesRegex(RuntimeError,'Treffer'):await j.apply_distance()
        self.assertEqual(r.writes,[])
    async def test_partial_write_keeps_original_for_rollback(self):
        r=Reader();r.fail_at=164;j=PatchJournal(r)
        with self.assertRaisesRegex(RuntimeError,'partial'):await j.apply_distance()
        await j.restore();self.assertEqual(r.memory,r.original)
    async def test_failed_restore_retains_journal_and_prevents_unhook(self):
        c=Client();b=self.bridge(c);j=PatchJournal(c.reader);await j.apply_distance();c.reader.bad_restore=True;b.adapter.fishing_patches['42']=j
        with self.assertRaisesRegex(RuntimeError,'wiederhergestellt'):await b.adapter.unhook(['42'])
        self.assertFalse(c.closed);self.assertIn('42',b.adapter.hooked);self.assertEqual(len(j.entries),6)
        c.reader.bad_restore=False;await b.adapter.unhook(['42']);self.assertTrue(c.closed);self.assertFalse(j.entries)
    async def test_full_fang_close_restore_then_unhook(self):
        c=Client();b=self.bridge(c)
        with self.modules(c),patch('fishing.native_flush',return_value=lambda a,n:None):
            await b.fishing.start(['42'],{'max_catches':1,'distance_patch':True})
            await b.fishing.task
        self.assertEqual(b.fishing.data['catches'],1);self.assertTrue(b.fishing.data['restored']);self.assertIsNone(b.fishing.data['error'])
        self.assertFalse(c.caught);self.assertFalse(c.open);self.assertEqual(c.reader.memory,c.reader.original)
        self.assertFalse(c.closed);await b.adapter.unhook(['42']);self.assertTrue(c.closed)
    async def test_manager_error_rolls_back_before_closing(self):
        c=Client();c.game_client.fishing_manager=AsyncMock(side_effect=RuntimeError('manager missing'));b=self.bridge(c)
        with self.modules(c),patch('fishing.native_flush',return_value=lambda a,n:None):
            await b.fishing.start(['42'],{'distance_patch':True});await b.fishing.task
        self.assertTrue(b.fishing.data['restored']);self.assertEqual(c.reader.memory,c.reader.original);self.assertEqual(b.fishing.data['error'],'manager missing')
    async def test_stop_finishes_key_up_and_restores(self):
        c=Client();b=self.bridge(c);started=asyncio.Event();finished=asyncio.Event()
        async def reel(key):started.set();await asyncio.sleep(.03);c.caught=True;finished.set()
        c.send_key=reel
        with self.modules(c),patch('fishing.native_flush',return_value=lambda a,n:None):
            await b.fishing.start(['42'],{'distance_patch':True});await started.wait();await b.fishing.stop()
        self.assertTrue(finished.is_set());self.assertFalse(c.caught);self.assertFalse(c.open);self.assertEqual(c.reader.memory,c.reader.original)
    async def test_zone_change_stops_before_cast(self):
        c=Client();b=self.bridge(c)
        original=c.manager
        async def manager():c.zone='Other';return await original()
        c.game_client.fishing_manager=manager
        with self.modules(c):await b.fishing.start(['42'],{});await b.fishing.task
        self.assertIn('Zonenwechsel',b.fishing.data['error']);self.assertFalse(c.cast_event.is_set())
    async def test_conflicting_commands_and_demo_are_rejected(self):
        b=Bridge(DemoAdapter(),'test',[],True)
        with self.assertRaisesRegex(ValueError,'Live'):await b.dispatch('fishing_start',{'ids':['9001']})
        c=Client();b=self.bridge(c);b.fishing.task=asyncio.create_task(asyncio.sleep(20))
        try:
            for op in ['run_script','teleport','freecam','automation']:
                with self.subTest(op=op),self.assertRaisesRegex(ValueError,'Fisch-Bot'):await b.dispatch(op,{})
        finally:b.fishing.task.cancel()
    def test_invalid_settings(self):
        for value in [{'minutes':0},{'rank':2.2},{'distance_patch':1},{'size_min':100,'size_max':2},{'size_max':float('nan')},{'school':'bad'},{'extra':1}]:
            with self.subTest(value=value),self.assertRaises(ValueError):options(value)
