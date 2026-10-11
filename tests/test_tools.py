import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from adapter import WizAdapter,DemoAdapter
from server import Bridge
from protocol import parse_script

class ToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_speed_restores_original_value_on_unhook(self):
        class Object:
            speed_multiplier=AsyncMock(return_value=40)
            write_speed_multiplier=AsyncMock()
        class Client:
            process_id=42
            client_object=Object()
            close=AsyncMock()
            def is_running(self):return True
        c=Client();a=WizAdapter.__new__(WizAdapter)
        a.handler=type('Handler',(),{'clients':[c]})();a.hooked={'42'};a.errors={};a.freecam=set();a.original_speeds={}
        await a.execute('speed',{'ids':['42'],'percent':100})
        await a.execute('speed',{'ids':['42'],'percent':200})
        await a.unhook(['42'])
        self.assertEqual(c.client_object.write_speed_multiplier.await_args.args,(40,))
        self.assertEqual(a.original_speeds,{})
    async def test_dialogue_stops_when_script_starts_and_on_shutdown(self):
        b=Bridge(DemoAdapter(),'token',[],True);await b.dispatch('hook',{'ids':['9001']})
        await b.dispatch('dialogue',{'ids':['9001'],'enabled':True});self.assertFalse(b.dialogue_task.done())
        await b.dispatch('run_script',{'ids':['9001'],'source':'sleep 60'})
        self.assertIsNone(b.dialogue_task)
        await b.dispatch('stop',{})
        await b.dispatch('dialogue',{'ids':['9001'],'enabled':True});await b.shutdown(None)
        self.assertIsNone(b.dialogue_task);self.assertFalse(b.adapter.rows[0]['hooked'])
    async def test_additional_commands_are_bounded(self):
        steps=parse_script('mass tp quest\np1 entitytp "Estate_Clue"\nmass clickwindow "advanceDialogButton"\nmass speed 100\nmass restorespeed')
        self.assertEqual([s['op'] for s in steps],['quest_tp','entity_tp','click_window','speed','restore_speed'])
        for source in ['mass speed 999','mass entitytp "'+('a'*181)+'"','mass clickwindow eval(x)']:
            with self.assertRaises(ValueError):parse_script(source)
