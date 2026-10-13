"""Local TLS WebSocket bridge. Loopback only; exact Origin + pairing token."""
import argparse
import asyncio
import contextlib
import datetime
import ipaddress
import json
import os
from pathlib import Path
import secrets
import ssl
import sys
import time
from diagnostics import event, logger, hide_secret, start_logging, bundle
from aiohttp import web, WSMsgType
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from adapter import WizAdapter, DemoAdapter
from protocol import parse_script
from botlang import compile_bot, walk_nodes, interpret
from block_library import BlockLibrary
from expert import compile_expert, ExpertVM
from playstyle import parse_style
from settings import Settings, ACTIONS
from hotkeys import Hotkeys
from automation import Automations
from fishing import Fishing
from raids import Raids

from version import VERSION, RELEASE_TAG
SITE_ORIGIN = 'https://mythic-walker.lord-time.chatgpt.site'
ROOT = Path(__file__).resolve().parent

def uses_expert(args):
    mode=args.get('engine','auto')
    if mode not in {'auto','basic','deimos'}:raise ValueError('Ausführung: auto, basic oder deimos.')
    source=str(args.get('source',''))
    import re
    return mode=='deimos' or mode=='auto' and bool(re.search(r'(?m)^#{2,}\s*deimos_expertmode|^(?:con|setvar|addone|minusone|settimer|endtimer|loadplaystyle|togglecombat|except)\s',source))


def bridge_event_loop(platform=None):
    # Loopback HTTPS/WSS needs sockets, not Windows pipes/subprocess transports.
    # Avoid Proactor's failing socket.shutdown callback after peer resets.
    if (platform or sys.platform) == 'win32':
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()


def ensure_cert(directory):
    directory.mkdir(parents=True, exist_ok=True)
    cert_path, key_path = directory/'localhost.crt', directory/'localhost.key'
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Mythic Walker localhost')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(private.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-datetime.timedelta(minutes=5)).not_valid_after(now+datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),
            x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(private, hashes.SHA256()))
    key_path.write_bytes(private.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    with contextlib.suppress(OSError): os.chmod(key_path, 0o600)
    return cert_path, key_path


class Bridge:
    def __init__(self, adapter, token, origins, demo=False, settings_path=None, observer=None, widget=None):
        self.adapter, self.token, self.origins, self.demo = adapter, token, set(origins), demo
        hide_secret(token)
        self.last_diagnostic_state = None
        event('bridge.init', demo=demo, origins=sorted(self.origins), release=RELEASE_TAG)
        self.lock = asyncio.Lock()
        self.session_lock = asyncio.Lock()
        self.ws = None
        self.script_task = None
        self.shutting_down = False
        self.cleanup_error = None
        self.settings = Settings(settings_path)
        defaults=json.loads((ROOT/"web"/"default-library.json").read_text(encoding="utf-8"))
        self.block_library=BlockLibrary(defaults,Path(settings_path).with_name("user-blocks.json") if settings_path else None)
        self.widget = widget
        if widget:widget.configure(self.settings.data['widget'])
        self.hotkeys = Hotkeys()
        self.shortcut_context = {'ids':[], 'source':''}
        self.hotkey_busy = False
        self.hotkeys_paused = False
        self.session_generation = 0
        self.observer = observer or (lambda title,detail='': None)
        self.automations = Automations(self)
        self.fishing = Fishing(self)
        self.raids = Raids(self)

    async def set_script_playstyle(self,source,ids):
        rows=parse_style(source)
        if not hasattr(self.adapter,'playstyles'):raise ValueError('Playstyles benötigen eine Live-Bridge.')
        for index,pid in enumerate(ids,1):
            self.adapter.playstyles[pid]=[row for row in rows if row['client'] in {'mass','p'+str(index)}]
        await self.log('Playstyle für '+str(len(ids))+' Clients übernommen.')

    async def run_expert(self,compiled,ids):
        previous_styles=dict(getattr(self.adapter,'playstyles',{}))
        try:
            await ExpertVM(self,compiled,ids,self.settings.data['automation']['max_minutes']).run()
            await self.log('Deimos-Bot abgeschlossen.')
        except asyncio.CancelledError:await self.log('Deimos-Bot gestoppt.','warning')
        except Exception as exc:
            logger.exception('expert.failed');await self.log('Deimos-Bot: '+str(exc),'error')
        finally:
            await self.automations.stop('combat')
            if hasattr(self.adapter,'playstyles'):self.adapter.playstyles=previous_styles
            await self.send({'type':'script_done'})

    async def send(self, data):
        ws = self.ws
        if ws and not ws.closed:
            try:
                await ws.send_json(data)
            except ConnectionResetError:
                # The peer can disappear after the closed check. Cleanup is
                # owned by the websocket handler, including native hotkeys.
                pass

    async def log(self, message, level='info'):
        getattr(logger, 'warning' if level == 'warning' else 'error' if level == 'error' else 'info')('%s', message)
        if level=='error':self.observer('Aktion fehlgeschlagen',message)
        await self.send({'type':'log', 'level':level, 'message':message,
                         'time':datetime.datetime.now().isoformat(timespec='seconds')})

    async def state(self):
        clients=await self.adapter.snapshot()
        summary = [(c['id'],c['hooked'],c.get('error')) for c in clients]
        if summary != self.last_diagnostic_state:
            event('state.changed', clients=summary)
            self.last_diagnostic_state = summary
        running=bool(self.script_task and not self.script_task.done())
        modes=self.automations.state()
        dialogue=modes['dialogue']
        await self.send({'type':'state','demo':self.demo,'version':VERSION,'clients':clients,'running':running,'dialogue':dialogue,'automations':modes,'fishing':dict(self.fishing.data),'raid':dict(self.raids.data)})
        self.observer('Dashboard verbunden',f"{len(clients)} Clients · {sum(c['hooked'] for c in clients)} Hooks · {'Skript läuft' if running else 'Dialog-Automatik' if dialogue else 'Bereit'}")

    @property
    def dialogue_task(self):return self.automations.tasks.get('dialogue')

    async def stop_dialogue(self):await self.automations.stop('dialogue')

    async def stop(self):
        await self.raids.stop()
        await self.fishing.stop()
        task = self.script_task
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError): await task
        self.script_task = None

    async def protected_step(self, op, args):
        # A stop must not interrupt WizWalker's key-up or a memory patch midway.
        async def operation():
            try:
                async with asyncio.timeout(25):
                    return await self.adapter.execute(op, args)
            except TimeoutError:
                await self.adapter.close()
                raise
        task = asyncio.create_task(operation())
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            except Exception as exc:
                await self.log(f'Letzten Schritt aufräumen: {exc}', 'error')
            raise

    async def run_script(self, steps, ids):
        try:
            start = asyncio.get_running_loop().time()
            program=steps if isinstance(steps,dict) else {'body':steps,'blocks':{},'instructions':len(steps)}
            async with self.lock: initial_zones=await self.adapter.zones(ids)
            zone_baseline=dict(zip(ids,initial_zones))
            async def progress(step,index):
                if asyncio.get_running_loop().time() - start > 900:
                    raise ValueError('Skript-Limit von 15 Minuten erreicht.')
                await self.send({'type':'progress','step':index,'total':program['instructions'],'line':step['line']})
            def targets(selector):
                target=ids if selector in {'mass','any'} else ids[int(selector[1:])-1:int(selector[1:])]
                if not target:raise ValueError('Client '+selector+' ist nicht ausgewählt.')
                return target
            async def check(condition):
                target=targets(condition['target'])
                async with self.lock:
                    value=await asyncio.wait_for(self.adapter.bot_condition(condition['test'],target),5)
                return not value if condition['not'] else value
            async def execute(step):
                if step['op']=='sleep':
                    await asyncio.sleep(step['seconds']);return
                target=targets(step['target'])
                if step['op']=='wait_zone':
                    baseline=[zone_baseline[pid] for pid in target]
                    async with asyncio.timeout(step['timeout']):
                        while True:
                            async with self.lock:
                                current=await asyncio.wait_for(self.adapter.zones(target),5)
                                loaded=await asyncio.wait_for(self.adapter.wait_condition('wait_loading',target),5)
                            if loaded and all(current[i]!=baseline[i] for i in range(len(target))):
                                zone_baseline.update(zip(target,current));break
                            await asyncio.sleep(.25)
                elif step['op'] in {'wait_loading','wait_window'}:
                    async with asyncio.timeout(step['timeout']):
                        while True:
                            async with self.lock:
                                ready=await asyncio.wait_for(self.adapter.wait_condition(step['op'],target,step.get('name')),5)
                            if ready:break
                            await asyncio.sleep(.25)
                elif step['op']=='wait_combat':
                    async with asyncio.timeout(300):
                        while True:
                            async with self.lock:battle=await self.adapter.battle(target)
                            if not battle:break
                            await asyncio.sleep(.5)
                else:
                    async with self.lock:
                        await self.protected_step(step['op'], {**step, 'ids':target, **({'target':step['card_target']} if step['op']=='cast' else {'target':'own'} if step['op']=='navmap_tp' else {})})
            await interpret(program,execute,check,progress)
            await self.log('Skript abgeschlossen.')
        except asyncio.CancelledError:
            await self.log('Skript gestoppt.', 'warning')
            raise
        except Exception as exc:
            await self.log(f'Skript abgebrochen: {type(exc).__name__}: {exc}', 'error')
        finally:
            await self.automations.stop('combat')
            await self.send({'type':'script_done'})

    async def configure_hotkeys(self):
        loop = asyncio.get_running_loop()
        generation = self.session_generation
        def callback(action):
            loop.call_soon_threadsafe(lambda: asyncio.create_task(self.shortcut(action, generation)))
        def status_changed(status):
            async def notify():
                if generation==self.session_generation:await self.send({'type':'hotkeys',**status})
            loop.call_soon_threadsafe(lambda: asyncio.create_task(notify()))
        if self.ws is not None and not self.ws.closed and self.settings.data['global_hotkeys'] and not self.hotkeys_paused:
            status = await asyncio.to_thread(self.hotkeys.start, self.settings.data['bindings'], callback, self.adapter.window_handles(), status_changed)
        else:
            await asyncio.to_thread(self.hotkeys.stop)
            status = self.hotkeys.status
        await self.send({'type':'hotkeys', **status})
        return status

    async def shortcut(self, action, generation):
        if generation != self.session_generation or self.ws is None or self.ws.closed or self.shutting_down or self.hotkeys_paused or not self.settings.data['global_hotkeys']:
            return
        if action not in ACTIONS or (self.hotkey_busy and action != 'stop'): return
        if action != 'stop': self.hotkey_busy = True
        try:
            selected = list(self.shortcut_context['ids'])
            op, args = action, {'ids':selected}
            if action in {'sync','freecam','camera_tp','quest_tp','quest_all','speed_toggle','interact','combat_toggle','dialogue_toggle','questing_toggle','sigil_toggle'}:
                op,args='movement',{'action':action}
            elif action == 'run_script': args['source'] = self.shortcut_context['source']
            elif action == 'forward':
                op='key';args.update(key='W',seconds=self.settings.data['key_seconds'])
            result = await self.dispatch(op,args)
            if action=='hook' and isinstance(result,list) and any(not r.get('ok') for r in result):
                raise ValueError('Mindestens ein Hook fehlgeschlagen; Client-Status prüfen.')
            await self.log('Shortcut: '+action)
            async with self.lock: await self.state()
        except Exception as exc:
            await self.log('Shortcut: '+str(exc),'error')
        finally:
            if action != 'stop': self.hotkey_busy = False

    async def movement(self,action,args):
        config=self.settings.data['movement'];selected=args.get('ids',self.shortcut_context['ids'])
        all_ids=self.adapter.hooked_ids()
        scope=all_ids if config['scope']=='all' else selected
        self.adapter.selected(scope)
        source=self.adapter.foreground_id() or args.get('source') or self.shortcut_context.get('leader') or (next((pid for pid in selected if pid in all_ids),scope[0]))
        self.adapter.selected([source])
        if action in {'combat_toggle','dialogue_toggle','questing_toggle','sigil_toggle'}:
            return await self.automations.toggle(action.split('_')[0],scope)
        if action=='interact':return await self.dispatch('key',{'ids':scope,'key':'X','seconds':self.settings.data['key_seconds']})
        if action=='sync':
            targets=[pid for pid in scope if pid!=source]
            if not targets:raise ValueError('Positions-Sync benötigt mindestens zwei gehookte Clients.')
            return await self.dispatch('sync',{'ids':targets,'source':source})
        if action in {'quest_tp','quest_all'}:
            return await self.dispatch('navmap_tp',{'ids':[source] if action=='quest_tp' else scope,'source':source,'target':'own' if action=='quest_tp' else config['navmap_target'],'timeout':config['navmap_timeout']})
        if action=='speed_toggle':
            on=bool(getattr(self.adapter,'original_speeds',{}))
            return await self.dispatch('restore_speed' if on else 'speed',{'ids':scope,'percent':config['speed_percent']})
        if action in {'freecam','camera_tp'}:return await self.dispatch(action,{'ids':selected if config['freecam_scope']=='selected' else [source]})
        raise ValueError('Unbekannte Movement-Aktion.')

    async def dispatch(self, op, args):
        if op == 'get_diagnostics': return bundle()
        if op == 'script_capabilities':
            from expert import SUPPORTED_COMMANDS, UNSUPPORTED
            return {'engine':'deimos','release':RELEASE_TAG,'commands':sorted(SUPPORTED_COMMANDS),'unsupported':UNSUPPORTED}
        if op == 'validate_playstyle':return {'rules':len(parse_style(args.get('source')))}
        if op == 'validate_block_library':
            self.block_library.validate(args.get('blocks'))
            return {'valid':True}
        if op == 'set_playstyle':
            self.adapter.selected(args.get('ids'))
            await self.set_script_playstyle(args.get('source'),args['ids'])
            return {'loaded':True}
        if self.cleanup_error:
            raise ValueError('Bridge nach Unhook-Fehler neu starten: ' + self.cleanup_error)
        if op=='raid_stop':return await self.raids.stop()
        if self.raids.running and op not in {'stop','unhook','scan','snapshot','get_settings','pause_hotkeys','shortcut_context','widget'}:
            raise ValueError('Raid-Aktion zuerst stoppen.')
        if op=='raid_start':return await self.raids.start(args.get('ids'),args.get('raid'),args.get('action'),args.get('target'))
        if op=='fishing_start':return await self.fishing.start(args.get('ids'),args.get('settings',{}))
        if op=='fishing_stop':return await self.fishing.stop(timeout=10)
        if self.fishing.running and op not in {'stop','unhook','scan','snapshot','get_settings','pause_hotkeys','shortcut_context','widget'}:
            raise ValueError('Fisch-Bot zuerst stoppen.')
        if op=='movement':return await self.movement(args.get('action'),args)
        if op=='automation':return await self.automations.toggle(args.get('mode'),args.get('ids'),args.get('enabled'))
        if op == 'widget':
            if not self.widget:raise ValueError('Widget-Steuerung benötigt die Windows-EXE.')
            action=args.get('action')
            if action not in {'show','hide','toggle'}:raise ValueError('Ungültige Widget-Aktion.')
            self.widget.visibility(action)
            return {'queued':True}
        if op == 'get_settings':
            return {'settings':self.settings.data, 'hotkeys':self.hotkeys.status}
        if op == 'set_settings':
            self.settings.save(args.get('settings'))
            if self.widget:self.widget.configure(self.settings.data['widget'])
            return {'settings':self.settings.data, 'hotkeys':await self.configure_hotkeys()}
        if op == 'pause_hotkeys':
            if type(args.get('paused')) is not bool: raise ValueError('paused muss boolesch sein.')
            self.hotkeys_paused = args['paused']
            return await self.configure_hotkeys()
        if op == 'shortcut_context':
            ids, source = args.get('ids'), args.get('source')
            if not isinstance(ids,list) or len(ids)>16 or any(not isinstance(i,str) or len(i)>80 for i in ids) or len(set(ids))!=len(ids):
                raise ValueError('Ungültige Shortcut-Auswahl.')
            if not isinstance(source,str) or len(source)>65536: raise ValueError('Shortcut-Skript zu lang (max. 64 KB).')
            leader=args.get('leader')
            if leader is not None and (not isinstance(leader,str) or len(leader)>80):raise ValueError('Ungültiger Leader.')
            self.shortcut_context = {'ids':list(ids), 'source':source,'leader':leader}
            return {'updated':True}
        if op == 'stop':
            await self.automations.stop()
            await self.stop()
            return {'stopped':True}
        if op == 'dialogue':
            return await self.automations.toggle('dialogue',args.get('ids'),args.get('enabled'))
        if op == 'get_block_library':return {'blocks':self.block_library.custom}
        if op == 'set_block_library':return {'blocks':self.block_library.update(args.get('blocks'))}
        if op == 'validate_script':
            if uses_expert(args):
                result=compile_expert(args.get('source'),self.block_library.merged())
                return {'steps':result['instructions'],'engine':'deimos','commands':result['commands']}
            steps=compile_bot(args.get('source'),self.block_library.merged())
            return {'steps':steps['instructions'], 'parsed':steps}

        if op == 'run_script':
            if self.script_task and not self.script_task.done():
                raise ValueError('Es läuft bereits ein Skript.')
            if uses_expert(args):
                if self.demo:raise ValueError('Deimos-Expertmode benötigt die Live-Bridge; Demo nur für den Basis-Runner.')
                compiled=compile_expert(args.get('source'),self.block_library.merged())
                ids=args.get('ids');self.adapter.selected(ids)
                auto_combat=args.get('auto_combat',False)
                if type(auto_combat) is not bool:raise ValueError('Auto-Combat muss boolesch sein.')
                vm=ExpertVM(self,compiled,ids,self.settings.data['automation']['max_minutes'])
                # Validate explicit selectors before the first game action.
                def selectors(value):
                    from deimoslang.types import PlayerSelector, Expression, Command
                    if isinstance(value,PlayerSelector):vm._select_players(value)
                    elif isinstance(value,(list,tuple)):
                        for item in value:selectors(item)
                    elif isinstance(value,dict):
                        for item in value.values():selectors(item)
                    elif isinstance(value,(Expression,Command)):
                        for item in vars(value).values():selectors(item)
                for instruction in compiled['program']:selectors(instruction.data)
                for node in compiled['extensions'].values():selectors(node)
                await self.automations.stop()
                if auto_combat:await self.automations.toggle('combat',ids,True)
                self.script_task=asyncio.create_task(self.run_expert(compiled,list(ids)))
                return {'started':True,'steps':compiled['instructions'],'engine':'deimos'}
            steps = compile_bot(args.get('source'),self.block_library.merged())
            ids = args.get('ids')
            self.adapter.selected(ids)
            for step in walk_nodes(steps):
                if step.get('target','mass') != 'mass' and int(step['target'][1:]) > len(ids):
                    raise ValueError(f"Zeile {step['line']}: Ziel fehlt in der Auswahl.")
            auto_combat=args.get('auto_combat',False)
            if type(auto_combat) is not bool:raise ValueError('Auto-Combat muss boolesch sein.')
            if auto_combat:
                if any(step['op'] in {'cast','pass'} for step in walk_nodes(steps)):raise ValueError('Automatischer und manueller Kampf dürfen im Bot nicht gleichzeitig aktiv sein.')
            await self.automations.stop()
            if auto_combat:await self.automations.toggle('combat',ids,True)
            self.script_task = asyncio.create_task(self.run_script(steps, list(ids)))
            return {'started':True, 'steps':steps['instructions']}
        if self.script_task and not self.script_task.done() and op not in {'snapshot','entities','ui_tree','cards','stats','quest_position'}:
            raise ValueError('Skript zuerst stoppen.')
        if op=='unhook':
            await self.raids.stop()
            await self.fishing.stop()
            await self.automations.stop()
        async with self.lock:
            async with asyncio.timeout(45):
                if op == 'scan': return await self.adapter.scan()
                if op == 'hook': return await self.adapter.hook(args.get('ids'))
                if op == 'unhook':
                    return await self.adapter.unhook(args.get('ids'))
                if op == 'snapshot': return await self.adapter.snapshot()
                if op in {'key','teleport','sync','freecam','entity_tp','entities','ui_tree','click_window','cards','cast','pass','quest_position','quest_tp','nearest_entity','speed','restore_speed','camera_tp','rename','stats','navmap_tp'}:
                    return await self.adapter.execute(op,args)
                raise ValueError('Nicht unterstützte Operation.')

    async def poll(self):
        while True:
            await asyncio.sleep(self.settings.data['poll_seconds'])
            try:
                async with self.lock: await self.state()
            except Exception as exc:
                await self.log(f'Status: {exc}', 'error')

    async def websocket(self, request):
        event('ws.handshake', origin=request.headers.get('Origin'), peer=request.remote,
              active=self.session_lock.locked(), shutting_down=self.shutting_down)
        if request.headers.get('Origin') not in self.origins:
            event('ws.rejected', reason='origin')
            raise web.HTTPForbidden(text='Origin nicht erlaubt.')
        if self.session_lock.locked() or self.shutting_down:
            event('ws.rejected', reason='another_session_or_shutdown')
            raise web.HTTPConflict(text='Bridge ist bereits verbunden oder wird beendet.')
        # Claim the session before awaiting the handshake, including teardown.
        async with self.session_lock:
            ws = web.WebSocketResponse(max_msg_size=1048576, heartbeat=20)
            await ws.prepare(request)
            poll = None
            try:
                msg = await ws.receive(timeout=8)
                event('ws.auth.received', frame_type=str(msg.type))
                payload = json.loads(msg.data) if msg.type == WSMsgType.TEXT else {}
                if payload.get('type') != 'auth' or not isinstance(payload.get('token'),str) or not secrets.compare_digest(payload['token'], self.token):
                    event('ws.auth.rejected', reason='invalid_token')
                    await ws.close(code=1008, message=b'Pairing token invalid')
                    return ws
                self.ws = ws
                event('ws.auth.accepted')
                self.observer('Dashboard gekoppelt','Automatische Verbindung hergestellt.')
                self.session_generation += 1
                self.hotkeys_paused = False
                print('Dashboard gekoppelt (' + ('DEMO' if self.demo else 'LIVE') + ').', flush=True)
                await self.send({'type':'ready','capabilities':['raid'],'version':VERSION,'release':RELEASE_TAG,'demo':self.demo,'backend':'demo' if self.demo else 'Vindaloniak DE','commit':'13223e0911578e586975ace496d9f586ac4538da'})
                await self.configure_hotkeys()
                async with self.lock:
                    try:
                        await self.adapter.scan()
                    except Exception as exc:
                        await self.log(f'Client-Suche: {type(exc).__name__}: {exc}', 'error')
                    await self.state()
                await self.log('Bridge verbunden. ' + ('DEMO – keine Spielverbindung.' if self.demo else 'Wizard101 öffnen und Clients suchen.'))
                poll = asyncio.create_task(self.poll())
                async for msg in ws:
                    if msg.type != WSMsgType.TEXT: continue
                    data = {}
                    started = time.monotonic()
                    try:
                        data = json.loads(msg.data)
                        if not isinstance(data,dict) or not isinstance(data.get('id'),str) or len(data['id']) > 80:
                            raise ValueError('Ungültige Anfrage.')
                        args = data.get('args',{})
                        if not isinstance(args,dict): raise ValueError('Argumente müssen ein Objekt sein.')
                        event('command.begin', id=data['id'], op=data.get('op'))
                        result = await self.dispatch(data.get('op'),args)
                        event('command.complete', id=data['id'], op=data.get('op'), elapsed_ms=round((time.monotonic()-started)*1000))
                        if data.get('op') == 'scan':
                            await self.log(f'Client-Suche: {len(result)} Spielclients gefunden.' + (' Wizard101 bis zur Charakterauswahl öffnen und erneut suchen.' if not result else ''))
                            for error in getattr(self.adapter,'scan_errors',[]):
                                await self.log(error, 'error')
                        if data.get('op') in {'hook','unhook','scan'}:await self.configure_hotkeys()
                        await self.send({'type':'result','id':data['id'],'ok':True,'data':result})
                        if data.get('op') not in {'get_settings','set_settings','pause_hotkeys','shortcut_context','get_diagnostics','validate_script','validate_playstyle','script_capabilities','validate_block_library'}:
                            async with self.lock: await self.state()
                    except Exception as exc:
                        logger.exception('command.failed op=%s', data.get('op') if isinstance(data,dict) else 'invalid')
                        await self.send({'type':'result','id':data.get('id') if isinstance(data,dict) else None,'ok':False,'error':f'{type(exc).__name__}: {exc}'})
                        await self.log(str(exc), 'error')
            except (TimeoutError, json.JSONDecodeError):
                logger.exception('ws.auth.handshake_failed')
                await ws.close(code=1008,message=b'Invalid auth handshake')
            except Exception:
                logger.exception('ws.session.failed')
                raise
            finally:
                event('ws.cleanup.begin', close_code=ws.close_code, exception=str(ws.exception()) if ws.exception() else None)
                if poll:
                    poll.cancel()
                    with contextlib.suppress(asyncio.CancelledError): await poll
                if self.ws is ws:
                    self.session_generation += 1
                    await asyncio.to_thread(self.hotkeys.stop)
                    self.shortcut_context = {'ids':[], 'source':''}
                    await self.automations.stop()
                    try:await self.stop()
                    except Exception as exc:self.cleanup_error=str(exc)
                    async with self.lock:
                        try: await self.adapter.close()
                        except Exception as exc:
                            self.cleanup_error = str(exc)
                            print('UNHOOK FEHLER: ',exc, flush=True)
                    self.ws = None
                    self.observer('Unhook-Fehler' if self.cleanup_error else 'Dashboard getrennt',self.cleanup_error or 'Hooks entfernt · Dashboard öffnen zum erneuten Koppeln.')
                    print('Dashboard getrennt; Skript- und Hook-Aufraeumen abgeschlossen.' if not self.cleanup_error else 'Dashboard getrennt; Unhook-Fehler im Protokoll beachten.', flush=True)
                event('ws.cleanup.complete', error=self.cleanup_error)
            return ws

    async def shutdown(self, app):
        self.shutting_down = True
        self.session_generation += 1
        await asyncio.to_thread(self.hotkeys.stop)
        await self.automations.stop()
        try:await self.stop()
        except Exception as exc:self.cleanup_error=str(exc)
        if self.ws: await self.ws.close(code=1001,message=b'Bridge shutdown')
        async with self.lock: await self.adapter.close()


def create_app(bridge, web_dir):
    @web.middleware
    async def trace_http(request, handler):
        try:
            response = await handler(request)
            event('http', method=request.method, path=request.path, status=response.status)
            return response
        except web.HTTPException as exc:
            event('http', method=request.method, path=request.path, status=exc.status)
            raise
        except Exception:
            logger.exception('http.failed path=%s', request.path)
            raise
    app = web.Application(client_max_size=65536, middlewares=[trace_http])
    app.router.add_get('/ws',bridge.websocket)
    async def index(request):
        return web.FileResponse(web_dir/'index.html')
    async def health(request):
        headers = {'Cache-Control':'no-store'}
        if request.headers.get('Origin') in bridge.origins:
            headers['Access-Control-Allow-Origin'] = request.headers['Origin']
            headers['Vary'] = 'Origin'
        return web.json_response({'service':'mythic-walker','version':VERSION,'release':RELEASE_TAG,'demo':bridge.demo,'connected':bool(bridge.ws is not None and not bridge.ws.closed)}, headers=headers)
    app.router.add_get('/health',health)
    app.router.add_get('/',index)
    # Serve only the explicit frontend assets, never bridge source/certificates.
    for filename in ['app.js','accounts.js','raids.js','raid-catalog.js','fishing.js','script-functions.js','script-studio.js','handoff.js','diagnostics.js','settings.js','tools.js','style.css','sources.json','botlang.js','bot-catalog.js','default-library.js','default-library.json','upstream-bots.json','BOTS_LICENSE.txt']:
        async def asset(request, filename=filename): return web.FileResponse(web_dir/filename)
        app.router.add_get('/'+filename,asset)
    # Only public, packaged icon assets; never expose other bridge directories.
    if (web_dir/'assets').is_dir():
        app.router.add_static('/assets/',web_dir/'assets',show_index=False,follow_symlinks=False)
    app.on_shutdown.append(bridge.shutdown)
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo',action='store_true',help='Test backend without Wizard101')
    parser.add_argument('--generate-cert',action='store_true')
    parser.add_argument('--origin',default=SITE_ORIGIN)
    args = parser.parse_args()
    log_path = start_logging(ROOT/'logs')
    print('Diagnose-Log:',log_path,flush=True)
    cert_dir = (Path(sys.executable).parent if getattr(sys,'frozen',False) else ROOT)/'certs'
    cert,key = ensure_cert(cert_dir)
    if args.generate_cert:
        print('Zertifikat erzeugt:',cert)
        return
    if not args.demo and sys.platform != 'win32':
        parser.error('Live-Bridge benötigt Windows. --demo ist plattformunabhängig.')
    if not args.origin.startswith('https://') or args.origin.endswith('/'):
        parser.error('--origin muss eine HTTPS-Origin ohne abschließenden Slash sein.')
    token = secrets.token_urlsafe(24)
    bridge = Bridge(DemoAdapter() if args.demo else WizAdapter(),token,
                    [args.origin,'https://localhost:18761','https://127.0.0.1:18761'],args.demo,
                    settings_path=(Path(sys.executable).parent if getattr(sys,'frozen',False) else ROOT)/'user-settings.json')
    web_dir = Path(getattr(sys,'_MEIPASS',ROOT))/'web'
    if not web_dir.exists(): web_dir = ROOT.parent/'dist'
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(cert,key)
    print('\nMYTHIC WALKER BRIDGE '+VERSION,flush=True)
    print('Modus: '+('DEMO' if args.demo else 'LIVE · Wizard101 DE'),flush=True)
    print('Pairing-Code: '+token,flush=True)
    print('Web-Dashboard: '+args.origin,flush=True)
    print('Lokale Alternative: https://localhost:18761',flush=True)
    print('Nur Loopback. Beenden mit Strg+C.\n',flush=True)
    loop = bridge_event_loop()
    print('Netzwerk-Loop: ' + type(loop).__name__, flush=True)
    web.run_app(create_app(bridge,web_dir),host='127.0.0.1',port=18761,
                ssl_context=tls,access_log=None,loop=loop)

if __name__ == '__main__': main()
