import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from protocol import parse_script
from adapter import DemoAdapter
from server import Bridge

class ExpandedScriptTests(unittest.TestCase):
    def test_nested_repeats_keep_line_and_client_target(self):
        steps=parse_script('times 2 {\n times 2 {\n  p2 cast "LifeBlade" @self\n }\n mass pass\n}')
        self.assertEqual(len(steps),6)
        self.assertEqual(steps[0],{'target':'p2','line':3,'op':'cast','name':'LifeBlade','card_target':'self'})
    def test_bounds_and_malformed_blocks(self):
        for source in ['times 0 {\nsleep 1\n}','times 51 {\nsleep 1\n}','times 2 {\n}','times 2 {\nsleep 1','}','times 50 {\ntimes 50 {\nsleep 1\n}\n}','mass waitforwindow "a" 121']:
            with self.subTest(source=source),self.assertRaises(ValueError):parse_script(source)
    def test_new_commands(self):
        steps=parse_script('mass tp navquest\np1 freecam\np1 tp camera\nmass waitforloading completion\np1 tp nearest "Chest"\nmass waitforwindow "NPCRangeWin" 30')
        self.assertEqual([s['op'] for s in steps],['navmap_tp','freecam','camera_tp','wait_loading','nearest_entity','wait_window'])

class ExpandedRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_targets_and_repeat_execution(self):
        adapter=DemoAdapter();await adapter.hook(['9001','9002'])
        adapter.execute=AsyncMock(return_value={'ok':True})
        bridge=Bridge(adapter,'test',[],True)
        await bridge.run_script(parse_script('times 2 {\np2 cast "LifeBlade" @self\n}\nmass tp navquest'),['9001','9002'])
        calls=adapter.execute.await_args_list
        self.assertEqual(len(calls),3)
        self.assertEqual(calls[0].args[1]['ids'],['9002'])
        self.assertEqual(calls[0].args[1]['target'],'self')
        self.assertEqual(calls[-1].args[1]['ids'],['9001','9002'])
        self.assertEqual(calls[-1].args[1]['target'],'own')
    async def test_stop_interrupts_condition_wait(self):
        adapter=DemoAdapter();await adapter.hook(['9001'])
        entered=asyncio.Event()
        async def condition(*args):entered.set();return False
        adapter.wait_condition=condition
        bridge=Bridge(adapter,'test',[],True)
        bridge.script_task=asyncio.create_task(bridge.run_script(parse_script('mass waitforwindow "NPCRangeWin" 120'),['9001']))
        await entered.wait()
        await asyncio.wait_for(bridge.stop(),1)
        self.assertIsNone(bridge.script_task)
