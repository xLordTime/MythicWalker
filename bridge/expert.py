"""Deimos compiler + bounded bridge VM, using the existing DE WizWalker adapter."""
import asyncio
import math
import re
import time
from dataclasses import dataclass
from deimoslang.ir import Compiler, InstructionKind
from deimoslang.parser import Parser
from deimoslang.tokenizer import Tokenizer
from deimoslang.types import *
from deimoslang.expression_vm import ExpressionVM
from protocol import _parse_flat, number, text, xyz
from diagnostics import event

UNSUPPORTED={'autopet':'Pet-Tanz-Hook fehlt im DE-Adapter.', 'tozone':'Weltenübergreifender Navigator fehlt im DE-Adapter.',
             'setdeck':'Deck-Preset-Adapter fehlt.', 'getdeck':'Deck-Preset-Adapter fehlt.'}
SUPPORTED_COMMANDS={'teleport','goto','sendkey','waitfor','click','cursor','usepotion','buypotions','relog','select_friend','toggle_combat','set_zone','set_goal','set_quest'}


def prepare_source(source, library):
    if not isinstance(source,str) or len(source)>65536:raise ValueError('Maximal 64 KB Bot.')
    # Wiki also documents `loop N times`, whereas upstream currently parses `times N`.
    source=re.sub(r'(?m)^(\s*)loop\s+(\d+)\s+times\s*{',r'\1times \2 {',source)
    source=re.sub(r'(?m)^(\s*)mass\s+except\s+',r'\1except ',source)
    local=set(re.findall(r'\bblock\s+([A-Za-z_]\w*)',source));needed=set(re.findall(r'\bcall\s+([A-Za-z_]\w*)',source))-local
    appended=[];seen=set();active=set()
    def include(name):
        if name in active:raise ValueError('Rekursiver Bibliotheksblock: '+name)
        if name in local:return
        if name in seen:return
        seen.add(name)
        if name not in library:return
        active.add(name);code=library[name]
        for dependency in re.findall(r'\bcall\s+([A-Za-z_]\w*)',code):include(dependency)
        active.remove(name)
        if not re.match(r'\s*block\s+',code):code=f'block {name} {{\n{code}\n}}'
        appended.append(code)
    for name in sorted(needed):include(name)
    source='\n'.join(appended+[source])
    extensions={};out=[];multiline=False
    def expr(raw):return Parser(Tokenizer().tokenize(raw)).parse_expression()
    def selector(prefix):
        compiled=Compiler.from_text((prefix or 'mass')+' sendkey X, .1').compile()
        return next(i.data[0] for i in compiled if i.kind==InstructionKind.deimos_call)
    def extension(node):
        index=len(extensions);extensions[index]=node;out.append(f'log "__mythic_action_{index}"')
    for line in source.splitlines():
        if multiline:
            out.append(line)
            if line.count('"""')%2:multiline=False
            continue
        if line.count('"""')%2:
            multiline=True;out.append(line);continue
        if counter:=re.fullmatch(r'\s*(addone|minusone|reset|resetcounter)\s+([A-Za-z_]\w*)\s*(?:#.*)?',line):
            extension({'op':'counter','name':counter[2],'change':{'addone':1,'minusone':-1,'reset':None,'resetcounter':None}[counter[1]]});continue
        if timer:=re.fullmatch(r'\s*(settimer|endtimer)\s+([A-Za-z_]\w*)\s*(?:#.*)?',line):
            extension({'op':timer[1],'name':timer[2]});continue
        custom=re.fullmatch(r'\s*(?:(mass|p\d+(?::p\d+)?|except\s+p\d+(?::p\d+)?|any|sameany|p\?)\s+)?(setyaw|set_yaw|nav|friendtp)\s+(.+)',line)
        if custom and (custom[2]!='friendtp' or custom[3].strip().startswith(('"',"'"))):
            extension({'op':custom[2],'selector':selector(custom[1]),'value':expr(custom[3])});continue
        line=re.sub(r'\b(inzone|in_zone)\s+"([A-Za-z0-9_/-]+)"',r'\1 \2',line)
        line=re.sub(r'\b(tp|teleport)\s*([+-])\s*(?=XYZ\()',lambda m:('plustp' if m[2]=='+' else 'minustp')+' ',line,flags=re.I)
        line=re.sub(r'(sendkey\s+[A-Z][A-Z0-9_]*)(\s*&&|\s*$)',r'\1, .1\2',line)
        if re.match(r'^\s*(?:(?:mass|p\d+)\s+)?(?:speed\b|restorespeed\b|freecam\b|tp\s+(?:camera|navquest)\b)',line):
            statement=line.strip()
            if not re.match(r'^(mass|p\d+)\s',statement):statement='mass '+statement
            extension(_parse_flat(statement)[0]);continue
        out.append(line)
    return '\n'.join(out),extensions


def compile_expert(source, library=None):
    try:
        source,extensions=prepare_source(source,library or {})
        program=Compiler.from_text(source).compile()
    except Exception as exc:raise ValueError(f'Deimos: {exc}') from None
    if len(program)>10000:raise ValueError('Maximal 10.000 kompilierte Anweisungen.')
    issues=[];commands=set()
    def scan(value):
        if isinstance(value,PlayerSelector):
            if any(n<1 or n>16 for n in value.player_nums):raise ValueError('Selektoren nur p1–p16.')
        elif isinstance(value,(list,tuple)):
            for item in value:scan(item)
        elif isinstance(value,dict):
            for item in value.values():scan(item)
        elif isinstance(value,(Expression,Command)):
            for item in vars(value).values():scan(item)
    for node in extensions.values():scan(node)
    for instruction in program:
        scan(instruction.data)
        if instruction.kind.name in UNSUPPORTED:issues.append(UNSUPPORTED[instruction.kind.name])
        calls=[instruction.data] if instruction.kind==InstructionKind.deimos_call else instruction.data if instruction.kind==InstructionKind.compound_deimos_call else []
        for selector,kind,data in calls:
            commands.add(kind)
            if kind not in SUPPORTED_COMMANDS:issues.append(UNSUPPORTED.get(kind,'Befehl noch nicht verfügbar: '+kind))
    if issues:raise ValueError(' '.join(dict.fromkeys(issues)))
    return {'program':program,'extensions':extensions,'instructions':len(program),'commands':sorted(commands),'source':source}


@dataclass
class Frame:
    stack:list
    ip:int=0


class ExpertVM(ExpressionVM):
    def __init__(self, bridge, compiled, ids, max_minutes=15):
        self.bridge=bridge;self.adapter=bridge.adapter;self.compiled=compiled;self.program=compiled['program']
        self._clients=self.adapter.selected(ids);self.ids=ids;self.current_task=Frame([])
        self._constants={'True':True,'False':False};self._timers={};self._any_player_client=[];self.untils=[]
        self.logged_data={'zone':{},'quest':{},'goal':{}};self.started=time.monotonic();self.limit=max_minutes*60;self.steps=0;self.last_progress=0
    def _select_players(self,selector):
        if selector is None or selector.mass or selector.wildcard:return self._clients
        if selector.any_player:return self._clients
        if selector.same_any:return self._any_player_client
        if selector.inverted:return [c for i,c in enumerate(self._clients,1) if i not in selector.player_nums]
        missing=[n for n in selector.player_nums if n>len(self._clients)]
        if missing:raise ValueError('Client fehlt in Auswahl: '+str(missing))
        return [self._clients[n-1] for n in selector.player_nums]
    async def eval(self,expr,client=None):
        if not isinstance(expr,Expression):return expr
        if isinstance(expr,ConstantExpression):return await self.eval(expr.value,client)
        if isinstance(expr,StringExpression) and expr.string in {'true','false'}:return expr.string=='true'
        if isinstance(expr,KeyExpression):return self.adapter.Keycode[expr.key]
        if isinstance(expr,XYZExpression):return self.adapter.XYZ(*xyz([await self.eval(expr.x,client),await self.eval(expr.y,client),await self.eval(expr.z,client)]))
        return await super().eval(expr,client)
    async def resolve(self,value,client=None):
        if isinstance(value,IdentExpression) and value.ident in self._constants:return self._constants[value.ident]
        if isinstance(value,list):return [await self.resolve(v,client) for v in value]
        result=await self.eval(value,client)
        return result.strip() if isinstance(result,str) else result
    async def window(self,c,path,required=False):
        path=await self.resolve(path,c)
        if isinstance(path,str):
            matches=await c.root_window.get_windows_with_name(path)
            w=matches[0] if len(matches)==1 else None
        else:
            w=c.root_window
            try:
                for part in path:w=await w.get_child_by_name(part)
            except ValueError:w=None
        if required and w is None:raise ValueError('UI-Pfad fehlt: '+str(path))
        return w
    async def _eval_expression(self,expression,client):
        kind=expression.kind.name;c=client or self._clients[0]
        stat={'health':'current_hitpoints','max_health':'max_hitpoints','mana':'current_mana','max_mana':'max_mana','gold':'current_gold','max_gold':'base_gold_pouch','max_energy':'energy_max','potioncount':'potion_charge','max_potioncount':'potion_max','account_level':'reference_level'}
        if kind in stat:return await getattr(c.stats,stat[kind])()
        if kind=='playercount':return len(self._clients)
        if kind=='any_player_list':return [x.title for x in self._any_player_client]
        if kind=='duel_round':return await c.duel.round_num() if await c.in_battle() else 0
        if kind=='energy':return await c.current_energy()
        if kind in {'bagcount','max_bagcount'}:return (await c.backpack_space())[0 if kind=='bagcount' else 1]
        if kind in {'windowtext','windownum'}:
            w=await self.window(c,expression.args[0]);value=(await w.maybe_text() or '') if w else ''
            if kind=='windowtext':return value.lower()
            return [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?',value)] or [0]
        if kind=='reference_counter':return self._constants.get(str(expression.args[0]),0)
        raise ValueError('Messwert im DE-Adapter noch nicht verfügbar: '+kind)
    async def quest_text(self,c,goal=False):
        if goal:
            w=await self.window(c,['WorldView','windowHUD','QuestHelperHud','ElementWindow','','txtGoalName'])
            if w is None:raise ValueError('Questziel-Tracker nicht sichtbar.')
            return re.sub(r'<[^>]*>','',await w.maybe_text() or '').strip()
        tracked=await c.quest_id();manager=await c.quest_manager()
        quests=await manager.quest_data()
        quest=quests.get(tracked)
        if quest is None:return ''
        key=await quest.name_lang_key()
        return key if key=='Quest Finder' else (await c.cache_handler.get_langcode_name(key)).strip()
    async def _eval_command_expression(self,expr):
        command=expr.command;kind=command.data[0].name;selector=command.player_selector;clients=self._select_players(selector)
        if kind.startswith('same_') or kind=='same_place':
            async def read(c):
                if kind in {'same_zone','same_place'}:return await c.zone_name()
                if kind=='same_quest':return await self.quest_text(c)
                if kind=='same_yaw':return await c.body.yaw()
                p=await c.body.position();return [p.x,p.y,p.z]
            values=[await read(c) for c in clients];return bool(values) and all(v==values[0] for v in values)
        async def check(c):
            args=[await self.resolve(x,c) for x in command.data[1:]]
            if kind=='constant_check':return self._constants.get(args[0])==args[1]
            if kind=='loading':return await c.is_loading()
            if kind=='in_combat':return await c.in_battle()
            if kind=='has_dialogue':return await c.is_in_dialog()
            if kind=='in_zone':return await c.zone_name()==args[0]
            if kind in {'window_visible','window_disabled'}:
                w=await self.window(c,args[0]);return bool(w) and bool(await (w.is_visible() if kind=='window_visible' else w.is_control_grayed()))
            if kind in {'zone_changed','quest_changed','goal_changed'}:
                key=kind.split('_')[0];value=await c.zone_name() if key=='zone' else await self.quest_text(c,key=='goal')
                old=self.logged_data[key].get(str(c.process_id));self.logged_data[key][str(c.process_id)]=value
                return value==args[0] if args else old is not None and old!=value
            if kind in {'tracking_quest','tracking_goal','has_quest'}:
                value=await self.quest_text(c,kind=='tracking_goal');return (args[0].casefold() in value.casefold()) if args else bool(value)
            if kind=='has_xyz':
                p=await c.body.position();target=args[0];return math.dist([p.x,p.y,p.z],[target.x,target.y,target.z])<25
            if kind=='has_yaw':return abs(await c.body.yaw()-float(args[0]))<.05
            if kind=='in_range':
                p=await c.body.position()
                for entity in (await c.get_base_entity_list())[:1000]:
                    name=await entity.object_name()
                    if name and str(args[0]).casefold() in name.casefold():
                        body=await entity.actor_body()
                        if body:
                            point=await body.position()
                            if math.dist([p.x,p.y,p.z],[point.x,point.y,point.z])<1000:return True
                return False
            if kind=='items_dropped':raise ValueError('Drop-Tracking ist noch nicht im DE-Adapter integriert.')
            raise ValueError('Bedingung noch nicht verfügbar: '+kind)
        results=[]
        for c in clients:
            async with self.bridge.lock:results.append(await asyncio.wait_for(check(c),5))
        if selector and selector.any_player:
            self._any_player_client=[c for c,v in zip(clients,results) if v];return any(results)
        return bool(results) and all(results)
    async def action(self,op,c,**args):
        async with self.bridge.lock:return await self.bridge.protected_step(op,{'ids':[str(c.process_id)],**args})
    async def click_path(self,c,path):
        async with self.bridge.lock:
            w=await self.window(c,path,True)
            if not await w.is_visible():raise ValueError('UI-Fenster nicht sichtbar: '+str(path))
            await self.adapter.mouse_action(c,c.mouse_handler.click_window,w)
    async def execute_command(self,entry):
        selector,kind,data=entry;clients=self._select_players(selector)
        if selector.any_player and self._any_player_client:clients=self._any_player_client
        async def one(c):
            args=[await self.resolve(x,c) for x in data]
            if kind=='sendkey':return await self.action('key',c,key=args[0].name,seconds=args[1] if len(args)>1 and args[1] is not None else .1)
            if kind=='teleport':
                mode=args[0].name
                if mode in {'position','plusteleport','minusteleport'}:
                    p=args[1];coords=[p.x,p.y,p.z]
                    if mode!='position':
                        async with self.bridge.lock:old=await c.body.position()
                        sign=1 if mode=='plusteleport' else -1;coords=[old.x+sign*p.x,old.y+sign*p.y,old.z+sign*p.z]
                    return await self.action('teleport',c,xyz=coords)
                if mode=='client_num':
                    target=int(args[1]);other=self._clients[target-1]
                    async with self.bridge.lock:p=await other.body.position()
                    return await self.action('teleport',c,xyz=[p.x,p.y,p.z])
                if mode=='mob':return await self.action('closest_mob',c)
                if mode=='quest':return await self.action('navmap_tp',c,target='own',timeout=20)
                if mode in {'entity_vague','entity_literal'}:return await self.action('nearest_entity' if mode=='entity_vague' else 'entity_tp',c,**({'query':str(args[-1])} if mode=='entity_vague' else {'name':str(args[-1])}))
                if mode in {'friend_name','friend_icon'}:return await self.friend(c,(args[1:] or [0,2]) if mode=='friend_icon' else args[-1],mode=='friend_icon',True)
                if mode=='nav':
                    p=args[1]
                    async with self.bridge.lock:await self.adapter.navmap_teleport(c,p,20)
                    return
                raise ValueError('Teleport-Variante fehlt: '+mode)
            if kind=='goto':
                from wizwalker.utils import calculate_perfect_yaw
                target=args[0]
                async with asyncio.timeout(120):
                    while True:
                        async with self.bridge.lock:
                            current=await c.body.position();distance=math.hypot(target.x-current.x,target.y-current.y)
                            if distance<25:return
                            speed=580*(1+await c.client_object.speed_multiplier()/100)
                            if speed<=0:raise ValueError('Bewegungsgeschwindigkeit ist null.')
                            await c.body.write_yaw(calculate_perfect_yaw(current,target))
                        await self.action('key',c,key='W',seconds=max(.01,min(distance/speed,1)))
            if kind=='waitfor':
                mode=args[0].name;completion=bool(args[-1])
                async with self.bridge.lock:baseline=await c.zone_name()
                async with asyncio.timeout(300):
                    while True:
                        async with self.bridge.lock:
                            if mode=='battle':ready=await c.in_battle()
                            elif mode=='dialog':ready=await c.is_in_dialog()
                            elif mode=='free':ready=not (await c.in_battle() or await c.is_loading() or await c.is_in_dialog())
                            elif mode=='zonechange':ready=not await c.is_loading() if completion else await c.zone_name()!=baseline and not await c.is_loading()
                            else:w=await self.window(c,args[1]);ready=bool(w) and await w.is_visible()
                        if (not ready if completion and mode!='zonechange' else ready):return
                        await asyncio.sleep(.2)
            if kind in {'click','cursor'}:
                mode=args[0].name
                if mode=='window':
                    if kind=='click':return await self.click_path(c,args[1])
                    async with self.bridge.lock:
                        w=await self.window(c,args[1],True);await self.adapter.mouse_action(c,c.mouse_handler.set_mouse_position_to_window,w)
                else:
                    async with self.bridge.lock:await self.adapter.mouse_action(c,c.mouse_handler.click if kind=='click' else c.mouse_handler.set_mouse_position,int(number(args[1],0,16384)),int(number(args[2],0,16384)))
                return
            if kind=='usepotion':
                if args:
                    async with self.bridge.lock:
                        hp=await c.stats.current_hitpoints();maxhp=await c.stats.max_hitpoints();mp=await c.stats.current_mana();maxmp=await c.stats.max_mana()
                    if hp>=maxhp*number(args[0],0,100)/100 and mp>=maxmp*number(args[1],0,100)/100:return
                return await self.click_path(c,['WorldView','windowHUD','btnPotions'])
            if kind=='buypotions':return await self.buy_potions(c,bool(args[0]) if args else False)
            if kind=='relog':
                await self.action('key',c,key='ESC',seconds=.1)
                await self.wait_visible_click(c,['WorldView','DeckConfiguration','SettingPage','QuitButton'])
                await self.wait_visible_click(c,['WorldView','mainWindow','btnPlay']);await asyncio.sleep(4);return
            if kind=='select_friend':return await self.friend(c,args[0],False,False)
            if kind.startswith('set_'):
                key=kind.split('_')[1];self.logged_data[key][str(c.process_id)]=await c.zone_name() if key=='zone' else await self.quest_text(c,key=='goal');return
            if kind=='toggle_combat':
                enabled=bool(args[0]) if args else not self.bridge.automations.state()['combat']
                await self.bridge.automations.toggle('combat',[str(x.process_id) for x in clients],enabled,from_script=True);return
            raise ValueError('Spielbefehl nicht verfügbar: '+kind)
        if kind=='toggle_combat':
            if clients:await one(clients[0])
        else:
            async with asyncio.TaskGroup() as group:
                for c in clients:group.create_task(one(c))
    async def wait_visible_click(self,c,path):
        async with asyncio.timeout(15):
            while True:
                async with self.bridge.lock:w=await self.window(c,path)
                if w and await w.is_visible():await self.click_path(c,path);return
                await asyncio.sleep(.2)
    async def buy_potions(self,c,ifneeded):
        async with self.bridge.lock:
            if ifneeded and await c.stats.potion_charge()>=await c.stats.potion_max():return
            zone=await c.zone_name()
        if zone!='WizardCity/WC_Hub':raise ValueError('buypotions: derzeit nur bei Hilda in WizardCity/WC_Hub. Automatische Weltreise fehlt.')
        await self.action('teleport',c,xyz=[-4398.7065,1016.1954,229.0008]);await self.action('key',c,key='X',seconds=.1)
        await self.wait_visible_click(c,['WorldView','main','fillallpotions']);await self.click_path(c,['WorldView','main','buyAction'])
        await self.action('key',c,key='ESC',seconds=.1)
    async def friend(self,c,name,icon,teleport):
        from wizwalker.extensions.scripting.utils import (teleport_to_friend_from_list,_maybe_get_named_window,_cycle_to_online_friends,_cycle_friends_list,_click_on_friend)
        async with self.bridge.lock:
            async with asyncio.timeout(25):
                async with c.mouse_handler:
                    if teleport:
                        if icon:
                            await teleport_to_friend_from_list(c,icon_index=int(name[0]),icon_list=int(name[1]))
                        else:await teleport_to_friend_from_list(c,name=text(str(name)))
                        return
                    friends=await _maybe_get_named_window(c.root_window,'NewFriendsListWindow')
                    if not await friends.is_visible():
                        button=await _maybe_get_named_window(c.root_window,'btnFriends');await c.mouse_handler.click_window(button)
                    await _cycle_to_online_friends(c,friends)
                    listing=await _maybe_get_named_window(friends,'listFriends');right=await _maybe_get_named_window(friends,'btnArrowDown');page=await _maybe_get_named_window(friends,'PageNumber')
                    current=int(re.sub(r'<[^>]*>','',await page.maybe_text()).split('/')[0])
                    match,index=await _cycle_friends_list(c,right,listing,None,None,str(name),current)
                    if match is None:raise ValueError('Freund nicht online gefunden: '+str(name))
                    await _click_on_friend(c,listing,index)
    async def step(self):
        frame=self.current_task
        for index,condition,exit_ip,size in reversed(self.untils):
            if await self.eval(condition):frame.ip=exit_ip;break
        if not 0<=frame.ip<len(self.program):return False
        instruction=self.program[frame.ip];kind=instruction.kind.name;data=instruction.data;next_ip=frame.ip+1
        if kind=='declare_constant':
            value=await self.eval(data[1])
            if isinstance(value,str) and value.strip() in self.adapter.Keycode.__members__:value=self.adapter.Keycode[value.strip()]
            self._constants[data[0]]=value
        elif kind=='set_timer':self._timers[data]=time.monotonic()
        elif kind=='end_timer':await self.bridge.log(f'Timer {data}: {time.monotonic()-self._timers.pop(data):.2f}s')
        elif kind=='kill':return False
        elif kind=='restart_bot':frame.stack.clear();self.untils.clear();next_ip=0
        elif kind=='sleep':await asyncio.sleep(number(await self.eval(data),0,300))
        elif kind=='jump':next_ip=frame.ip+data
        elif kind in {'jump_if','jump_ifn'}:
            condition=bool(await self.eval(data[0]))
            if condition==(kind=='jump_if'):next_ip=frame.ip+data[1]
        elif kind=='call':
            if len(frame.stack)>128:raise ValueError('Aufruf-/Variablenstack zu tief.')
            frame.stack.append(next_ip);next_ip=frame.ip+data
        elif kind=='ret':next_ip=frame.stack.pop()
        elif kind=='enter_until':self.untils.append((data[1],data[0],frame.ip+data[2],len(frame.stack)))
        elif kind=='exit_until':
            for i,entry in enumerate(self.untils):
                if entry[0]==data:self.untils=self.untils[:i];frame.stack=frame.stack[:entry[3]];break
        elif kind=='push_stack':frame.stack.append(None)
        elif kind=='pop_stack':frame.stack.pop()
        elif kind=='write_stack':frame.stack[data[0]]=await self.eval(data[1])
        elif kind=='deimos_call':await self.execute_command(data)
        elif kind=='compound_deimos_call':
            async with asyncio.TaskGroup() as group:
                for entry in data:group.create_task(self.execute_command(entry))
        elif kind=='set_yaw':
            for c in self._select_players(data[0]):
                async with self.bridge.lock:await c.body.write_yaw(number(await self.resolve(data[1],c),-100,100))
        elif kind=='load_playstyle':await self.bridge.set_script_playstyle(str(data),self.ids)
        elif kind in {'log_single','log_multi'}:
            value=await self.resolve(data) if kind=='log_single' else [await self.resolve(data[1],c) for c in self._select_players(data[0])]
            match=re.fullmatch(r'__mythic_action_(\d+)',str(value).strip())
            if match:
                node=self.compiled['extensions'][int(match[1])]
                if node['op'] in {'settimer','endtimer'}:
                    if node['op']=='settimer':self._timers[node['name']]=time.monotonic()
                    elif node['name'] not in self._timers:raise ValueError('Timer nicht gestartet: '+node['name'])
                    else:await self.bridge.log(f"Timer {node['name']}: {time.monotonic()-self._timers.pop(node['name']):.2f}s")
                elif node['op'] in {'setyaw','set_yaw','nav','friendtp'}:
                    for c in self._select_players(node['selector']):
                        value=await self.resolve(node['value'],c)
                        if node['op'] in {'setyaw','set_yaw'}:
                            async with self.bridge.lock:await c.body.write_yaw(number(value,-100,100))
                        elif node['op']=='nav':await self.action('navmap_to',c,position=[value.x,value.y,value.z])
                        else:await self.friend(c,value,False,True)
                elif node['op']=='counter':
                    name=node['name']
                    if name not in self._constants:raise ValueError('Zähler zuerst mit con definieren: '+name)
                    self._constants[name]=0 if node['change'] is None else number(self._constants[name])+node['change']
                else:
                    target=self.ids if node['target']=='mass' else [self.ids[int(node['target'][1:])-1]]
                    async with self.bridge.lock:await self.bridge.protected_step(node['op'],{**node,'ids':target})
            else:await self.bridge.log('Bot: '+str(value))
        elif kind not in {'label','nop'}:raise ValueError('Anweisung nicht unterstützt: '+kind)
        frame.ip=next_ip;return True
    async def run(self):
        while True:
            if time.monotonic()-self.started>self.limit:raise ValueError('Bot-Zeitlimit erreicht.')
            self.steps+=1
            if self.steps%200==0:await asyncio.sleep(.01)
            else:await asyncio.sleep(0)
            if time.monotonic()-self.last_progress>.25:
                self.last_progress=time.monotonic();await self.bridge.send({'type':'progress','step':self.steps,'line':self.current_task.ip+1,'engine':'deimos'})
            if not await self.step():break
