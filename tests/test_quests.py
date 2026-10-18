import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).parents[1]/'bridge'))
from quest_tracker import QuestReader, clean


def data(key, goals=None):
    return SimpleNamespace(name_lang_key=AsyncMock(return_value=key),mainline=AsyncMock(return_value=True),
        ready_to_turn_in=AsyncMock(return_value=False),goal_data=AsyncMock(return_value=goals or {}),
        goal_destination_zone=AsyncMock(return_value='WizardCity/Commons'),goal_type=AsyncMock(return_value=SimpleNamespace(name='persona')))


def client():
    goal=data('Quest_2');q=data('Quest_1',{8:goal})
    root=SimpleNamespace(file_path='Root.wad',names=AsyncMock(return_value=['Locale/de-DE/Quest.lang','Locale/en-US/Quest.lang']),get_file=AsyncMock(return_value=b'local data'))
    cache=SimpleNamespace(_root_wad=root,_parse_lang_file=lambda raw:{'Quest':{'1':'<center>Erste Schritte</center>','2':'Sprich mit Merle'}})
    c=SimpleNamespace(process_id=42,is_loading=AsyncMock(return_value=False),quest_id=AsyncMock(return_value=7),goal_id=AsyncMock(return_value=8),zone_name=AsyncMock(return_value='WizardCity/Commons'),
        quest_manager=AsyncMock(return_value=SimpleNamespace(quest_data=AsyncMock(return_value={7:q}))),cache_handler=cache,
        root_window=SimpleNamespace(get_child_by_name=AsyncMock(side_effect=ValueError('HUD hidden'))))
    return c,q,goal

class QuestTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_ids_local_german_and_active_goal(self):
        c,q,g=client();reader=QuestReader();result=await reader.read(c)
        self.assertEqual(result['status'],'ready');self.assertEqual(result['active_id'],'7');self.assertEqual(result['goal_id'],'8')
        self.assertEqual(result['quests'][0]['name'],'Erste Schritte');self.assertEqual(result['quests'][0]['language'],'de-DE')
        self.assertEqual(result['quests'][0]['goals'][0]['name'],'Sprich mit Merle')
        self.assertEqual(result['quests'][0]['world'],'WizardCity')
        c.cache_handler._root_wad.get_file.assert_awaited_once_with('Locale/de-DE/Quest.lang')
        await reader.read(c);self.assertEqual(c.cache_handler._root_wad.get_file.await_count,1)
    async def test_transition_drops_mixed_journal(self):
        c,_,_=client();c.quest_id.side_effect=[7,9]
        result=await QuestReader().read(c)
        self.assertEqual(result['status'],'transition');self.assertEqual(result['quests'],[]);self.assertIsNone(result['active_id'])
    async def test_loading_does_not_read_memory_journal(self):
        c,_,_=client();c.is_loading.return_value=True
        result=await QuestReader().read(c)
        self.assertEqual(result['status'],'loading');c.quest_manager.assert_not_awaited();c.quest_id.assert_not_awaited()
    async def test_no_active_quest(self):
        c,_,_=client();c.quest_id.return_value=0
        self.assertEqual((await QuestReader().read(c))['status'],'no_active');c.quest_manager.assert_not_awaited()
    async def test_missing_metadata_preserves_id_without_guessing_name(self):
        c,_,_=client();c.quest_manager.return_value.quest_data.return_value={}
        result=await QuestReader().read(c)
        self.assertEqual(result['active_id'],'7');self.assertEqual(result['quests'][0]['name'],'Quest 7')
    async def test_manager_failure_keeps_verified_active_ids(self):
        c,_,_=client();c.quest_manager.side_effect=ValueError('pattern unavailable')
        result=await QuestReader().read(c)
        self.assertFalse(result['metadata_available']);self.assertEqual(result['active_id'],'7')
        self.assertEqual(result['goal_id'],'8');self.assertEqual(result['quests'][0]['name'],'Quest 7')
    async def test_language_failure_keeps_key_and_live_id(self):
        c,_,_=client();c.cache_handler._root_wad.get_file.side_effect=OSError('missing WAD')
        result=await QuestReader().read(c)
        self.assertEqual(result['quests'][0]['name'],'Quest_1');self.assertEqual(result['active_id'],'7')
    async def test_unhook_or_closed_client_does_not_fabricate_state(self):
        c,_,_=client();c.quest_id.side_effect=RuntimeError('closed')
        with self.assertRaises(RuntimeError):await QuestReader().read(c)
    async def test_bridge_route_requires_one_hooked_client(self):
        from server import Bridge
        from adapter import DemoAdapter
        adapter=DemoAdapter();bridge=Bridge(adapter,'test-token',[],False)
        bridge.quest_reader.read=AsyncMock(return_value={'id':'9001','active_id':'7'})
        with self.assertRaises(ValueError):await bridge.dispatch('quest_status',{'ids':['9001']})
        await adapter.hook(['9001'])
        result=await bridge.dispatch('quest_status',{'ids':['9001']})
        self.assertEqual(result['active_id'],'7');bridge.quest_reader.read.assert_awaited_once()
        for ids in [[],['9001','9002'],'9001']:
            with self.assertRaises(ValueError):await bridge.dispatch('quest_status',{'ids':ids})
    def test_game_markup_is_cleaned(self):self.assertEqual(clean('<center>Hallo &amp; Welt</center>'),'Hallo & Welt')

if __name__=='__main__':unittest.main()
