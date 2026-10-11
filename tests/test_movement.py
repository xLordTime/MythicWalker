import asyncio
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from adapter import DemoAdapter,WizAdapter
from server import Bridge
from settings import DEFAULTS,validate,migrate,combat_rules,combo

class MovementTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.b=Bridge(DemoAdapter(),'token',[],True)
        await self.b.dispatch('hook',{'ids':['9001','9002']})
        self.b.shortcut_context={'ids':['9002'],'source':'sleep 1','leader':'9002'}
        self.b.adapter.execute=AsyncMock(wraps=self.b.adapter.execute)
    async def test_interact_all_and_source_sync(self):
        await self.b.dispatch('movement',{'action':'interact'})
        self.b.adapter.execute.assert_awaited_with('key',{'ids':['9001','9002'],'key':'X','seconds':.2})
        await self.b.dispatch('movement',{'action':'sync'})
        self.b.adapter.execute.assert_awaited_with('sync',{'ids':['9001'],'source':'9002'})
    async def test_navmap_selected_all_and_speed_toggle(self):
        await self.b.dispatch('movement',{'action':'quest_tp'})
        args=self.b.adapter.execute.await_args.args[1];self.assertEqual(args['ids'],['9002']);self.assertEqual(args['target'],'own')
        await self.b.dispatch('movement',{'action':'quest_all'})
        args=self.b.adapter.execute.await_args.args[1];self.assertEqual(args['ids'],['9001','9002']);self.assertEqual(args['source'],'9002')
        await self.b.dispatch('movement',{'action':'speed_toggle'});self.assertTrue(self.b.adapter.original_speeds)
        await self.b.dispatch('movement',{'action':'speed_toggle'});self.assertFalse(self.b.adapter.original_speeds)
    async def test_automations_mutual_exclusion_and_global_stop(self):
        await self.b.dispatch('movement',{'action':'combat_toggle'})
        await self.b.dispatch('movement',{'action':'questing_toggle'})
        self.assertTrue(self.b.automations.state()['questing'])
        await self.b.dispatch('movement',{'action':'sigil_toggle'})
        self.assertFalse(self.b.automations.state()['questing']);self.assertTrue(self.b.automations.state()['sigil'])
        await self.b.dispatch('stop',{});self.assertFalse(any(self.b.automations.state().values()))
    async def test_auto_combat_selects_once_per_round(self):
        class Card:
            is_castable=AsyncMock(return_value=True)
            name=AsyncMock(return_value='LifeBlade')
            display_name=AsyncMock(return_value='Lebensklinge')
            cast=AsyncMock()
        class Handler:
            def __init__(self,c):pass
            get_cards=AsyncMock(return_value=[Card()])
            get_client_member=AsyncMock(return_value='self')
        import types
        enums=types.ModuleType('wizwalker.memory.memory_objects.enums')
        enums.DuelPhase=types.SimpleNamespace(planning=1)
        from unittest.mock import patch
        client=types.SimpleNamespace(process_id=42,in_battle=AsyncMock(return_value=True),duel=types.SimpleNamespace(duel_phase=AsyncMock(return_value=1),duel_id_full=AsyncMock(return_value=55),round_num=AsyncMock(return_value=3)))
        client.mouse_handler=__import__('unittest.mock',fromlist=['AsyncMock']).AsyncMock()
        adapter=WizAdapter.__new__(WizAdapter);adapter.combat_rounds={};adapter.CombatHandler=Handler
        with patch.dict(sys.modules,{'wizwalker.memory.memory_objects.enums':enums}):
            config={**DEFAULTS['automation'],'combat_rules':'LifeBlade@self'}
            await adapter.combat_step(client,config);await adapter.combat_step(client,config)
        self.assertEqual(Handler.get_cards.await_count,1);self.assertEqual(Card.cast.await_count,1)
        client.mouse_handler.__aenter__.assert_awaited_once()
        client.mouse_handler.__aexit__.assert_awaited_once()

class ConfigurationTests(unittest.TestCase):
    def test_deimos_defaults_and_legacy_migration(self):
        for action,key in [('interact','X'),('sync','F8'),('quest_tp','F7'),('quest_all','F6'),('speed_toggle','F5'),('combat_toggle','9'),('dialogue_toggle','F4'),('questing_toggle','F3'),('sigil_toggle','F2'),('freecam','F1'),('camera_tp','Shift+F1')]:self.assertEqual(DEFAULTS['bindings'][action],key)
        value=migrate({'global_hotkeys':False,'poll_seconds':3,'key_seconds':.3,'bindings':{'hook':'Ctrl+Alt+F3'}})
        self.assertEqual(value['key_seconds'],.3);self.assertEqual(value['bindings']['hook'],'Ctrl+Alt+F3');self.assertIn('questing_toggle',value['bindings'])
        self.assertEqual(combo('NINE'),'9')
    def test_settings_and_rules_reject_bad_values(self):
        for group,key,value in [('movement','navmap_timeout',99),('automation','max_minutes',False),('movement','speed_percent',3.5),('automation','combat_rules','eval(x)')]:
            config=copy.deepcopy(DEFAULTS);config[group][key]=value
            with self.assertRaises(ValueError):validate(config)
        self.assertEqual(combat_rules('LifeBlade@self\nany<aoe>@enemy\npass')[1]['name'],'any<aoe>')
