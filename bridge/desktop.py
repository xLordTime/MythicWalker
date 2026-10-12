"""Windows EXE entry point: update -> local TLS -> browser -> status widget."""
import asyncio
import ctypes
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import sys
import threading
import webbrowser
from urllib.parse import urlencode
from aiohttp import web
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from server import Bridge, SITE_ORIGIN, create_app, ensure_cert, bridge_event_loop
from adapter import WizAdapter, DemoAdapter
from updater import check_and_install, launch_update
from version import VERSION, CHANNEL, RELEASE_TAG
from widget import StatusWidget
from settings import Settings
from diagnostics import start_logging, event, logger, hide_secret
from windows_desktop import copy_text, focus_dashboard


def handoff_url(token,origin=SITE_ORIGIN):
    return origin+'/#'+urlencode({'pair':token})

def trust_certificate(cert):
    leaf=x509.load_pem_x509_certificate(cert.read_bytes())
    fingerprint=leaf.fingerprint(hashes.SHA1()).hex()
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    query=subprocess.run(['certutil','-user','-store','Root',fingerprint],capture_output=True,creationflags=flags)
    if query.returncode==0:return
    result=subprocess.run(['certutil','-user','-addstore','Root',str(cert)],capture_output=True,creationflags=flags)
    if result.returncode:raise RuntimeError('Lokales Zertifikatsvertrauen konnte nicht eingerichtet werden.')


def main():
    if sys.platform!='win32':raise RuntimeError('Desktop-App benötigt Windows.')
    if '--smoke-test' in sys.argv:
        from vendor import fishbot_de
        if not callable(fishbot_de.main):raise RuntimeError('FishBot fehlt im EXE-Paket.')
        widget=StatusWidget(VERSION+' Beta');widget.report('Native UI Smoke Test','Fenster, Zeichnen und Schließen prüfen.')
        widget.copy_pairing=lambda:setattr(widget,'smoke_pairing',widget.smoke_pairing+1)
        threading.Timer(.3,lambda:widget.visibility('hide')).start()
        threading.Timer(.5,lambda:widget.visibility('show')).start()
        threading.Timer(.7,lambda:widget.events.put(('smoke','',''))).start()
        threading.Timer(1.2,widget.finish).start();widget.run()
        if widget.hidden or widget.smoke_toggles!=2:raise RuntimeError('Widget hide/show smoke test failed.')
        return
    root=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'MythicWalker';root.mkdir(parents=True,exist_ok=True)
    start_logging(root)
    widget=StatusWidget(RELEASE_TAG.removeprefix('v'));widget.configure(Settings(root/'user-settings.json').data['widget']);stop=threading.Event();finished=threading.Event();launch={'url':SITE_ORIGIN,'token':None,'bridge':None,'loop':None}
    def open_browser():
        bridge=launch['bridge'];loop=launch['loop']
        if bridge is not None and bridge.ws is not None and not bridge.ws.closed:
            asyncio.run_coroutine_threadsafe(bridge.send({'type':'dashboard_focus'}),loop)
            focused=focus_dashboard()
            event('browser.reuse', focused=focused)
            widget.report('Dashboard bereits offen','Vorhandenen Browser-Tab verwenden. Rechtsklick kopiert den Pairing-Code.')
            return True
        event('browser.open.begin', paired_link='#pair=' in launch['url'])
        result = webbrowser.open(launch['url'])
        event('browser.open.return', accepted=result)
        return result
    widget.browser=open_browser
    def copy_pairing():
        if not launch['token']:
            widget.report('Pairing noch nicht bereit','Warte, bis die Bridge gestartet ist.');return
        try:
            copy_text(launch['token'],widget.hwnd);event('pairing.clipboard.copied')
            widget.report('Pairing-Code kopiert','In der Weboberfläche unter Bridge mit Strg+V einfügen.')
        except Exception as exc:
            logger.exception('pairing.clipboard.failed');widget.report('Kopieren fehlgeschlagen',str(exc))
    widget.copy_pairing=copy_pairing
    def close():
        widget.report('Bridge beenden','Automatik stoppen und Hooks entfernen …');stop.set()
        if finished.is_set():widget.finish()
    widget.stop=close
    async def serve():
        widget.report('Zertifikat vorbereiten','Lokale Verbindung für diesen Windows-Benutzer.')
        cert,key=ensure_cert(root/'certs');await asyncio.to_thread(trust_certificate,cert)
        event('certificate.trusted')
        token=secrets.token_urlsafe(24)
        hide_secret(token)
        bridge=Bridge(DemoAdapter() if '--demo' in sys.argv else WizAdapter(),token,[SITE_ORIGIN,'https://localhost:18761','https://127.0.0.1:18761'],'--demo' in sys.argv,settings_path=root/'user-settings.json',observer=widget.report,widget=widget)
        launch.update(token=token,bridge=bridge,loop=asyncio.get_running_loop())
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.minimum_version=ssl.TLSVersion.TLSv1_2;tls.load_cert_chain(cert,key)
        web_dir=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'web'
        runner=web.AppRunner(create_app(bridge,web_dir));await runner.setup()
        try:
            widget.report('Bridge starten','HTTPS · localhost:18761')
            await web.TCPSite(runner,'127.0.0.1',18761,ssl_context=tls).start()
            event('server.listening', host='127.0.0.1', port=18761)
            launch['url']=handoff_url(token)
            widget.report('Browser öffnen','Dashboard wird automatisch gekoppelt.')
            await asyncio.to_thread(open_browser)
            if bridge.ws is None or bridge.ws.closed:
                widget.report('Kopplung wartet','Falls nötig im Browser anmelden und lokalen Netzwerkzugriff erlauben.')
            while not stop.is_set():await asyncio.sleep(.2)
        finally:await runner.cleanup()
    def worker():
        try:
            resource=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'release_source.json'
            repo=json.loads(resource.read_text()).get('repository','') if resource.exists() else ''
            if repo and getattr(sys,'frozen',False) and '--updated' not in sys.argv:
                try:
                    def report(title,detail=''):
                        event('startup.step', title=title, detail=detail)
                        widget.report(title,detail)
                    new=check_and_install(repo,RELEASE_TAG,root,report,channel=CHANNEL)
                    if new and not stop.is_set():
                        launch_update(new);widget.finish();return
                except Exception as exc:
                    logger.exception('update.failed');widget.report('Update nicht verfügbar',str(exc))
            elif not repo:widget.report('Updatequelle noch offen','GitHub-Release-Repository wird beim Build hinterlegt.')
            if stop.is_set():widget.finish();return
            loop=bridge_event_loop()
            event('event_loop', implementation=type(loop).__name__)
            loop.set_exception_handler(lambda loop,context: logger.error('asyncio.failed %s',context.get('message'),exc_info=context.get('exception')))
            try:loop.run_until_complete(serve())
            finally:loop.close()
            widget.finish()
        except Exception as exc:
            logger.exception('desktop.failed')
            widget.report('Fehler',str(exc)+' · Details: bridge.log')
        finally:
            finished.set()
            event('desktop.worker.finished')
            if stop.is_set():widget.finish()
    thread=threading.Thread(target=worker,name='MythicBridge',daemon=False);thread.start()
    try:widget.run()
    finally:
        stop.set();thread.join(timeout=55)

if __name__=='__main__':main()
