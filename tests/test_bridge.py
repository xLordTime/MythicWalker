import asyncio
import json
from pathlib import Path
import ssl
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from aiohttp import ClientSession, web, WSServerHandshakeError
from adapter import DemoAdapter, WizAdapter
from protocol import parse_script, number
from server import Bridge, create_app, ensure_cert

class ProtocolTests(unittest.TestCase):
    def test_compatible_subset(self):
        steps=parse_script('# demo\nmass waitforcombat completion\nsleep 0.5\nmass sendkey W 0.2\np2 tp XYZ(-15.3, 20, 0)')
        self.assertEqual([s['op'] for s in steps],['wait_combat','sleep','key','teleport'])
        self.assertEqual(steps[-1]['xyz'],[-15.3,20,0])
    def test_reject_unsafe_and_unsupported(self):
        for source in ['import os','mass tp closestmob','loop {','sleep 61','mass sendkey W 10','mass tp XYZ(NaN, 0, 0)','mass sendkey NOT_A_KEY 1','p0 sendkey X 0.1']:
            with self.subTest(source=source), self.assertRaises(ValueError):parse_script(source)
        with self.assertRaises(ValueError):parse_script('sleep 0\n'*201)
        with self.assertRaises(ValueError):number(True)

class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_finishes_current_memory_step(self):
        started=asyncio.Event();released=asyncio.Event()
        class Adapter(DemoAdapter):
            async def execute(self, op, args):
                started.set()
                await asyncio.sleep(.03)
                released.set()
        b=Bridge(Adapter(),'test',[],True)
        task=asyncio.create_task(b.protected_step('key',{}))
        await started.wait();task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertTrue(released.is_set())

    async def test_hook_failure_cleanup_and_recovery(self):
        class Client:
            process_id=42
            body=type('Body',(),{'position':AsyncMock(return_value=object())})()
            mouse_handler=type('Mouse',(),{'activate_mouseless':AsyncMock()})()
            activate_hooks=AsyncMock(side_effect=ValueError('Pattern missing'))
            close=AsyncMock()
            def is_running(self):return True
        c=Client(); a=WizAdapter.__new__(WizAdapter)
        a.handler=type('Handler',(),{'clients':[c]})();a.hooked=set();a.errors={};a.freecam=set();a.original_speeds={}
        result=await a.hook(['42'])
        self.assertFalse(result[0]['ok']);self.assertNotIn('42',a.hooked);c.close.assert_awaited_once()
        c.activate_hooks.side_effect=None
        result=await a.hook(['42'])
        self.assertTrue(result[0]['ok']);self.assertIn('42',a.hooked)
        c.mouse_handler.activate_mouseless.assert_not_awaited()
        await a.unhook(['42']);self.assertNotIn('42',a.hooked)

class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();cert,key=ensure_cert(Path(self.tmp.name))
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(cert,key)
        self.bridge=Bridge(DemoAdapter(),'test-pairing',['https://dashboard.example'],True)
        self.runner=web.AppRunner(create_app(self.bridge,Path(__file__).resolve().parents[1]/'dist'))
        await self.runner.setup();site=web.TCPSite(self.runner,'127.0.0.1',0,ssl_context=tls);await site.start()
        self.base='https://127.0.0.1:'+str(site._server.sockets[0].getsockname()[1])
        self.session=ClientSession()
    async def asyncTearDown(self):
        await self.session.close();await self.runner.cleanup();self.tmp.cleanup()
    async def connect(self,token='test-pairing'):
        ws=await self.session.ws_connect(self.base+'/ws',ssl=False,headers={'Origin':'https://dashboard.example'})
        await ws.send_json({'type':'auth','token':token})
        return ws
    async def request(self,ws,op,args=None):
        await ws.send_json({'id':op,'op':op,'args':args or {}})
        while True:
            msg=await ws.receive_json(timeout=5)
            if msg.get('type')=='result' and msg.get('id')==op:return msg
    async def test_origin_and_token_rejected(self):
        with self.assertRaises(WSServerHandshakeError) as error:
            await self.session.ws_connect(self.base+'/ws',ssl=False,headers={'Origin':'https://evil.example'})
        self.assertEqual(error.exception.status,403)
        ws=await self.connect('wrong');await ws.receive();self.assertEqual(ws.close_code,1008)
    async def test_authenticated_roundtrip_and_disconnect_unhook(self):
        ws=await self.connect();self.assertEqual((await ws.receive_json())['type'],'ready')
        scan=await self.request(ws,'scan');ids=[r['id'] for r in scan['data']]
        self.assertTrue((await self.request(ws,'hook',{'ids':ids}))['ok'])
        self.assertTrue((await self.request(ws,'teleport',{'ids':ids,'xyz':[55,66,77]}))['ok'])
        snap=await self.request(ws,'snapshot');self.assertEqual(snap['data'][0]['position'],[55,66,77])
        await ws.send_str('{invalid json')
        while True:
            msg=await ws.receive_json(timeout=5)
            if msg.get('type')=='result':break
        self.assertFalse(msg['ok'])
        self.assertFalse((await self.request(ws,'eval',{'source':'__import__("os")'}))['ok'])
        await ws.close()
        async with asyncio.timeout(3):
            while self.bridge.session_lock.locked():await asyncio.sleep(.01)
        self.assertFalse(any(r['hooked'] for r in self.bridge.adapter.rows))
    async def test_stop_and_script_validation(self):
        ws=await self.connect();await ws.receive_json();await self.request(ws,'hook',{'ids':['9001']})
        invalid=await self.request(ws,'run_script',{'ids':['9001'],'source':'p2 sendkey X 0.1'})
        self.assertFalse(invalid['ok']);self.assertIsNone(self.bridge.script_task)
        start=await self.request(ws,'run_script',{'ids':['9001'],'source':'sleep 60\nmass sendkey W 0.2'})
        self.assertTrue(start['ok']);self.assertFalse(self.bridge.script_task.done())
        stop=await self.request(ws,'stop');self.assertTrue(stop['ok']);self.assertIsNone(self.bridge.script_task)
        with self.assertRaises(WSServerHandshakeError) as error:
            await self.session.ws_connect(self.base+'/ws',ssl=False,headers={'Origin':'https://dashboard.example'})
        self.assertEqual(error.exception.status,409)
        await ws.close()
    async def test_settings_websocket_roundtrip_and_hotkey_cleanup(self):
        from settings import DEFAULTS
        ws=await self.connect();await ws.receive_json()
        settings=await self.request(ws,'get_settings')
        self.assertEqual(settings['data']['settings'],DEFAULTS)
        changed={**DEFAULTS,'key_seconds':0.7,'global_hotkeys':True}
        result=await self.request(ws,'set_settings',{'settings':changed})
        self.assertTrue(result['ok']);self.assertEqual(result['data']['settings']['key_seconds'],0.7)
        bad=await self.request(ws,'set_settings',{'settings':{**changed,'poll_seconds':False}})
        self.assertFalse(bad['ok']);self.assertEqual(self.bridge.settings.data['key_seconds'],0.7)
        await self.request(ws,'shortcut_context',{'ids':['9001'],'source':'mass sendkey X 0.1'})
        async with self.session.get(self.base+'/settings.js',ssl=False) as r:self.assertEqual(r.status,200)
        await ws.close()
        async with asyncio.timeout(3):
            while self.bridge.session_lock.locked():await asyncio.sleep(.01)
        self.assertEqual(self.bridge.shortcut_context,{'ids':[],'source':''})
        self.assertEqual(self.bridge.hotkeys.status['active'],[])

    async def test_local_assets_and_certificate(self):
        async with self.session.get(self.base+'/',ssl=False) as r:
            self.assertEqual(r.status,200);self.assertIn('MYTHIC',await r.text())
        async with self.session.get(self.base+'/certs/localhost.key',ssl=False) as r:self.assertEqual(r.status,404)
        trusted=ssl.create_default_context(cafile=str(Path(self.tmp.name)/'localhost.crt'))
        async with self.session.get(self.base+'/health',ssl=trusted) as r:self.assertEqual(r.status,200)

if __name__=='__main__':unittest.main()
