import asyncio
import base64
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from aiohttp.test_utils import TestClient, TestServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from launcher_vault import Vault, LauncherError, dpapi
from launcher_native import launch_args, NativeLauncher
from launcher_service import LauncherService, local_app, LOCAL_ORIGIN

class FixtureCipher:
    def __init__(self):self.f=Fernet(Fernet.generate_key())
    def __call__(self,data,decrypt=False):return self.f.decrypt(data) if decrypt else self.f.encrypt(data)

class VaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.cipher=FixtureCipher();self.vault=Vault(self.tmp.name,self.cipher);self.vault.unlock()
        self.account={'name':'Example','username':'sensitive-user','password':'sensitive-pass','region':'de'}
    def test_encrypted_roundtrip_and_no_password_readback(self):
        self.vault.put(self.account)
        self.assertNotIn(b'sensitive',self.vault.path.read_bytes())
        self.assertNotIn('password',self.vault.public()[0])
        copy=Vault(self.tmp.name,self.cipher);copy.unlock();self.assertEqual(copy.rows[0]['password'],'sensitive-pass')
        copy.lock()
        with self.assertRaises(LauncherError):copy.public()
    def test_edit_keeps_password_and_rejects_duplicate(self):
        self.vault.put(self.account);row=self.vault.public()[0]
        self.vault.put({**row,'name':'Edited','password':''})
        self.assertEqual(self.vault.rows[0]['password'],'sensitive-pass')
        with self.assertRaises(LauncherError):self.vault.put(self.account)
        self.vault.delete(row['id']);self.assertEqual(self.vault.rows,[])
    def test_save_failure_does_not_replace_previous_accounts(self):
        self.vault.put(self.account);old=self.vault.path.read_bytes()
        with patch.object(self.vault,'_atomic',side_effect=OSError('private path')):
            with self.assertRaises(OSError):self.vault.put({**self.account,'username':'other'})
        self.assertEqual(len(self.vault.rows),1);self.assertEqual(self.vault.path.read_bytes(),old)
    def test_wizq_master_import_is_read_only_and_deduplicates(self):
        salt=b'x'*16;kdf=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=390000)
        key=base64.urlsafe_b64encode(kdf.derive(b'master'))
        data={'data':Fernet(key).encrypt(json.dumps([{**self.account,'last_used':123,'total_playtime':20}]).encode()).decode(),'salt':base64.b64encode(salt).decode(),'iterations':390000,'mode':'password'}
        path=self.vault.root/'data'/'accounts.enc.json';path.write_text(json.dumps(data));before=path.read_bytes()
        with self.assertRaises(LauncherError):self.vault.import_wizq('wrong')
        self.assertEqual(self.vault.rows,[])
        self.assertEqual(self.vault.import_wizq('master'),1);self.assertEqual(self.vault.import_wizq('master'),0)
        self.assertEqual(path.read_bytes(),before)
    def test_wizq_local_key_and_existing_paths(self):
        key=Fernet.generate_key()
        config={'master_password_mode':'local','master_password_secret_b64':base64.b64encode(self.cipher(key)).decode(),'region_install_de':'D:/WizDE','discord_webhook_url':'https://never.invalid'}
        (self.vault.root/'config.json').write_text(json.dumps(config))
        (self.vault.root/'data'/'accounts.enc.json').write_text(json.dumps({'data':Fernet(key).encrypt(json.dumps([self.account]).encode()).decode(),'mode':'local'}))
        self.vault.unlock();self.assertEqual(self.vault.settings['paths']['de'],'D:/WizDE')
        self.assertNotIn('discord_webhook_url',self.vault.settings)
        self.assertEqual(self.vault.import_wizq(),1)
    def test_control_characters_and_invalid_regions_rejected(self):
        for field,value in [('password','pass\tEnter'),('username','u\n'),('region','other')]:
            with self.assertRaises(LauncherError):self.vault.put({**self.account,field:value})
    @unittest.skipUnless(sys.platform=='win32','Windows DPAPI')
    def test_real_windows_dpapi_roundtrip(self):
        protected=dpapi(b'unit-test-secret');self.assertNotIn(b'unit-test-secret',protected)
        self.assertEqual(dpapi(protected,True),b'unit-test-secret')
    def test_fixed_login_endpoint_no_credentials_in_arguments(self):
        p=Path(self.tmp.name)/'Wizard101(DE)'/'Bin';p.mkdir(parents=True);(p/'WizardGraphicalClient.exe').write_bytes(b'MZ')
        args=launch_args('de',str(p.parent));self.assertEqual(args[1:],['-L','login-de.eu.wizard101.com','12000','-A','de'])
        self.assertNotIn('password',' '.join(args))
        for path in ['relative','//host/share']:
            with self.assertRaises(LauncherError):launch_args('de',path)

class LocalApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.vault=Vault(self.tmp.name,FixtureCipher())
        self.service=LauncherService(self.vault);self.service.available=True;self.service.enabled=True
        self.client=TestClient(TestServer(local_app(self.service,{'https://dashboard.invalid'})))
        await self.client.start_server();self.session=None
    async def asyncTearDown(self):
        await self.service.revoke();await self.client.close();self.tmp.cleanup()
    async def post(self,action,data=None,origin=LOCAL_ORIGIN,host='localhost:18762'):
        return await self.client.post('/api/'+action,json=data or {},headers={'Origin':origin,'Host':host,**({'Authorization':'Bearer '+self.session} if self.session else {})})
    async def connect(self):
        ticket=self.service.issue_ticket()['url'].split('#ticket=')[1]
        r=await self.post('exchange',{'ticket':ticket});self.assertEqual(r.status,200)
        self.session=(await r.json())['session'];return ticket
    async def test_disabled_by_default_and_revokes_existing_session(self):
        self.assertFalse(LauncherService(self.vault).enabled)
        await self.connect();await self.post('unlock')
        await self.post('save',{'name':'n','username':'u','password':'p','region':'de'})
        await self.service.set_enabled(False)
        self.assertIsNone(self.service.ticket);self.assertIsNone(self.service.session);self.assertIsNone(self.vault.rows)
        with self.assertRaises(LauncherError):self.service.issue_ticket()
        self.assertEqual((await self.post('state')).status,403)
        await self.service.set_enabled(True);await self.connect();await self.post('unlock')
        self.assertEqual(len(self.vault.rows),1)
    async def test_ticket_one_time_and_short_lived(self):
        ticket=await self.connect();self.assertNotEqual(ticket,self.session)
        self.assertEqual((await self.post('exchange',{'ticket':ticket})).status,401)
        next_ticket=self.service.issue_ticket()['url'].split('#ticket=')[1];self.service.ticket_until=0
        self.assertEqual((await self.post('exchange',{'ticket':next_ticket})).status,401)
    async def test_cloud_cannot_exchange_or_read_even_with_tokens(self):
        ticket=self.service.issue_ticket()['url'].split('#ticket=')[1]
        r=await self.post('exchange',{'ticket':ticket},origin='https://dashboard.invalid');self.assertEqual(r.status,403)
        self.assertNotIn('Access-Control-Allow-Origin',r.headers)
        await self.connect();await self.post('unlock')
        for origin in ['https://dashboard.invalid','https://localhost:18761','null','https://evil.invalid']:
            self.assertEqual((await self.post('state',origin=origin)).status,403)
    async def test_bad_host_and_unauthenticated_calls(self):
        self.assertEqual((await self.post('state')).status,401)
        await self.connect()
        self.assertEqual((await self.post('state',host='evil.invalid')).status,403)
    async def test_no_get_api_no_cors_strict_csp(self):
        r=await self.client.get('/',headers={'Host':'localhost:18762'})
        self.assertEqual(r.status,200);self.assertEqual(r.headers['Cache-Control'],'no-store')
        self.assertIn("connect-src 'self'",r.headers['Content-Security-Policy']);self.assertIn("form-action 'none'",r.headers['Content-Security-Policy'])
        self.assertEqual((await self.client.get('/api/state',headers={'Host':'localhost:18762'})).status,405)
        self.assertEqual((await self.client.get('/data/accounts.enc.json',headers={'Host':'localhost:18762'})).status,404)
    async def test_account_api_has_no_password_and_revokes_on_disconnect(self):
        await self.connect();self.assertEqual((await self.post('unlock')).status,200)
        r=await self.post('save',{'name':'Private name','username':'user','password':'DO-NOT-EXPOSE','region':'de'})
        body=await r.text();self.assertNotIn('DO-NOT-EXPOSE',body);self.assertNotIn('password',body)
        await self.service.revoke()
        self.assertIsNone(self.vault.rows);self.assertEqual((await self.post('state')).status,401)
    async def test_unknown_errors_do_not_disclose_secret_exception_text(self):
        await self.connect()
        with patch.object(self.vault,'unlock',side_effect=ValueError('SECRET-PASSWORD')):
            r=await self.post('unlock');self.assertEqual(r.status,400);self.assertNotIn('SECRET-PASSWORD',await r.text())
    async def test_start_is_background_and_stop_drains_login_thread(self):
        class Process:
            pid=777
            def poll(self):return None
        class Native:
            def start(self,*args):return Process()
            def login(self,process,account,wait,cancel):cancel.wait(5);return False
        self.service.native=Native();await self.connect();await self.post('unlock')
        await self.post('save',{'name':'n','username':'u','password':'p','region':'de'})
        self.vault.settings['paths']['de']=self.tmp.name
        ident=self.vault.rows[0]['id']
        with patch('launcher_service.launch_args',return_value=['game']):
            r=await self.post('launch',{'ids':[ident]});self.assertEqual(r.status,200)
            self.assertTrue(self.service.progress['running']);await asyncio.sleep(.05)
            await self.post('lock')
        self.assertFalse(self.service.progress['running']);self.assertIsNone(self.vault.rows)
        self.assertEqual(self.service.processes[0].poll(),None)
    async def test_session_expiry_denies_accounts(self):
        await self.connect();await self.post('unlock');self.service.session_until=0
        self.assertEqual((await self.post('state')).status,401)

if __name__=='__main__':unittest.main()
