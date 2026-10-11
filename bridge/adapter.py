"""WizWalker integration, pinned to Vindaloniak DE commit in requirements.txt."""
import asyncio
import math
import time
from settings import combat_rules
from protocol import key, number, text, xyz

class WizAdapter:
    def __init__(self):
        from wizwalker import ClientHandler, Keycode
        from wizwalker.utils import XYZ
        from wizwalker.combat import CombatHandler
        self.handler = ClientHandler()
        self.Keycode, self.XYZ, self.CombatHandler = Keycode, XYZ, CombatHandler
        self.hooked = set()
        self.errors = {}
        self.freecam = set()
        self.original_speeds = {}
        self.combat_rounds = {}
        self.automation_data = {}

    def clients(self):
        return {str(c.process_id): c for c in self.handler.clients if c.is_running()}

    def selected(self, ids, hooked=True):
        if not isinstance(ids, list) or not 1 <= len(ids) <= 16 or len(set(ids)) != len(ids):
            raise ValueError('1–16 unterschiedliche Clients auswählen.')
        clients = self.clients()
        result = []
        for pid in ids:
            if not isinstance(pid, str) or pid not in clients:
                raise ValueError('Client nicht mehr verfügbar. Neu suchen.')
            if hooked and pid not in self.hooked:
                raise ValueError('Client zuerst hooken.')
            result.append(clients[pid])
        return result

    async def scan(self):
        for client in self.handler.remove_dead_clients():
            self.hooked.discard(str(client.process_id))
            self.original_speeds.pop(str(client.process_id),None)
            self.freecam.discard(str(client.process_id))
            # ClientHandler otherwise retains dead window handles.
            if client.window_handle in self.handler._managed_handles:
                self.handler._managed_handles.remove(client.window_handle)
        self.handler.get_new_clients()
        return await self.snapshot()

    async def hook(self, ids):
        results = []
        for c in self.selected(ids, hooked=False):
            pid = str(c.process_id)
            if pid in self.hooked:
                continue
            try:
                await asyncio.wait_for(c.activate_hooks(wait_for_ready=True, timeout=12), 20)
                # Validate basic reads before advertising the client as ready.
                await asyncio.wait_for(c.body.position(), 3)
                await c.mouse_handler.activate_mouseless()
                self.hooked.add(pid)
                self.errors.pop(pid, None)
                results.append({'pid': pid, 'ok': True})
            except BaseException as exc:
                try:
                    await c.close()
                finally:
                    self.hooked.discard(pid)
                if isinstance(exc, asyncio.CancelledError):
                    raise
                self.errors[pid] = f'{type(exc).__name__}: {exc}'
                results.append({'pid': pid, 'ok': False, 'error': self.errors[pid]})
        return results

    async def unhook(self, ids):
        for c in self.selected(ids, hooked=False):
            await self.restore_speed(c)
            if str(c.process_id) in self.freecam:
                await c.camera_elastic()
                self.freecam.discard(str(c.process_id))
            await c.close()
            self.hooked.discard(str(c.process_id))
            self.errors.pop(str(c.process_id), None)
        return {'unhooked': ids}

    async def snapshot(self):
        rows = []
        for pid, c in self.clients().items():
            row = {'id': pid, 'pid': int(pid), 'title': c.title, 'hooked': pid in self.hooked,
                   'error': self.errors.get(pid), 'zone': None, 'position': None, 'health': None,
                   'mana': None, 'level': None, 'battle': None, 'foreground':bool(c.is_foreground)}
            if row['hooked']:
                try:
                    async with asyncio.timeout(4):
                        p = await c.body.position()
                        row.update(position=[p.x, p.y, p.z], zone=await c.zone_name(),
                            health=await c.stats.current_hitpoints(), mana=await c.stats.current_mana(),
                            level=await c.stats.reference_level(), battle=await c.in_battle())
                except Exception as exc:
                    row['error'] = f'{type(exc).__name__}: {exc}'
            rows.append(row)
        return rows

    def foreground_id(self):
        return next((pid for pid,c in self.clients().items() if c.is_foreground and pid in self.hooked),None)

    def hooked_ids(self):return [pid for pid in self.clients() if pid in self.hooked]

    def window_handles(self):return [c.window_handle for pid,c in self.clients().items() if pid in self.hooked]

    async def prepare_automation(self,mode,ids):
        if mode=='combat':
            for pid in ids:self.combat_rounds.pop(pid,None)
        for c in self.selected(ids):
            data={'last':0}
            if mode=='sigil':
                p=await c.body.position();data.update(zone=await c.zone_name(),position=[p.x,p.y,p.z],entered=False)
            self.automation_data[(mode,str(c.process_id))]=data

    async def window_path(self,c,path):
        current=c.root_window
        try:
            for name in path:current=await current.get_child_by_name(name)
            return current if await current.is_visible() else None
        except ValueError:return None

    async def dialogue_step(self,c,accept=False):
        if not await c.is_in_dialog():return False
        paths=[['WorldView','wndDialogMain','btnRight']] if accept else []
        paths += [['WorldView','wndDialogMain','advanceDialogButton']]
        for path in paths:
            window=await self.window_path(c,path)
            if window is not None and await window.is_visible():
                await c.mouse_handler.click_window(window);return True
        return False

    async def combat_step(self,c,config):
        pid=str(c.process_id)
        if not await c.in_battle():self.combat_rounds.pop(pid,None);return
        from wizwalker.memory.memory_objects.enums import DuelPhase
        if await c.duel.duel_phase()!=DuelPhase.planning:return
        marker=(await c.duel.duel_id_full(),await c.duel.round_num())
        if self.combat_rounds.get(pid)==marker:return
        handler=self.CombatHandler(c)
        for rule in combat_rules(config['combat_rules']):
            if rule['name']=='pass':
                self.combat_rounds[pid]=marker;await handler.pass_button();return
            cards=await handler.get_damaging_aoes() if rule['name']=='any<aoe>' else await handler.get_cards()
            for card in cards:
                if not await card.is_castable():continue
                if rule['name']!='any<aoe>' and rule['name'].casefold() not in {(await card.name()).casefold(),(await card.display_name()).casefold()}:continue
                target=None
                if rule['target']=='self':target=await handler.get_client_member()
                elif rule['target']=='enemy':
                    enemies=[m for m in await handler.get_all_monster_members() if not await m.is_dead()]
                    if not enemies:continue
                    target=enemies[0]
                # Claim before clicking: never choose a second card in this round.
                self.combat_rounds[pid]=marker;await card.cast(target);return
        if config['combat_pass']:
            self.combat_rounds[pid]=marker;await handler.pass_button()

    async def navmap_teleport(self,c,target=None,timeout=20):
        from navmap import navmap_tp
        if await c.in_battle() or await c.is_loading() or await c.is_in_dialog():return {'id':str(c.process_id),'skipped':'Client beschäftigt'}
        p=target or await c.quest_position.position();xyz([p.x,p.y,p.z])
        if [p.x,p.y,p.z]==[0,0,0]:raise ValueError('Kein aktives Quest-Ziel verfügbar.')
        async with asyncio.timeout(timeout):await navmap_tp(c,p)
        return {'id':str(c.process_id),'position':[p.x,p.y,p.z]}

    async def questing_step(self,c,config,movement,mode='questing'):
        pid=str(c.process_id);data=self.automation_data.setdefault((mode,pid),{'last':0})
        if await self.dialogue_step(c,config['quest_accept']):return
        now=time.monotonic()
        if now-data['last']<2:return
        data['last']=now
        if await c.is_in_npc_range():await c.send_key(self.Keycode.X,.1);return
        p=await c.quest_position.position();position=await c.body.position()
        if [p.x,p.y,p.z]==[0,0,0]:return
        if math.dist([p.x,p.y,p.z],[position.x,position.y,position.z])>config['quest_distance']:
            await self.navmap_teleport(c,p,movement['navmap_timeout'])
        elif config['quest_forward']:await c.send_key(self.Keycode.W,.1)

    async def automation_step(self,c,mode,config,movement):
        if mode=='combat':await self.combat_step(c,config);return
        if await c.in_battle() or await c.is_loading():return
        if mode=='dialogue':await self.dialogue_step(c,config['quest_accept']);return
        if mode=='questing':await self.questing_step(c,config,movement);return
        if mode=='sigil':
            data=self.automation_data[('sigil',str(c.process_id))];zone=await c.zone_name();now=time.monotonic()
            if zone!=data['zone']:
                data['entered']=True;await self.questing_step(c,config,movement,'sigil');return
            if data['entered'] and not config['sigil_rejoin']:return
            if now-data['last']<config['sigil_cooldown']:return
            data['last']=now
            await c.teleport(self.XYZ(*data['position']))
            if await c.is_in_npc_range():await c.send_key(self.Keycode.X,.1)
            await asyncio.sleep(.25)
            if config['sigil_confirm']:
                path=['MessageBoxModalWindow','messageBoxBG','messageBoxLayout','AdjustmentWindow','Layout','centerButton']
                window=await self.window_path(c,path) or await self.window_path(c,['WorldView']+path)
                if window is not None:await c.mouse_handler.click_window(window)

    async def restore_speed(self,c):
        pid=str(c.process_id)
        if pid in self.original_speeds:
            obj=c.client_object
            if obj is None: raise ValueError('Spielerobjekt nicht verfügbar.')
            await obj.write_speed_multiplier(self.original_speeds[pid])
            del self.original_speeds[pid]

    async def execute(self, op, args):
        clients = self.selected(args.get('ids'))
        result = []
        if op=='navmap_tp':
            source=self.selected([args['source']])[0] if args.get('source') else None
            target=await source.quest_position.position() if source else None
            source_zone=await source.zone_name() if source else None
            jobs=[]
            for c in clients:
                same_zone=source is not None and await c.zone_name()==source_zone
                policy=args.get('target','auto')
                if policy=='leader' and not same_zone:raise ValueError('Leader-Quest-Teleport benötigt dieselbe Zone.')
                jobs.append(self.navmap_teleport(c,target if same_zone and policy!='own' else None,args.get('timeout',20)))
            results=await asyncio.gather(*jobs,return_exceptions=True)
            failures=[str(r) for r in results if isinstance(r,BaseException)]
            if failures:raise ValueError('Navmap: '+ '; '.join(failures))
            return results
        for c in clients:
            if op=='automation_step':await self.automation_step(c,args['mode'],args['config'],args['movement'])
            elif op == 'quest_position'  or op == 'quest_tp':
                if await c.is_loading() or await c.in_battle(): raise ValueError('Quest-Teleport benötigt einen freien Client.')
                p=await c.quest_position.position()
                coords=xyz([p.x,p.y,p.z])
                if coords==[0,0,0]: raise ValueError('Kein aktives Quest-Ziel verfügbar.')
                if op=='quest_tp': await c.teleport(self.XYZ(*coords))
                result.append({'id':str(c.process_id),'position':coords,'zone':await c.zone_name()})
            elif op == 'nearest_entity':
                query=text(args.get('query')).casefold()
                origin=await c.body.position();nearest=None;distance=float('inf')
                for e in (await c.get_base_entity_list())[:1000]:
                    try:
                        template=await e.object_template();body=await e.actor_body()
                        if template is None or body is None:continue
                        name=await template.object_name();display=await e.display_name()
                        if query not in (name+' '+(display or '')).casefold():continue
                        p=await body.position();coords=xyz([p.x,p.y,p.z]);d=math.dist([origin.x,origin.y,origin.z],coords)
                        if d<distance:nearest=(name,coords);distance=d
                    except Exception:continue
                if nearest is None:raise ValueError('Keine passende Entity gefunden.')
                await c.teleport(self.XYZ(*nearest[1]))
                result.append({'id':str(c.process_id),'name':nearest[0],'distance':distance})
            elif op == 'speed':
                obj=c.client_object
                if obj is None:raise ValueError('Spielerobjekt nicht verfügbar.')
                value=number(args.get('percent'),0,300)
                if not value.is_integer():raise ValueError('Geschwindigkeit muss ganzzahlig sein.')
                value=int(value);pid=str(c.process_id)
                if pid not in self.original_speeds:self.original_speeds[pid]=await obj.speed_multiplier()
                await obj.write_speed_multiplier(value)
            elif op == 'restore_speed':await self.restore_speed(c)
            elif op == 'camera_tp':
                if not await c.game_client.is_freecam():raise ValueError('Zuerst Freecam aktivieren.')
                camera=await c.game_client.free_camera_controller()
                if camera is None:raise ValueError('Freecam nicht verfügbar.')
                p=await camera.position();await c.teleport(self.XYZ(*xyz([p.x,p.y,p.z])))
            elif op == 'rename':c.title=text(args.get('title'),80)
            elif op == 'stats':
                values={}
                for name in ['max_hitpoints','current_hitpoints','max_mana','current_mana','current_gold','reference_level','potion_charge','potion_max','dmg_bonus_percent','dmg_reduce_percent','critical_hit_rating_by_school','ap_bonus_percent']:
                    try:values[name]=await getattr(c.stats,name)()
                    except Exception as exc:values[name]={'error':str(exc)}
                result.append({'id':str(c.process_id),'title':c.title,'stats':values})
            elif op == 'dialogue_step':
                if await c.in_battle() or await c.is_loading():continue
                if await c.is_in_dialog():
                    windows=[w for w in await c.root_window.get_windows_with_name('advanceDialogButton') if await w.is_visible()]
                    if len(windows)==1:await c.mouse_handler.click_window(windows[0])
            elif op == 'key':
                await c.send_key(self.Keycode[key(args.get('key'))], number(args.get('seconds', .1), .01, 5))
            elif op == 'teleport':
                coords = xyz(args.get('xyz'))
                await c.teleport(self.XYZ(*coords))
            elif op == 'sync':
                source = self.selected([text(args.get('source'))])[0]
                if await source.zone_name() != await c.zone_name():
                    raise ValueError('Positions-Sync erfordert dieselbe Zone.')
                await c.teleport(await source.body.position())
            elif op == 'freecam':
                await c.camera_swap()
                pid = str(c.process_id)
                if await c.game_client.is_freecam():
                    self.freecam.add(pid)
                else:
                    self.freecam.discard(pid)
            elif op == 'entity_tp':
                entities = await c.get_base_entities_with_name(text(args.get('name')))
                if len(entities) != 1:
                    raise ValueError(f'{len(entities)} passende Entities: eindeutigen Namen wählen.')
                body = await entities[0].actor_body()
                if body is None:
                    raise ValueError('Entity hat keinen ActorBody.')
                await c.teleport(await body.position())
            elif op == 'entities':
                rows = []
                for e in (await c.get_base_entity_list())[:200]:
                    try:
                        template = await e.object_template()
                        if template is None:
                            continue
                        body = await e.actor_body()
                        p = await body.position() if body else None
                        rows.append({'name': await template.object_name(), 'display': await e.display_name(),
                                     'position': [p.x,p.y,p.z] if p else None})
                    except Exception:
                        continue
                result.append({'id': str(c.process_id), 'entities': rows})
            elif op == 'ui_tree':
                result.append({'id': str(c.process_id), 'tree': (await c.root_window.get_ui_tree_stringified())[:60000]})
            elif op == 'click_window':
                windows = await c.root_window.get_windows_with_name(text(args.get('name')))
                windows = [w for w in windows if await w.is_visible()]
                if len(windows) != 1:
                    raise ValueError('Fenster fehlt, ist unsichtbar oder nicht eindeutig.')
                await c.mouse_handler.click_window(windows[0])
            elif op in {'cards', 'cast', 'pass'}:
                handler = self.CombatHandler(c)
                if not await c.in_battle():
                    raise ValueError('Client ist nicht im Kampf.')
                if op == 'cards':
                    cards = await handler.get_cards()
                    result.append({'id': str(c.process_id), 'cards': [
                        {'name': await card.name(), 'display': await card.display_name(), 'castable': await card.is_castable()}
                        for card in cards]})
                else:
                    from wizwalker.memory.memory_objects.enums import DuelPhase
                    if await c.duel.duel_phase() != DuelPhase.planning:
                        raise ValueError('Auf die Planungsphase warten.')
                    if op == 'pass':
                        await handler.pass_button()
                    else:
                        card = await handler.get_card_named(text(args.get('name')))
                        if not await card.is_castable():
                            raise ValueError('Karte aktuell nicht spielbar.')
                        target_type = args.get('target', 'none')
                        if target_type == 'self':
                            target = await handler.get_client_member()
                        elif target_type == 'enemy':
                            enemies = [m for m in await handler.get_all_monster_members() if not await m.is_dead()]
                            if not enemies:
                                raise ValueError('Kein lebender Gegner.')
                            target = enemies[0]
                        elif target_type == 'none':
                            target = None
                        else:
                            raise ValueError('Ungültiges Kartenziel.')
                        await card.cast(target)
            else:
                raise ValueError('Unbekannter Befehl.')
        return result or {'ok': True, 'count': len(clients)}

    async def battle(self, ids):
        return any([await c.in_battle() for c in self.selected(ids)])

    async def close(self):
        errors = []
        for c in self.handler.clients:
            try:
                if c.is_running(): await self.restore_speed(c)
                if c.is_running() and str(c.process_id) in self.freecam:
                    await c.camera_elastic()
                    self.freecam.discard(str(c.process_id))
                await c.close()
                self.hooked.discard(str(c.process_id))
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError('Unhook fehlgeschlagen: ' + '; '.join(errors))

class DemoAdapter:
    """Portable integration-test adapter. Never imports or hooks WizWalker."""
    def __init__(self):
        self.rows = [{'id': str(9001+i), 'pid': 9001+i, 'title': f'Demo Wizard {i+1}', 'hooked': False,
                     'zone': 'WizardCity/Commons', 'position': [100+i*20, 200, 0],
                     'health': 8500, 'mana': 210, 'level': 170, 'battle': False, 'error': None} for i in range(2)]
        self.original_speeds={}
    def selected(self, ids, hooked=True):
        if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids):
            raise ValueError('Clients auswählen.')
        rows = [next((r for r in self.rows if r['id'] == i), None) for i in ids]
        if any(r is None for r in rows) or (hooked and any(not r['hooked'] for r in rows)):
            raise ValueError('Client fehlt oder ist nicht gehookt.')
        return rows
    def foreground_id(self):return next((r['id'] for r in self.rows if r['hooked'] and r.get('foreground')),None)
    def hooked_ids(self):return [r['id'] for r in self.rows if r['hooked']]
    def window_handles(self):return []
    async def prepare_automation(self,mode,ids):self.selected(ids)
    async def scan(self): return await self.snapshot()
    async def snapshot(self): return [dict(r) for r in self.rows]
    async def hook(self, ids):
        for r in self.selected(ids, False): r['hooked'] = True
        return [{'pid': i, 'ok': True} for i in ids]
    async def unhook(self, ids):
        for r in self.selected(ids, False): r['hooked'] = False
        return {'unhooked': ids}
    async def execute(self, op, args):
        rows = self.selected(args.get('ids'))
        if op=='automation_step':return {'ok':True,'demo':True}
        if op=='navmap_tp':
            for r in rows:r['position']=[500,800,0]
            return {'ok':True,'demo':True}
        if op in {'quest_position','quest_tp'}:
            if op=='quest_tp':
                for r in rows:r['position']=[500,800,0]
            return [{'id':r['id'],'position':[500,800,0],'zone':r['zone']} for r in rows]
        elif op=='stats':return [{'id':r['id'],'title':r['title'],'stats':{'current_hitpoints':8500,'max_hitpoints':9000,'current_mana':210,'current_gold':10000,'reference_level':170}} for r in rows]
        elif op=='rename':
            for r in rows:r['title']=text(args.get('title'),80)
        elif op=='speed':
            number(args.get('percent'),0,300)
            for r in rows:self.original_speeds.setdefault(r['id'],40)
        elif op=='restore_speed':
            for r in rows:self.original_speeds.pop(r['id'],None)
        elif op in {'camera_tp','dialogue_step'}:pass
        elif op=='nearest_entity':
            text(args.get('query'))
            for r in rows:r['position']=[150,200,0]
        elif op == 'teleport':
            for r in rows: r['position'] = xyz(args.get('xyz'))
        elif op == 'sync':
            source = self.selected([args.get('source')])[0]
            for r in rows: r['position'] = list(source['position'])
        elif op == 'key': key(args.get('key')); number(args.get('seconds', .1), .01, 5)
        elif op == 'entities': return [{'id': rows[0]['id'], 'entities': [{'name':'Demo_Chest_001','display':'Demo-Truhe','position':[150,200,0]}]}]
        elif op == 'ui_tree': return [{'id':rows[0]['id'], 'tree':'WorldView\n  NPCRangeWin\n  DemoWindow'}]
        elif op == 'cards': return [{'id':rows[0]['id'], 'cards':[{'name':'LifeBlade','display':'Lebensklinge','castable':True}]}]
        elif op not in {'entity_tp','click_window','cast','pass','freecam'}: raise ValueError('Unbekannter Befehl.')
        return {'ok':True, 'demo':True}
    async def battle(self, ids): return any(r['battle'] for r in self.selected(ids))
    async def close(self):
        self.original_speeds.clear()
        for r in self.rows: r['hooked'] = False
