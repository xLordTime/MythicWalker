import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge'))
from botlang import compile_bot, interpret
from block_library import BlockLibrary
from adapter import DemoAdapter
from server import Bridge
DEFAULTS=json.loads((ROOT/'dist/default-library.json').read_text())
LIB={b['name']:b['source'] for b in DEFAULTS}

class CompilerTests(unittest.TestCase):
    def test_user_example_uses_default_without_definition(self):
        p=compile_bot('##deimos_expertmode\ntimes 999999 {\ncall safe_mob_pull\nif incombat {\nmass waitforcombat completion\n}\nsleep 0.5\nmass sendkey W, 0.2\nsleep 3\n}',LIB)
        self.assertEqual(p['body'][0]['count'],999999)
        self.assertLess(p['instructions'],100)
        self.assertEqual(p['blocks']['safe_mob_pull'][0]['body'][0]['else'][0]['op'],'closest_mob')
    def test_inline_override_and_dependencies(self):
        p=compile_bot('block safe_mob_pull {\nsleep 0\n}\ncall safe_mob_pull',LIB)
        self.assertEqual(p['blocks']['safe_mob_pull'],[{'op':'sleep','seconds':0.,'line':2}])
    def test_unknown_recursive_invalid_blocks(self):
        for source,library in [('call absent',{}),('call a',{'a':'call b','b':'call a'}),('call a',{'a':'call a'}),('break',{}),('if incombat {\nbreak\n}',{}),('times 1000000 {\nsleep 0\n}',{}),('call a',{'a':'block b {\nsleep 0\n}'})]:
            with self.subTest(source=source,library=library),self.assertRaises(ValueError):compile_bot(source,library)
    def test_persistence_and_rejected_update_leave_previous(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'blocks.json';store=BlockLibrary(DEFAULTS,path)
            store.update({'mine':'call step_forward'})
            self.assertEqual(BlockLibrary(DEFAULTS,path).custom,{'mine':'call step_forward'})
            with self.assertRaises(ValueError):store.update({'mine':'call missing'})
            self.assertEqual(BlockLibrary(DEFAULTS,path).custom,store.custom)
    def test_upstream_import_actual_basic_bots(self):
        bots=json.loads((ROOT/'dist/upstream-bots.json').read_text())
        results={}
        for bot in bots:
            try:compile_bot(bot['source'],LIB);results[bot['name']]=True
            except ValueError:results[bot['name']]=False
        for name in ['Foulgaze','PublishTest1','Harvest Lord Test']:self.assertTrue(results[name])
        self.assertEqual(len(bots),12)

class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_call_condition_break_and_fallback(self):
        program=compile_bot('times 4 {\ncall pull\nsleep 0.5\n}',{'pull':'times 10 {\nif incombat {\nbreak\n} else {\nmass sendkey X, 0.1\n}\n}'})
        count=0;executed=[]
        async def check(c):
            nonlocal count
            count+=1
            return count>2
        async def execute(n):executed.append(n['op'])
        await interpret(program,execute,check,AsyncMock())
        self.assertEqual(executed,['key','key','sleep','sleep','sleep','sleep'])
    async def test_sleep_free_loop_can_stop(self):
        p=compile_bot('loop {\nif incombat {\nbreak\n} else {\nsleep 0\n}\n}')
        task=asyncio.create_task(interpret(p,AsyncMock(),AsyncMock(return_value=False),AsyncMock()))
        await asyncio.sleep(.04);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await asyncio.wait_for(task,.2)
    async def test_real_dispatch_library_persistence_and_runtime(self):
        adapter=DemoAdapter();await adapter.hook(['9001'])
        b=Bridge(adapter,'test',[])
        await b.dispatch('set_block_library',{'blocks':{'mine':'mass sendkey W, 0.01'}})
        result=await b.dispatch('validate_script',{'source':'call mine'})
        self.assertGreater(result['steps'],0)
        execute=AsyncMock(return_value={'ok':True});adapter.execute=execute
        await b.dispatch('run_script',{'source':'call mine','ids':['9001']})
        await b.script_task
        self.assertEqual(execute.await_args.args[0],'key')
        self.assertEqual(execute.await_args.args[1]['ids'],['9001'])
    async def test_auto_combat_and_manual_cast_rejected(self):
        adapter=DemoAdapter();await adapter.hook(['9001']);b=Bridge(adapter,'test',[])
        with self.assertRaises(ValueError):await b.dispatch('run_script',{'source':'p1 cast "x" @self','ids':['9001'],'auto_combat':True})
        self.assertFalse(b.automations.state()['combat'])
    async def test_zone_change_before_wait_is_recognized(self):
        adapter=DemoAdapter();await adapter.hook(['9001']);b=Bridge(adapter,'test',[])
        original=adapter.execute
        async def execute(op,args):
            result=await original(op,args)
            if op=='key':adapter.rows[0]['zone']='NewZone'
            return result
        adapter.execute=execute
        await b.dispatch('run_script',{'source':'mass sendkey X, 0.01\nmass waitforzonechange completion','ids':['9001']})
        await asyncio.wait_for(b.script_task,.5)
