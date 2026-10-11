import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import urlsplit,parse_qs
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from updater import check_and_install,version_tuple
from desktop import handoff_url

class UpdateTests(unittest.TestCase):
    def test_pairing_is_fragment_only(self):
        url=urlsplit(handoff_url('pair-code'))
        self.assertEqual(url.query,'');self.assertEqual(parse_qs(url.fragment),{'pair':['pair-code']})
        self.assertEqual(url.hostname,'mythic-walker.lord-time.chatgpt.site')
    def test_valid_release_and_tampered_download(self):
        repo='example/MythicWalker';data=b'MZ'+b'a'*100
        release={'tag_name':'v0.4.0','assets':[{'name':n,'browser_download_url':f'https://github.com/{repo}/releases/download/v0.4.0/{n}'} for n in ['bridge-release.json','MythicWalker.exe']]}
        manifest={'version':'0.4.0','filename':'MythicWalker.exe','sha256':hashlib.sha256(data).hexdigest()}
        def fetch(url,limit):
            if url.endswith('/latest'):return json.dumps(release).encode()
            if url.endswith('.json'):return json.dumps(manifest).encode()
            return data
        with tempfile.TemporaryDirectory() as directory:
            path=check_and_install(repo,'0.3.0',directory,lambda *args:None,fetch)
            self.assertEqual(path.read_bytes(),data)
            manifest['sha256']='0'*64
            with self.assertRaises(ValueError):check_and_install(repo,'0.3.0',directory,lambda *args:None,fetch)
            self.assertEqual(path.read_bytes(),data)
    def test_no_downgrade_and_reject_cross_repo_asset(self):
        def latest(url,limit):return json.dumps({'tag_name':'v0.2.0'}).encode()
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(check_and_install('owner/repo','0.3.0',directory,lambda *a:None,latest))
            def hostile(url,limit):return json.dumps({'tag_name':'v0.4.0','assets':[{'name':'bridge-release.json','browser_download_url':'https://github.com/other/repo/releases/download/v0.4.0/a'}]}).encode()
            with self.assertRaises(ValueError):check_and_install('owner/repo','0.3.0',directory,lambda *a:None,hostile)
        for value in ['../../run','v0.3.0/../x','0.3.0-beta']:
            with self.assertRaises(ValueError):version_tuple(value)

class BetaUpdateTests(unittest.TestCase):
    def test_beta_channel_finds_newer_prerelease(self):
        repo='example/MythicWalker';payload=b'MZ-beta';tag='v0.1.1-beta.2'
        manifest={'version':'0.1.1','filename':'MythicWalker.exe','sha256':hashlib.sha256(payload).hexdigest()}
        release={'tag_name':tag,'prerelease':True,'assets':[{'name':name,'browser_download_url':f'https://github.com/{repo}/releases/download/{tag}/{name}'} for name in ['bridge-release.json','MythicWalker.exe']]}
        def fetch(url,limit):
            if '/releases?' in url:return json.dumps([release]).encode()
            if url.endswith('.json'):return json.dumps(manifest).encode()
            return payload
        with tempfile.TemporaryDirectory() as directory:
            path=check_and_install(repo,'v0.1.1-beta.1',directory,lambda *a:None,fetch,channel='beta')
            self.assertEqual(path.read_bytes(),payload);self.assertEqual(path.parent.name,'0.1.1-beta.2')
