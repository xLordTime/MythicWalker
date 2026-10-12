import asyncio
import ast
import contextlib
import inspect
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge'))
from raids import Raids, RaidSession, ClientProxy, native_modules
from raid_catalog import CATALOG
from test_fishing import Reader

class RaidTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.a=types.SimpleNamespace(process_id=11,title='Account A',is_loading=AsyncMock(return_value=False),in_battle=AsyncMock(return_value=False),send_key=AsyncMock(),teleport=AsyncMock())
        self.b=types.SimpleNamespace(process_id=22,title='Account B',is_loading=AsyncMock(return_value=False),in_battle=AsyncMock(return_value=False),send_key=AsyncMock(),teleport=AsyncMock())
        self.bridge=types.SimpleNamespace(demo=False,fishing=types.SimpleNamespace(running=False),script_task=None,automations=types.SimpleNamespace(state=lambda:{}),adapter=types.SimpleNamespace(selected=lambda ids:[{'11':self.a,'22':self.b}[p] for p in ids],fishing_patches={}),send=AsyncMock(),log=AsyncMock(),cleanup_error=None)
        self.raids=Raids(self.bridge)
    async def test_selected_client_not_foreground(self):
        class Utils:
            def __init__(s,c):s.client=c
            async def handle_basic_teleport(s,*args,**kwargs):await s.client.teleport(*args,**kwargs)
        module=types.SimpleNamespace(Utils=Utils)
        with patch('raids.native_modules',return_value={'ds':module}):
            await self.raids.start(['22'],'ds','mana_ranch_teleport')
            await self.raids.task
        self.a.teleport.assert_not_called()
        self.b.teleport.assert_awaited_once_with(7850.18017578125,11077.51953125,30.008514404296875)
        self.assertFalse(self.raids.running)
    async def test_reject_conflicts_bad_actions_and_client_counts(self):
        for args in [([], 'ds','mana_ranch_teleport'),(['11','22'],'ds','mana_ranch_teleport'),(['11'],'invalid','mana_ranch_teleport'),(['11'],'ds','__init__')]:
            with self.assertRaises(ValueError):await self.raids.start(*args)
        self.bridge.fishing.running=True
        with self.assertRaisesRegex(ValueError,'Fisch'):await self.raids.start(['11'],'ds','mana_ranch_teleport')
        self.bridge.fishing.running=False;self.a.is_loading.return_value=True
        with self.assertRaisesRegex(ValueError,'Ladebildschirm'):await self.raids.start(['11'],'ds','mana_ranch_teleport')
    async def test_stop_drains_key_up_before_finishing(self):
        started=asyncio.Event();release=asyncio.Event();done=[]
        async def key(*args):started.set();await release.wait();done.append('key-up')
        self.a.send_key=key
        class Utils:
            def __init__(s,c):s.client=c
            async def auto_raid_drums(s):await s.client.send_key('X')
        with patch('raids.native_modules',return_value={'ds':types.SimpleNamespace(Utils=Utils)}):
            await self.raids.start(['11'],'ds','auto_drums');await started.wait()
            stop=asyncio.create_task(self.raids.stop());await asyncio.sleep(.01)
            self.assertFalse(stop.done());release.set();await stop
        self.assertEqual(done,['key-up']);self.assertFalse(self.raids.running)
    async def test_stop_before_first_task_tick(self):
        class Utils:
            def __init__(s,c):pass
            async def auto_raid_drums(s):await asyncio.sleep(20)
        with patch('raids.native_modules',return_value={'ds':types.SimpleNamespace(Utils=Utils)}):
            await self.raids.start(['11'],'ds','auto_drums');await self.raids.stop()
        self.assertFalse(self.raids.data['running'])
    async def test_partial_raid_fish_patch_restores_before_stop(self):
        reader=Reader();reader.memory[100]=b'original';reader.fail_at=100;self.a._pymem=reader
        module=types.SimpleNamespace(MemoryReader=lambda p:p)
        class Utils:
            def __init__(s,c):pass
            async def patch_fish(s,c):await module.MemoryReader(c._pymem).write_bytes(100,b'PATCH')
            async def catch_fish(s,*args):raise AssertionError('Must not fish after patch failure')
        module.Utils=Utils
        with patch('raids.native_modules',return_value={'az':module}),patch('raids.native_flush',return_value=lambda *args:None):
            await self.raids.start(['11'],'az','catch_fire_fish');await self.raids.task
        self.assertEqual(reader.memory[100],b'original');self.assertTrue(self.raids.data['restored']);self.assertEqual(self.bridge.adapter.fishing_patches,{})
    async def test_failed_restore_blocks_further_writes_and_retains_journal(self):
        reader=Reader();reader.memory[100]=b'original';reader.original[100]=b'original';self.a._pymem=reader
        module=types.SimpleNamespace(MemoryReader=lambda p:p)
        class Utils:
            def __init__(s,c):pass
            async def patch_fish(s,c):await module.MemoryReader(c._pymem).write_bytes(100,b'PATCH')
            async def catch_fish(s,*args):reader.bad_restore=True
        module.Utils=Utils
        with patch('raids.native_modules',return_value={'az':module}),patch('raids.native_flush',return_value=lambda *args:None):
            await self.raids.start(['11'],'az','catch_fire_fish');await self.raids.task
        self.assertFalse(self.raids.data['restored']);self.assertIsNotNone(self.bridge.cleanup_error);self.assertIn('11',self.bridge.adapter.fishing_patches)
        with self.assertRaises(RuntimeError):await self.raids.stop()
        reader.bad_restore=False;await self.bridge.adapter.fishing_patches['11'].restore();self.assertEqual(reader.memory[100],b'original')
    async def test_ambiguous_patterns_do_not_write(self):
        reader=Reader();reader.ambiguous=True;self.a._pymem=reader;module=types.SimpleNamespace(MemoryReader=lambda p:p)
        with patch('raids.native_flush',return_value=lambda *args:None):session=RaidSession(module,self.a,lambda t:None)
        with self.assertRaisesRegex(RuntimeError,'eindeutig'):await module.MemoryReader(reader).pattern_scan(b'abc')
        self.assertFalse(session.journal.entries);session.release()
    async def test_wisp_resolves_fresh_entity_on_selected_client(self):
        ent=types.SimpleNamespace(global_id_full=AsyncMock(return_value=42))
        self.b.get_base_entities_with_name=AsyncMock(return_value=[ent]);seen=[]
        class Utils:
            def __init__(s,c):seen.append(c.process_id)
            async def wisp_teleport(s,e):seen.append(e)
        with patch('raids.native_modules',return_value={'ms':types.SimpleNamespace(Utils=Utils)}):
            await self.raids.start(['22'],'ms','wisp_target','42');await self.raids.task
        self.assertEqual(seen,[22,ent])

class RaidCatalogTests(unittest.TestCase):
    def test_every_catalog_action_has_a_native_method_and_valid_arguments(self):
        for raid in CATALOG:
            tree=ast.parse((ROOT/f'bridge/vendor/raids/{raid["id"]}.py').read_text())
            # Compile headless classes without Windows imports, with deferred annotations.
            tree.body=[n for n in tree.body if isinstance(n,ast.ClassDef)]
            code=compile(ast.fix_missing_locations(tree),'<raid>', 'exec',flags=__import__('__future__').annotations.compiler_flag)
            ns={};exec(code,ns);cls=ns['Utils']
            for action in raid['actions']:
                if action['method']=='list_wisps':continue
                inspect.signature(getattr(cls,action['method'])).bind(None,*action['args'],**action['kwargs'])
        self.assertEqual(len(CATALOG),5)
    @unittest.skipUnless(sys.platform=='win32','Requires Windows game dependencies')
    def test_native_dependencies_import(self):
        self.assertEqual(set(native_modules()),{'ds','az','pl','lm','ms'})

class OriginalRaidUtilityTests(unittest.IsolatedAsyncioTestCase):
    def module(self,raid):
        tree=ast.parse((ROOT/f'bridge/vendor/raids/{raid}.py').read_text())
        tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
        xyz=lambda x,y,z:types.SimpleNamespace(x=x,y=y,z=z)
        ns=dict(XYZ=xyz,asyncio=asyncio,MemoryReader=lambda p:p,print=lambda *args:None)
        exec(compile(ast.fix_missing_locations(tree),'<raid>','exec',flags=__import__('__future__').annotations.compiler_flag),ns)
        return types.SimpleNamespace(**ns),ns
    async def test_actual_fifteen_raid_fish_patches_restore(self):
        module,ns=self.module('az');reader=Reader();client=types.SimpleNamespace(_pymem=reader,title='Selected')
        with patch('raids.native_flush',return_value=lambda *a:None):session=RaidSession(module,client,lambda s:None)
        ns['MemoryReader']=module.MemoryReader
        originals=await module.Utils(client).patch_fish(client)
        self.assertEqual(len(originals),15);self.assertEqual(len(session.journal.entries),15)
        await session.restore()
        for address,original in originals:self.assertEqual(await reader.read_bytes(address,len(original)),original)
        session.release()
    async def test_actual_patch_failure_has_no_background_writes(self):
        module,ns=self.module('az');reader=Reader();reader.fail_at=1256;client=types.SimpleNamespace(_pymem=reader,title='Selected')
        with patch('raids.native_flush',return_value=lambda *a:None):session=RaidSession(module,client,lambda s:None)
        ns['MemoryReader']=module.MemoryReader
        with self.assertRaisesRegex(RuntimeError,'partial write'):await module.Utils(client).patch_fish(client)
        self.assertEqual(len(session.journal.entries),3)
        await session.restore();snapshot=dict(reader.memory);await asyncio.sleep(.01)
        self.assertEqual(reader.memory,snapshot);self.assertEqual(reader.memory,reader.original)
        session.release()
    async def test_auto_drums_targets_filtered_drum_not_excluded_last_entry(self):
        module,ns=self.module('ds');seen=[];removed=False
        excluded=types.SimpleNamespace(location=AsyncMock(return_value=ns['excluded_drums'][0]))
        async def entities(name):
            nonlocal removed
            if removed:removed=False;return []
            return [types.SimpleNamespace(location=AsyncMock(return_value='TARGET'),global_id_full=AsyncMock(return_value=len(seen))),excluded]
        async def teleport(pos):
            nonlocal removed
            seen.append(pos);removed=True
        client=types.SimpleNamespace(title='Selected',get_base_entities_with_name=entities,teleport=teleport)
        util=module.Utils(client);util.are_xyzs_within_threshold=lambda pos,ex:pos!='TARGET'
        ns['asyncio']=types.SimpleNamespace(sleep=AsyncMock(),CancelledError=asyncio.CancelledError)
        await util.auto_raid_drums()
        self.assertEqual(seen,['TARGET']*8)
