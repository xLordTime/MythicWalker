"""Isolated local origin for accounts. The cloud dashboard only gets a one-use ticket."""
import asyncio
import contextlib
import secrets
import sys
import threading
import time
from pathlib import Path
from aiohttp import web
from diagnostics import hide_secret
from launcher_vault import Vault, REGIONS, LauncherError
from launcher_native import NativeLauncher, installations, launch_args

LOCAL_ORIGIN='https://localhost:18762'

class LauncherService:
    def __init__(self, vault=None, native=None):
        self.vault=vault or Vault();self.native=native or NativeLauncher()
        self.available=False;self.ticket=None;self.ticket_until=0
        self.session=None;self.session_until=0
        self.lock=asyncio.Lock();self.cancel=threading.Event();self.job=None
        self.progress={'running':False,'message':'Bereit.','done':0,'total':0}
        self.processes=[]

    def issue_ticket(self):
        if not self.available:raise LauncherError('Lokaler Launcher nicht verfügbar. Bridge aktualisieren bzw. Port 18762 prüfen.')
        self.ticket=secrets.token_urlsafe(32);self.ticket_until=time.monotonic()+30
        hide_secret(self.ticket)
        return {'url':LOCAL_ORIGIN+'/#ticket='+self.ticket}

    async def stop(self):
        self.cancel.set()
        if self.job and not self.job.done():
            await asyncio.shield(self.job)
        self.job=None

    async def revoke(self):
        self.ticket=None;self.session=None
        await self.stop()
        self.vault.lock()

    def check_session(self, value):
        if not self.session or time.monotonic()>=self.session_until or not secrets.compare_digest(value,'Bearer '+self.session):
            raise web.HTTPUnauthorized(text='Lokale Sitzung abgelaufen. Launcher erneut verbinden.')

    def snapshot(self):
        unlocked=self.vault.rows is not None
        self.processes=[p for p in self.processes if p.poll() is None]
        return {'unlocked':unlocked,'accounts':self.vault.public() if unlocked else [],
                'settings':self.vault.settings if unlocked else None,
                'folder':str(self.vault.root) if unlocked else None,
                'legacy':(self.vault.root/'data'/'accounts.enc.json').is_file() if unlocked else False,
                'imported':self.vault.imported if unlocked else False,
                'regions':REGIONS,'progress':dict(self.progress),'processes':[p.pid for p in self.processes]}

    async def launch(self, args):
        self.vault.require()
        if self.job and not self.job.done():raise LauncherError('Ein Startvorgang läuft bereits.')
        accounts=args.get('ids',[]);region=args.get('region','de');count=args.get('count',1)
        if not isinstance(accounts,list) or len(accounts)>16 or any(not isinstance(i,str) for i in accounts) or len(set(accounts))!=len(accounts):
            raise LauncherError('Maximal 16 eindeutige Konten auswählen.')
        if accounts:
            lookup={r['id']:r for r in self.vault.rows}
            if any(i not in lookup for i in accounts):raise LauncherError('Konto nicht gefunden.')
            queue=[dict(lookup[i]) for i in accounts]
        else:
            if type(count) is not int or not 1<=count<=16 or region not in REGIONS:raise LauncherError('Region und Anzahl (1–16) prüfen.')
            queue=[{'region':region} for _ in range(count)]
        self.processes=[p for p in self.processes if p.poll() is None]
        if len(self.processes)+len(queue)>16:raise LauncherError('Maximal 16 gleichzeitig vom Launcher gestartete Clients.')
        paths=dict(self.vault.settings['paths'])
        for r in {a['region'] for a in queue}:
            if not paths.get(r):raise LauncherError('Installationspfad für jede ausgewählte Region zuerst speichern.')
            launch_args(r,paths[r])
        self.cancel.clear();self.progress={'running':True,'message':'Spielstart wird vorbereitet.','done':0,'total':len(queue)}
        async def run():
            try:
                for index,account in enumerate(queue,1):
                    if self.cancel.is_set():break
                    self.progress['message']=f'Start {index} von {len(queue)} · {account["region"].upper()}'
                    process=await asyncio.to_thread(self.native.start,account['region'],paths[account['region']])
                    self.processes.append(process)
                    if self.cancel.is_set():break
                    if 'password' in account:
                        self.progress['message']=f'Login {index}: Spielfenster wird erwartet …'
                        completed=await asyncio.to_thread(self.native.login,process,account,self.vault.settings['login_wait'],self.cancel)
                        if not completed:break
                    self.progress['done']=index
                    if index<len(queue):await asyncio.sleep(.5)
                self.progress['message']='Startvorgang gestoppt. Bereits gestartete Spiele bleiben offen.' if self.cancel.is_set() else 'Start abgeschlossen. Login-Eingaben wurden gesendet; Erfolg im Spielfenster prüfen.' if accounts else 'Spielclients gestartet.'
            except LauncherError as exc:self.progress['message']=str(exc)
            except Exception:self.progress['message']='Spielstart fehlgeschlagen. Installation und Windows-Berechtigungen prüfen.'
            finally:
                for row in queue:row.clear()
                queue.clear();self.progress['running']=False
        self.job=asyncio.create_task(run())
        return {'started':True}

    async def api(self, request):
        # Do not accept a trusted *cloud* Origin here. Never add CORS to this API.
        if request.headers.get('Origin')!=LOCAL_ORIGIN or request.headers.get('Content-Type','').split(';')[0]!='application/json':
            raise web.HTTPForbidden(text='Nur die lokale Launcher-Ansicht darf diese API verwenden.')
        action=request.match_info['action']
        async with self.lock:
            try:
                args=await request.json()
                if not isinstance(args,dict):raise LauncherError('Ungültige Anfrage.')
                if action=='exchange':
                    ticket=args.get('ticket')
                    if not self.ticket or not isinstance(ticket,str) or time.monotonic()>=self.ticket_until or not secrets.compare_digest(ticket,self.ticket):
                        raise web.HTTPUnauthorized(text='Launcher-Ticket ungültig oder abgelaufen.')
                    await self.revoke()
                    self.session=secrets.token_urlsafe(32);hide_secret(self.session)
                    self.session_until=time.monotonic()+1800
                    return web.json_response({'session':self.session})
                self.check_session(request.headers.get('Authorization',''))
                if action=='end':
                    await self.revoke();return web.json_response({'locked':True})
                if action=='state':return web.json_response(self.snapshot())
                if action=='unlock':
                    if self.vault.rows is None:await asyncio.to_thread(self.vault.unlock)
                elif action=='lock':
                    await self.stop();self.vault.lock()
                elif action=='stop':await self.stop()
                elif action=='launch':return web.json_response(await self.launch(args))
                else:
                    self.vault.require()
                    if self.job and not self.job.done():raise LauncherError('Startvorgang zuerst stoppen.')
                    if action=='save':await asyncio.to_thread(self.vault.put,args)
                    elif action=='delete':await asyncio.to_thread(self.vault.delete,args.get('id'))
                    elif action=='import':
                        password=args.get('password','')
                        if not isinstance(password,str) or len(password)>1024:raise LauncherError('Masterpasswort prüfen.')
                        added=await asyncio.to_thread(self.vault.import_wizq,password)
                        return web.json_response({'added':added})
                    elif action=='settings':await asyncio.to_thread(self.vault.save_settings,args.get('paths'),args.get('login_wait'))
                    elif action=='detect':return web.json_response({'paths':await asyncio.to_thread(installations)})
                    else:raise web.HTTPNotFound()
                return web.json_response(self.snapshot())
            except web.HTTPException:raise
            except LauncherError as exc:return web.json_response({'error':str(exc)},status=400)
            except Exception:
                # No raw OS paths, data, exception representations or request bodies in logs.
                return web.json_response({'error':'Lokaler Vorgang fehlgeschlagen. Tresordatei, Windows-Benutzer und Zugriffsrechte prüfen.'},status=400)


def local_app(service, frame_origins, web_dir=None):
    directory=Path(web_dir or Path(__file__).parent/'launcher_web')
    csp="default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; object-src 'none'; frame-ancestors "+' '.join(sorted(frame_origins))
    @web.middleware
    async def privacy(request, handler):
        if request.host!='localhost:18762':raise web.HTTPForbidden(text='Unzulässiger Host.')
        try:response=await handler(request)
        except web.HTTPException as exc:response=web.Response(status=exc.status,text=exc.text,headers=exc.headers)
        response.headers.update({'Content-Security-Policy':csp,'Cache-Control':'no-store',
                                 'Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',
                                 'Permissions-Policy':'camera=(), microphone=(), geolocation=()'})
        return response
    app=web.Application(client_max_size=65536,middlewares=[privacy])
    async def index(request):return web.FileResponse(directory/'index.html')
    app.router.add_get('/',index)
    for filename in ['launcher.js','launcher.css']:
        async def asset(request, filename=filename):return web.FileResponse(directory/filename)
        app.router.add_get('/'+filename,asset)
    app.router.add_post('/api/{action}',service.api)
    return app


def attach_launcher(app, bridge, tls):
    service=LauncherService();bridge.launcher=service
    async def lifetime(_):
        runner=web.AppRunner(local_app(service,bridge.origins),access_log=None)
        await runner.setup()
        try:
            try:
                await web.TCPSite(runner,'127.0.0.1',18762,ssl_context=tls).start()
                service.available=True
            except OSError:
                bridge.observer('Launcher-Port belegt','Port 18762 freigeben. Die Spiel-Bridge bleibt verfügbar.')
            async def expire():
                while True:
                    await asyncio.sleep(2)
                    if service.session and time.monotonic()>=service.session_until:
                        async with service.lock:await service.revoke()
            watchdog=asyncio.create_task(expire())
            try:yield
            finally:
                watchdog.cancel()
                with contextlib.suppress(asyncio.CancelledError):await watchdog
                async with service.lock:await service.revoke()
        finally:
            service.available=False;await runner.cleanup()
    app.cleanup_ctx.append(lifetime)
