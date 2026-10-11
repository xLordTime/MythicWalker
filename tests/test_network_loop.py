import asyncio
from pathlib import Path
import ssl
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from aiohttp import ClientSession,web
from adapter import DemoAdapter
from server import bridge_event_loop,Bridge,create_app,ensure_cert

class NetworkLoopTests(unittest.TestCase):
    def test_windows_loop_tls_websocket_and_peer_disconnect(self):
        loop=bridge_event_loop('win32')
        self.assertIsInstance(loop,asyncio.SelectorEventLoop)
        errors=[]
        loop.set_exception_handler(lambda loop,context: errors.append(context))
        async def verify():
            with tempfile.TemporaryDirectory() as directory:
                cert,key=ensure_cert(Path(directory))
                tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(cert,key)
                bridge=Bridge(DemoAdapter(),'test',['https://dashboard.example'],True)
                runner=web.AppRunner(create_app(bridge,Path(__file__).resolve().parents[1]/'dist'))
                await runner.setup()
                try:
                    site=web.TCPSite(runner,'127.0.0.1',0,ssl_context=tls);await site.start()
                    base='https://127.0.0.1:'+str(site._server.sockets[0].getsockname()[1])
                    async with ClientSession() as client:
                        ws=await client.ws_connect(base+'/ws',ssl=False,headers={'Origin':'https://dashboard.example'})
                        await ws.send_json({'type':'auth','token':'test'})
                        self.assertEqual((await ws.receive_json())['type'],'ready')
                        await bridge.adapter.hook(['9001'])
                        # Simulate a peer disappearing without a normal WS close.
                        ws._response.connection.transport.abort()
                        async with asyncio.timeout(3):
                            while bridge.session_lock.locked():await asyncio.sleep(.01)
                        self.assertFalse(bridge.adapter.rows[0]['hooked'])
                        async with client.get(base+'/health',ssl=False) as response:
                            self.assertEqual(response.status,200)
                finally:await runner.cleanup()
        try:loop.run_until_complete(verify())
        finally:loop.close()
        self.assertEqual(errors,[])

if __name__=='__main__':unittest.main()
