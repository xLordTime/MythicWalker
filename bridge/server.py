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
from aiohttp import web, WSMsgType
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from adapter import WizAdapter, DemoAdapter
from protocol import parse_script
from settings import Settings, ACTIONS
from hotkeys import Hotkeys
from automation import Automations

from version import VERSION
SITE_ORIGIN = 'https://mythic-walker.lord-time.chatgpt.site'
ROOT = Path(__file__).resolve().parent


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
    def __init__(self, adapter, token, origins, demo=False, settings_path=None, observer=None):
        self.adapter, self.token, self.origins, self.demo = adapter, token, set(origins), demo
        self.lock = asyncio.Lock()
        self.session_lock = asyncio.Lock()
        self.ws = None
        self.script_task = None
        self.shutting_down = False
        self.cleanup_error = None
        self.settings = Settings(settings_path)
        self.hotkeys = Hotkeys()
        self.shortcut_context = {'ids':[], 'source':''}
        self.hotkey_busy = False
        self.hotkeys_paused = False
        self.session_generation = 0
        self.observer = observer or (lambda title,detail='': None)
        self.automations = Automations(self)

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
        if level=='error':self.observer('Aktion fehlgeschlagen',message)
        await self.send({'type':'log', 'level':level, 'message':message,
                         'time':datetime.datetime.now().isoformat(timespec='seconds')})

    async def state(self):
        clients=await self.adapter.snapshot()
        running=bool(self.script_task and not self.script_task.done())
        modes=self.automations.state()
        dialogue=modes['dialogue']
        await self.send({'type':'state','demo':self.demo,'version':VERSION,'clients':clients,'running':running,'dialogue':dialogue,'automations':modes})
        self.observer('Dashboard verbunden',f"{len(clients)} Clients · {sum(c['hooked'] for c in clients)} Hooks · {'Skript läuft' if running else 'Dialog-Automatik' if dialogue else 'Bereit'}")

    @property
    def dialogue_task(self):return self.automations.tasks.get('dialogue')

    async def stop_dialogue(self):await self.automations.stop('dialogue')

    async def stop(self):
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
            for index, step in enumerate(steps):
                if asyncio.get_running_loop().time() - start > 900:
                    raise ValueError('Skript-Limit von 15 Minuten erreicht.')
                await self.send({'type':'progress','step':index+1,'total':len(steps),'line':step['line']})
                if step['op'] == 'sleep':
                    await asyncio.sleep(step['seconds'])
                    continue
                target = ids if step['target'] == 'mass' else ids[int(step['target'][1:])-1:int(step['target'][1:])]
                if not target:
                    raise ValueError(f"Zeile {step['line']}: Client {step['target']} ist nicht ausgewählt.")
                if step['op'] == 'wait_combat':
                    # completion waits for currently active fights; it does not enter a fight.
                    async with asyncio.timeout(300):
                        while True:
                            async with self.lock: battle = await self.adapter.battle(target)
                            if not battle: break
                            await asyncio.sleep(.5)
                else:
                    async with self.lock:
                        await self.protected_step(step['op'], {**step, 'ids':target})
            await self.log('Skript abgeschlossen.')
        except asyncio.CancelledError:
            await self.log('Skript gestoppt.', 'warning')
            raise
        except Exception as exc:
            await self.log(f'Skript abgebrochen: {type(exc).__name__}: {exc}', 'error')
        finally:
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
        if self.cleanup_error:
            raise ValueError('Bridge nach Unhook-Fehler neu starten: ' + self.cleanup_error)
        if op=='movement':return await self.movement(args.get('action'),args)
        if op=='automation':return await self.automations.toggle(args.get('mode'),args.get('ids'),args.get('enabled'))
        if op == 'get_settings':
            return {'settings':self.settings.data, 'hotkeys':self.hotkeys.status}
        if op == 'set_settings':
            self.settings.save(args.get('settings'))
            return {'settings':self.settings.data, 'hotkeys':await self.configure_hotkeys()}
        if op == 'pause_hotkeys':
            if type(args.get('paused')) is not bool: raise ValueError('paused muss boolesch sein.')
            self.hotkeys_paused = args['paused']
            return await self.configure_hotkeys()
        if op == 'shortcut_context':
            ids, source = args.get('ids'), args.get('source')
            if not isinstance(ids,list) or len(ids)>16 or any(not isinstance(i,str) or len(i)>80 for i in ids) or len(set(ids))!=len(ids):
                raise ValueError('Ungültige Shortcut-Auswahl.')
            if not isinstance(source,str) or len(source)>16000: raise ValueError('Shortcut-Skript zu lang.')
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
        if op == 'validate_script':
            steps = parse_script(args.get('source'))
            return {'steps':len(steps), 'parsed':steps}
        if op == 'run_script':
            await self.automations.stop()
            if self.script_task and not self.script_task.done():
                raise ValueError('Es läuft bereits ein Skript.')
            steps = parse_script(args.get('source'))
            ids = args.get('ids')
            self.adapter.selected(ids)
            for step in steps:
                if step.get('target','mass') != 'mass' and int(step['target'][1:]) > len(ids):
                    raise ValueError(f"Zeile {step['line']}: Ziel fehlt in der Auswahl.")
            self.script_task = asyncio.create_task(self.run_script(steps, list(ids)))
            return {'started':True, 'steps':len(steps)}
        if self.script_task and not self.script_task.done() and op not in {'snapshot','entities','ui_tree','cards','stats','quest_position'}:
            raise ValueError('Skript zuerst stoppen.')
        if op=='unhook':await self.automations.stop()
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
        if request.headers.get('Origin') not in self.origins:
            raise web.HTTPForbidden(text='Origin nicht erlaubt.')
        if self.session_lock.locked() or self.shutting_down:
            raise web.HTTPConflict(text='Bridge ist bereits verbunden oder wird beendet.')
        # Claim the session before awaiting the handshake, including teardown.
        async with self.session_lock:
            ws = web.WebSocketResponse(max_msg_size=65536, heartbeat=20)
            await ws.prepare(request)
            poll = None
            try:
                msg = await ws.receive(timeout=8)
                payload = json.loads(msg.data) if msg.type == WSMsgType.TEXT else {}
                if payload.get('type') != 'auth' or not isinstance(payload.get('token'),str) or not secrets.compare_digest(payload['token'], self.token):
                    await ws.close(code=1008, message=b'Pairing token invalid')
                    return ws
                self.ws = ws
                self.observer('Dashboard gekoppelt','Automatische Verbindung hergestellt.')
                self.session_generation += 1
                self.hotkeys_paused = False
                print('Dashboard gekoppelt (' + ('DEMO' if self.demo else 'LIVE') + ').', flush=True)
                await self.send({'type':'ready','version':VERSION,'demo':self.demo,'backend':'demo' if self.demo else 'Vindaloniak DE','commit':'13223e0911578e586975ace496d9f586ac4538da'})
                await self.configure_hotkeys()
                async with self.lock:
                    await self.adapter.scan()
                    await self.state()
                await self.log('Bridge verbunden. ' + ('DEMO – keine Spielverbindung.' if self.demo else 'Wizard101 öffnen und Clients suchen.'))
                poll = asyncio.create_task(self.poll())
                async for msg in ws:
                    if msg.type != WSMsgType.TEXT: continue
                    data = {}
                    try:
                        data = json.loads(msg.data)
                        if not isinstance(data,dict) or not isinstance(data.get('id'),str) or len(data['id']) > 80:
                            raise ValueError('Ungültige Anfrage.')
                        args = data.get('args',{})
                        if not isinstance(args,dict): raise ValueError('Argumente müssen ein Objekt sein.')
                        result = await self.dispatch(data.get('op'),args)
                        if data.get('op') in {'hook','unhook','scan'}:await self.configure_hotkeys()
                        await self.send({'type':'result','id':data['id'],'ok':True,'data':result})
                        if data.get('op') not in {'get_settings','set_settings','pause_hotkeys','shortcut_context'}:
                            async with self.lock: await self.state()
                    except Exception as exc:
                        await self.send({'type':'result','id':data.get('id') if isinstance(data,dict) else None,'ok':False,'error':f'{type(exc).__name__}: {exc}'})
                        await self.log(str(exc), 'error')
            except (TimeoutError, json.JSONDecodeError):
                await ws.close(code=1008,message=b'Invalid auth handshake')
            finally:
                if poll:
                    poll.cancel()
                    with contextlib.suppress(asyncio.CancelledError): await poll
                if self.ws is ws:
                    self.session_generation += 1
                    await asyncio.to_thread(self.hotkeys.stop)
                    self.shortcut_context = {'ids':[], 'source':''}
                    await self.automations.stop()
                    await self.stop()
                    async with self.lock:
                        try: await self.adapter.close()
                        except Exception as exc:
                            self.cleanup_error = str(exc)
                            print('UNHOOK FEHLER: ',exc, flush=True)
                    self.ws = None
                    self.observer('Unhook-Fehler' if self.cleanup_error else 'Dashboard getrennt',self.cleanup_error or 'Hooks entfernt · Dashboard öffnen zum erneuten Koppeln.')
                    print('Dashboard getrennt; Skript- und Hook-Aufraeumen abgeschlossen.' if not self.cleanup_error else 'Dashboard getrennt; Unhook-Fehler im Protokoll beachten.', flush=True)
            return ws

    async def shutdown(self, app):
        self.shutting_down = True
        self.session_generation += 1
        await asyncio.to_thread(self.hotkeys.stop)
        await self.automations.stop()
        await self.stop()
        if self.ws: await self.ws.close(code=1001,message=b'Bridge shutdown')
        async with self.lock: await self.adapter.close()


def create_app(bridge, web_dir):
    app = web.Application(client_max_size=65536)
    app.router.add_get('/ws',bridge.websocket)
    async def index(request):
        return web.FileResponse(web_dir/'index.html')
    async def health(request):
        return web.json_response({'service':'mythic-walker','version':VERSION,'demo':bridge.demo})
    app.router.add_get('/health',health)
    app.router.add_get('/',index)
    # Serve only the explicit frontend assets, never bridge source/certificates.
    for filename in ['app.js','settings.js','tools.js','style.css','sources.json']:
        async def asset(request, filename=filename): return web.FileResponse(web_dir/filename)
        app.router.add_get('/'+filename,asset)
    app.on_shutdown.append(bridge.shutdown)
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo',action='store_true',help='Test backend without Wizard101')
    parser.add_argument('--generate-cert',action='store_true')
    parser.add_argument('--origin',default=SITE_ORIGIN)
    args = parser.parse_args()
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
