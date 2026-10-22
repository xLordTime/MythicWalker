import asyncio
import base64
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave
import zlib
sys.path.insert(0,str(Path(__file__).parents[1]/'bridge'))
from sound_files import SoundStore, SoundError, WadIndex, audio_info, digest, ki_crc, RECORD
from sounds import Sounds, require_game_closed


def wav(value=100,frames=100,rate=22050):
    output=io.BytesIO()
    with wave.open(output,'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes(struct.pack('<h',value)*frames)
    return output.getvalue()


def wad(path,files,version=2,compressed=True):
    names=list(files);offset=13+(version>=2)+sum(21+len(n.encode())+1 for n in names)
    header=bytearray(b'KIWAD'+struct.pack('<ll',version,len(names))+(b'\x01' if version>=2 else b''));payload=bytearray()
    for name in names:
        data=files[name];stored=zlib.compress(data) if compressed else data
        header+=RECORD.pack(offset,len(data),len(stored) if compressed else -1,compressed,ki_crc(stored),len(name.encode())+1)+name.encode()+b'\0'
        payload+=stored;offset+=len(stored)
    path.write_bytes(header+payload)


class SoundFileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();self.game=self.root/'game'
        (self.game/'Bin').mkdir(parents=True);(self.game/'Bin'/'WizardGraphicalClient.exe').write_bytes(b'test')
        (self.game/'Data'/'GameData').mkdir(parents=True)
        self.path=self.game/'Data'/'GameData'/'Sound-WorldData.wad';self.first=wav();self.second=wav(200)
        wad(self.path,{'Sounds/player_hurt.wav':self.first,'Sounds/other.wav':self.second,'config.xml':b'keep me exactly'})
        self.baseline=self.path.read_bytes();self.store=SoundStore(self.root/'user',lambda:None);self.store.configure(str(self.game))
    def tearDown(self):self.temp.cleanup()
    def change(self,name='Sounds/player_hurt.wav',data=None,restore=False):
        inspected=self.store.inspect(self.path.name,name)
        return self.store.replace(self.path.name,name,data or wav(300),inspected['sha256'],'Schaden bekommen',restore)
    def test_scan_inspect_and_candidate(self):
        rows=self.store.files(self.path.name)['files'];self.assertEqual(rows[0]['name'],'Sounds/player_hurt.wav')
        self.assertTrue(rows[0]['candidate']);self.assertEqual(len(rows),2)
        self.assertEqual(base64.b64decode(self.store.inspect(self.path.name,rows[0]['name'])['data']),self.first)
    def test_configuration_roundtrips_non_ascii_installation_paths(self):
        moved=self.root/'Spiel-Ä例';self.game.rename(moved);self.store.configure(str(moved))
        reopened=SoundStore(self.root/'user',lambda:None)
        self.assertEqual(reopened.game,moved)
        self.assertEqual(reopened.archives()['archives'][0]['id'],self.path.name)
    def test_root_bin_gamedata_executable_and_wad_paths_are_accepted(self):
        for p in [self.game,self.game/'Bin',self.game/'Data',self.path.parent,self.game/'Bin'/'WizardGraphicalClient.exe',self.path]:
            with self.subTest(path=p):
                result=self.store.configure('  "'+str(p)+'"  ')
                self.assertEqual(result['installation'],str(self.game))
                self.assertEqual(result['archives'][0]['id'],self.path.name)
    def test_original_preview_and_change_overview_after_replacement(self):
        self.change();preview=self.store.inspect(self.path.name,'Sounds/player_hurt.wav')
        self.assertEqual(base64.b64decode(preview['data']),wav(300))
        self.assertEqual(base64.b64decode(preview['baseline']['data']),self.first)
        self.assertEqual(preview['sha256'],hashlib.sha256(wav(300)).hexdigest())
        changes=self.store.changes()['changes']
        self.assertEqual(len(changes),1);self.assertEqual(changes[0]['archive'],self.path.name)
        self.assertEqual(changes[0]['label'],'Schaden bekommen')
        self.change(restore=True);self.assertEqual(self.store.changes()['changes'],[])
    def test_search_all_archives_is_read_only_and_keeps_archive_identity(self):
        second=self.path.with_name('Sound-Another.wad')
        wad(second,{'Sounds/player_hurt.wav':wav(500),'Sounds/music.wav':self.first})
        second.with_name('Unknown.wad').write_bytes(b'unsupported')
        before={p.name:digest(p) for p in self.path.parent.glob('*.wad')}
        result=self.store.search();self.assertEqual(result['total'],2);self.assertEqual(result['failed'],1)
        self.assertEqual({r['archive'] for r in result['files']},{self.path.name,second.name})
        self.assertEqual(self.store.search('music')['total'],1)
        self.assertEqual(self.store.search('DOES NOT EXIST')['files'],[])
        self.assertFalse((self.store.root/'backups').exists())
        self.assertEqual(before,{p.name:digest(p) for p in self.path.parent.glob('*.wad')})
    def test_global_search_bounds_and_limits(self):
        wad(self.path,{f'Sounds/hurt_{i}.wav':self.first for i in range(130)})
        result=self.store.search();self.assertEqual(len(result['files']),120)
        self.assertEqual(result['total'],130);self.assertTrue(result['limited'])
        with self.assertRaises(SoundError):self.store.search('x'*151)
    def test_single_sound_replace_preserves_all_other_data_and_restores_exactly(self):
        self.change();index=WadIndex(self.path)
        self.assertEqual(index.read('Sounds/player_hurt.wav'),wav(300));self.assertEqual(index.read('Sounds/other.wav'),self.second)
        self.assertEqual(index.read('config.xml'),b'keep me exactly')
        self.assertEqual((self.store.folder(self.path)/'original.wad').read_bytes(),self.baseline)
        self.change(restore=True);self.assertEqual(self.path.read_bytes(),self.baseline)
    def test_two_sounds_restore_individually_and_reapply(self):
        self.change();self.change('Sounds/other.wav',wav(400));self.change(restore=True)
        self.assertEqual(WadIndex(self.path).read('Sounds/player_hurt.wav'),self.first)
        self.assertEqual(WadIndex(self.path).read('Sounds/other.wav'),wav(400))
        self.change('Sounds/other.wav',restore=True);self.assertEqual(self.path.read_bytes(),self.baseline)
        self.change();self.assertEqual((self.store.folder(self.path)/'original.wad').read_bytes(),self.baseline)
    def test_stale_preview_and_external_update_are_not_overwritten(self):
        with self.assertRaises(SoundError):self.store.replace(self.path.name,'Sounds/player_hurt.wav',wav(),'0'*64)
        self.change();self.path.write_bytes(self.path.read_bytes()+b'external patch')
        changed=self.path.read_bytes()
        with self.assertRaises(SoundError):self.change(restore=True)
        self.assertEqual(self.path.read_bytes(),changed)
    def test_game_running_initial_and_started_during_job(self):
        def deny():raise SoundError('game running')
        self.store.guard=deny
        with self.assertRaises(SoundError):self.change()
        self.assertEqual(self.path.read_bytes(),self.baseline)
        calls=[]
        def start_midway():
            calls.append(1)
            if len(calls)>1:raise SoundError('started while copying')
        self.store.guard=start_midway
        with self.assertRaises(SoundError):self.change()
        self.assertEqual(self.path.read_bytes(),self.baseline)
    def test_backup_corruption_stops_restore(self):
        self.change();before=self.path.read_bytes();(self.store.folder(self.path)/'original.wad').write_bytes(b'broken')
        with self.assertRaises(SoundError):self.change(restore=True)
        self.assertEqual(self.path.read_bytes(),before)
    def test_failed_atomic_replace_leaves_original_and_recoverable_journal(self):
        import sound_files
        real=sound_files.os.replace
        def fail(src,dst):
            if Path(dst)==self.path:raise OSError('in use')
            return real(src,dst)
        with patch('sound_files.os.replace',side_effect=fail):
            with self.assertRaises(OSError):self.change()
        self.assertEqual(self.path.read_bytes(),self.baseline)
        self.assertIn('pending',json.loads((self.store.folder(self.path)/'journal.json').read_text()))
        self.assertNotIn('pending',self.store.state(self.path,True))
        self.change();self.change(restore=True);self.assertEqual(self.path.read_bytes(),self.baseline)
    def test_crash_after_replace_recovers_committed_state(self):
        import sound_files
        real=sound_files.json_save;calls=[]
        def fail_last(path,value):
            calls.append(1)
            if len(calls)==3:raise OSError('power loss after replace')
            real(path,value)
        with patch('sound_files.json_save',side_effect=fail_last):
            with self.assertRaises(OSError):self.change()
        recovered=self.store.state(self.path,True)
        self.assertIn('Sounds/player_hurt.wav',recovered['changes'])
        self.change(restore=True);self.assertEqual(self.path.read_bytes(),self.baseline)
    def test_paths_and_non_sound_files_cannot_be_changed(self):
        for path in ['../Sound.wad','C:\\x.wad','a/b.wad','a\\b.wad']:
            with self.assertRaises(SoundError):self.store.path(path)
        with self.assertRaises(SoundError):self.store.replace(self.path.name,'config.xml',wav(),'x'*64)
        with self.assertRaises(SoundError):self.store.configure(str(self.root))
    def test_unknown_crc_refuses_modification(self):
        data=bytearray(self.baseline);entry=WadIndex(self.path).entries['Sounds/player_hurt.wav'];data[entry['offset']]^=1;self.path.write_bytes(data)
        with self.assertRaises(SoundError):self.change()
        self.assertEqual(self.path.read_bytes(),data)
    def test_both_user_sound_variants_are_valid(self):
        root=Path(__file__).parents[1]
        for ext in ('.wav','.ogg'):
            data=(root/'dist'/'assets'/'sounds'/('damage'+ext)).read_bytes();info=audio_info(data,ext)
            self.assertEqual(info['channels'],1);self.assertAlmostEqual(info['duration'],3.38,places=1)
    def test_malformed_audio_and_opus_rejected(self):
        for data,ext in [(b'RIFF'+b'\0'*50,'.wav'),(b'OggS'+b'\0'*50,'.ogg'),(wav(),'.mp3'),(wav(frames=22050*16),'.wav')]:
            with self.assertRaises(SoundError):audio_info(data,ext)
    def test_archive_validation(self):
        for bad in [b'not a wad',b'KIWAD'+struct.pack('<ll',999,0),b'KIWAD'+struct.pack('<ll',1,999999)]:
            self.path.write_bytes(bad)
            with self.assertRaises(SoundError):WadIndex(self.path)
    def test_uncompressed_version_one(self):
        wad(self.path,{'Sounds/player_hurt.wav':self.first},version=1,compressed=False);self.baseline=self.path.read_bytes()
        self.change();self.change(restore=True);self.assertEqual(self.path.read_bytes(),self.baseline)

class SoundJobTests(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(sys.platform=='win32','Native Windows folder dialog')
    async def test_native_folder_dialog_opens_and_cooperatively_closes(self):
        import threading
        from sound_picker import choose_folder
        class Cancel:
            calls=0
            def is_set(self):self.calls+=1;return True
        signal=Cancel();result=[];errors=[]
        def work():
            try:result.append(choose_folder(cancel=signal))
            except Exception as exc:errors.append(exc)
        worker=threading.Thread(target=work,daemon=True);worker.start()
        await asyncio.to_thread(worker.join,8)
        self.assertFalse(worker.is_alive(),'Folder dialog did not respond to cancellation')
        self.assertEqual(errors,[]);self.assertEqual(result,[None]);self.assertGreater(signal.calls,0)

    async def test_folder_picker_is_a_nonblocking_job_and_cancellation_preserves_configuration(self):
        import threading
        with tempfile.TemporaryDirectory() as tmp:
            game=Path(tmp).resolve()/'game';(game/'Bin').mkdir(parents=True);(game/'Bin'/'WizardGraphicalClient.exe').write_bytes(b'fixture')
            (game/'Data'/'GameData').mkdir(parents=True);wad(game/'Data'/'GameData'/'Sound.wad',{'hurt.wav':wav()})
            entered=threading.Event();release=threading.Event()
            def pick(initial,owner,cancel):entered.set();release.wait(2);return str(game/'Bin')
            service=Sounds(SimpleNamespace(demo=False,launcher=None),Path(tmp)/'user',lambda:None,picker=pick)
            response=await service.dispatch('sound_choose_folder',{})
            self.assertTrue(response['started']);await asyncio.to_thread(entered.wait,1)
            self.assertTrue((await service.dispatch('sound_status',{}))['running'])
            release.set();await service.job
            status=await service.dispatch('sound_status',{})
            self.assertEqual(status['kind'],'folder');self.assertEqual(status['result']['installation'],str(game))
            self.assertEqual(status['result']['archives'][0]['id'],'Sound.wad')
            self.assertFalse((service.store.root/'backups').exists())
            service.picker=lambda *args:None
            await service.dispatch('sound_choose_folder',{});await service.job
            self.assertTrue(service.status['result']['cancelled']);self.assertEqual(service.store.game,game)
            await service.close()

    async def test_search_job_does_not_require_game_closed_and_reports_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            def deny():raise SoundError('Game is open')
            service=Sounds(SimpleNamespace(demo=False,launcher=None),tmp,deny)
            service.store.search=lambda query,progress:{'files':[],'total':0,'archives':3,'query':query}
            response=await service.dispatch('sound_search',{'query':'hurt'})
            self.assertTrue(response['started']);await service.close()
            status=await service.dispatch('sound_status',{})
            self.assertFalse(status['running']);self.assertEqual(status['kind'],'search')
            self.assertEqual(status['result']['query'],'hurt')
    @unittest.skipUnless(sys.platform=='win32','Windows process enumeration')
    async def test_native_process_enumeration_on_windows(self):
        require_game_closed()

    async def test_job_returns_immediately_blocks_concurrent_writes_and_drains(self):
        import threading
        with tempfile.TemporaryDirectory() as tmp:
            bridge=SimpleNamespace(demo=False,launcher=None);service=Sounds(bridge,tmp,lambda:None)
            started=threading.Event();finish=threading.Event()
            def work(*args):started.set();finish.wait(2);return {'name':'hurt.wav'}
            service.store.replace=work
            result=await service.dispatch('sound_apply',{'archive':'Sound.wad','name':'hurt.wav','data':base64.b64encode(wav()).decode(),'expected':'a'*64})
            self.assertTrue(result['started']);await asyncio.to_thread(started.wait,1)
            self.assertTrue((await service.dispatch('sound_status',{}))['running'])
            with self.assertRaises(SoundError):await service.dispatch('sound_config',{'path':tmp})
            finish.set();await service.close();self.assertFalse((await service.dispatch('sound_status',{}))['running'])
    async def test_demo_and_large_upload_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=Sounds(SimpleNamespace(demo=True,launcher=None),tmp,lambda:None)
            with self.assertRaises(SoundError):await service.dispatch('sound_config',{})
            service.bridge.demo=False
            with self.assertRaises(SoundError):await service.dispatch('sound_apply',{'data':'x'*(4*1024*1024+20)})
            service.bridge.shutting_down=True
            with self.assertRaises(SoundError):await service.dispatch('sound_config',{})
            service.bridge.shutting_down=False
            service.bridge.launcher=SimpleNamespace(progress={'running':True})
            with self.assertRaises(SoundError):await service.dispatch('sound_apply',{})

if __name__=='__main__':unittest.main()
