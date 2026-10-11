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
        widget=StatusWidget(VERSION+' Beta');widget.report('Native UI Smoke Test','Fenster, Zeichnen und Schließen prüfen.')
        threading.Timer(.3,lambda:widget.visibility('hide')).start()
        threading.Timer(.5,lambda:widget.visibility('show')).start()
        threading.Timer(.7,lambda:widget.events.put(('smoke','',''))).start()
        threading.Timer(1.2,widget.finish).start();widget.run()
        if widget.hidden or widget.smoke_toggles!=2:raise RuntimeError('Widget hide/show smoke test failed.')
        return
    root=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'MythicWalker';root.mkdir(parents=True,exist_ok=True)
    widget=StatusWidget(VERSION+' Beta');widget.configure(Settings(root/'user-settings.json').data['widget']);stop=threading.Event();finished=threading.Event();launch={'url':SITE_ORIGIN}
    widget.browser=lambda:webbrowser.open(launch['url'])
    def close():
        widget.report('Bridge beenden','Automatik stoppen und Hooks entfernen …');stop.set()
        if finished.is_set():widget.finish()
    widget.stop=close
    async def serve():
        widget.report('Zertifikat vorbereiten','Lokale Verbindung für diesen Windows-Benutzer.')
        cert,key=ensure_cert(root/'certs');await asyncio.to_thread(trust_certificate,cert)
        token=secrets.token_urlsafe(24)
        bridge=Bridge(DemoAdapter() if '--demo' in sys.argv else WizAdapter(),token,[SITE_ORIGIN,'https://localhost:18761','https://127.0.0.1:18761'],'--demo' in sys.argv,settings_path=root/'user-settings.json',observer=widget.report,widget=widget)
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.minimum_version=ssl.TLSVersion.TLSv1_2;tls.load_cert_chain(cert,key)
        web_dir=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'web'
        runner=web.AppRunner(create_app(bridge,web_dir));await runner.setup()
        try:
            widget.report('Bridge starten','HTTPS · localhost:18761')
            await web.TCPSite(runner,'127.0.0.1',18761,ssl_context=tls).start()
            launch['url']=handoff_url(token)
            widget.report('Browser öffnen','Dashboard wird automatisch gekoppelt.')
            await asyncio.to_thread(webbrowser.open,launch['url'])
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
                    new=check_and_install(repo,RELEASE_TAG,root,widget.report,channel=CHANNEL)
                    if new and not stop.is_set():
                        launch_update(new);widget.finish();return
                except Exception as exc:widget.report('Update nicht verfügbar',str(exc))
            elif not repo:widget.report('Updatequelle noch offen','GitHub-Release-Repository wird beim Build hinterlegt.')
            if stop.is_set():widget.finish();return
            loop=bridge_event_loop()
            try:loop.run_until_complete(serve())
            finally:loop.close()
            widget.finish()
        except Exception as exc:
            widget.report('Fehler',str(exc)+' · Details: bridge.log')
            (root/'bridge.log').write_text(type(exc).__name__+': '+str(exc),encoding='utf-8')
        finally:
            finished.set()
            if stop.is_set():widget.finish()
    thread=threading.Thread(target=worker,name='MythicBridge',daemon=False);thread.start()
    try:widget.run()
    finally:
        stop.set();thread.join(timeout=55)

if __name__=='__main__':main()
