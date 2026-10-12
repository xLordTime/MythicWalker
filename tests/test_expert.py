import asyncio
from enum import Enum
import json
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from expert import compile_expert,ExpertVM
from block_library import BlockLibrary
from playstyle import parse_style,condition_passes,play_round

class FakeBridge:
    def __init__(self):
        self.lock=asyncio.Lock();self.messages=[];self.actions=[]
        self.clients=[Obj(process_id=i,title='p'+str(i),in_battle=AsyncMock(return_value=i==1),is_loading=AsyncMock(return_value=False),is_in_dialog=AsyncMock(return_value=False),zone_name=AsyncMock(return_value='Zone'+str(i)),stats=Obj(current_hitpoints=AsyncMock(return_value=20),max_hitpoints=AsyncMock(return_value=100))) for i in [1,2]]
        self.adapter=Obj(selected=lambda ids:[self.clients[int(i)-1] for i in ids],Keycode=Enum('Keycode',{'W':1,'X':2}),XYZ=lambda x,y,z:Obj(x=x,y=y,z=z))
    async def log(self,message,*args):self.messages.append(message)
    async def send(self,message):pass
    async def protected_step(self,op,args):self.actions.append((op,args))

class ExpertTests(unittest.IsolatedAsyncioTestCase):
    def defaults(self):return BlockLibrary(json.loads((Path(__file__).resolve().parents[1]/'bridge/web/default-library.json').read_text())).merged()
    async def test_original_catalog_compiles_all_twelve_bots(self):
        for bot in json.loads((Path(__file__).resolve().parents[1]/'dist/upstream-bots.json').read_text()):
            with self.subTest(bot=bot['name']):self.assertGreater(compile_expert(bot['source'],self.defaults())['instructions'],0)
    async def test_constants_counters_conditions_return_and_formatted_log(self):
        source='''con count = 0
block interact {
    p1 sendkey X, .1
    return
    p2 sendkey W, .1
}
loop 3 times {
    addone count
    call interact
}
if any incombat {
    sameany sendkey W, .1
} elif mass loading {
    kill
} else {
    log "unexpected"
}
log $count
'''
        bridge=FakeBridge();vm=ExpertVM(bridge,compile_expert(source),['1','2']);await vm.run()
        self.assertEqual(len(bridge.actions),4)
        self.assertTrue(all(a[1]['ids']==['1'] for a in bridge.actions));self.assertIn('Bot: 3.0',bridge.messages)
    async def test_library_dependencies_and_existing_convenience_commands(self):
        bridge=FakeBridge();vm=ExpertVM(bridge,compile_expert('call entry',{'entry':'call helper\nmass speed 150','helper':'p2 sendkey W, .2'}),['1','2']);await vm.run()
        self.assertEqual([a[0] for a in bridge.actions],['key','speed']);self.assertEqual(bridge.actions[1][1]['ids'],['1','2'])
    async def test_unknown_unsafe_or_unavailable_commands_rejected_before_run(self):
        for source in ['import os','autopet','mass tozone "Unknown"','setdeck "abc"','mass sendkey X, .1\nunknowncmd']:
            with self.subTest(source=source),self.assertRaises(ValueError):compile_expert(source)
    async def test_percent_health_condition_and_stop_sleep(self):
        bridge=FakeBridge();vm=ExpertVM(bridge,compile_expert('if p1 healthbelow 50% {\np1 sendkey X, .1\n}\nsleep 200'),['1'])
        task=asyncio.create_task(vm.run());await asyncio.sleep(.01);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(len(bridge.actions),1)
    async def test_parallel_actions_and_except_selector(self):
        bridge=FakeBridge();vm=ExpertVM(bridge,compile_expert('p1 sendkey X, .1 && p2 sendkey W, .1\nmass except p1 sendkey X, .1'),['1','2']);await vm.run()
        self.assertEqual(len(bridge.actions),3);self.assertEqual(bridge.actions[-1][1]['ids'],['2'])

    async def test_documented_timers_parallel_defaults_and_quoted_zone(self):
        bridge=FakeBridge();vm=ExpertVM(bridge,compile_expert('settimer farm\nif p1 inzone "Zone1" {\np1 sendkey X && p2 sendkey W\n}\nendtimer farm'),['1','2']);await vm.run()
        self.assertEqual(len(bridge.actions),2)
        self.assertTrue(any('Timer farm:' in message for message in bridge.messages))

    async def test_real_bridge_validate_run_and_stop_expert_routes(self):
        from server import Bridge
        fake=FakeBridge();fake.adapter.execute=AsyncMock(return_value=[])
        bridge=Bridge(fake.adapter,'fixture',[],False)
        checked=await bridge.dispatch('validate_script',{'engine':'deimos','source':'p1 sendkey X\nsleep 200'})
        self.assertEqual(checked['engine'],'deimos');json.dumps(checked)
        started=await bridge.dispatch('run_script',{'engine':'deimos','source':'p1 sendkey X\nsleep 200','ids':['1']})
        self.assertEqual(started['engine'],'deimos')
        await asyncio.sleep(.01);await bridge.dispatch('stop',{})
        self.assertIsNone(bridge.script_task);fake.adapter.execute.assert_awaited_once()

class PlaystyleTests(unittest.IsolatedAsyncioTestCase):
    def test_priorities_enchants_rounds_targets_and_unavailable_verbs(self):
        rules=parse_style('###p1\n{1} any<blade>[sharp] @ ally(1) | pass\n?(self.health < 30%) any<heal> @ self | any<damage&aoe>[Epic] @ enemies')
        self.assertEqual(len(rules),4);self.assertEqual(rules[0]['round'],1);self.assertEqual(rules[0]['moves'][0]['enchants'][0]['name'],'sharpened')
        with self.assertRaisesRegex(ValueError,'noch nicht verfügbar'):parse_style('any<gambit(harmful_wards,3)> @ enemy')
    async def test_health_condition_and_named_card_cast_without_cursor_leak(self):
        member=Obj(health=AsyncMock(return_value=20),max_health=AsyncMock(return_value=100))
        card=Obj(name=AsyncMock(return_value='Heal'),display_name=AsyncMock(return_value='Heal'),is_castable=AsyncMock(return_value=True),cast=AsyncMock())
        handler=Obj(get_client_member=AsyncMock(return_value=member),get_cards=AsyncMock(return_value=[card]))
        async def action(c,fn,*args,**kwargs):return await fn(*args,**kwargs)
        adapter=Obj(CombatHandler=lambda c:handler,mouse_action=action)
        self.assertTrue(await play_round(adapter,Obj(),parse_style('?(self.health < 30%) Heal @ self'),1));card.cast.assert_awaited_once_with(member)
