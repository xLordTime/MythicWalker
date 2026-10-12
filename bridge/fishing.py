"""FishBot-DE adapter, based on xLordTime/Fisch-Bot-DE c29dc5e18375.
Uses the bridge's existing clients. No timer DLL hooks or modal/UI byte patches.
"""
import asyncio
import math
import sys
from diagnostics import logger

SCHOOLS={'Any','Fire','Ice','Storm','Myth','Life','Death','Balance','Sun','Moon','Star','Shadow','Astral'}
# Only the six fishing distance/angle checks from the upstream patch set.
# Animation skips affect broader game lifecycles and are deliberately excluded.
DISTANCE_PATCHES=[
 ('fish_distance_check',rb'\x0F\x84....\xF3\x0F\x10\x70\x6C\x0F\x28\xC6'),
 ('fish_fov_check',rb'\x0F\x84....\x48\x8B\x8B....\x45\x32'),
 ('fish_distance_threshold',rb'\x0F\x86....\x44\x0F\x2F\x05'),
 ('fish_min_distance',rb'\x0F\x86....\xF3\x41\x0F\x5C\xF2'),
 ('fish_final_angle_max',rb'\x0F\x82....\xF3\x44\x0F\x10\x0D....\x41\x0F\x2F\xC1'),
 ('fish_final_angle_min',rb'\x0F\x82....\xC7\x83........\x8B\x93'),
]

def options(value):
    if not isinstance(value,dict):raise ValueError('Angel-Einstellungen fehlen.')
    result={'chests':False,'school':'Any','rank':0,'fish_id':0,'size_min':0,'size_max':9999,'distance_patch':False,'max_catches':0,'minutes':30}
    if set(value)-set(result):raise ValueError('Unbekannte Angel-Einstellung.')
    result.update(value)
    for name in ('chests','distance_patch'):
        if type(result[name]) is not bool:raise ValueError(name+' muss boolesch sein.')
    if result['school'] not in SCHOOLS:raise ValueError('Unbekannte Fischschule.')
    for name,lo,hi in [('rank',0,20),('fish_id',0,2147483647),('max_catches',0,10000),('minutes',1,60)]:
        n=result[name]
        if type(n) is not int or not lo<=n<=hi:raise ValueError(name+': ungültiger Wert.')
    for name in ('size_min','size_max'):
        n=result[name]
        if type(n) not in (int,float) or not math.isfinite(n) or not 0<=n<=9999:raise ValueError('Ungültige Fischgröße.')
    if result['size_min']>result['size_max']:raise ValueError('Minimalgröße größer als Maximalgröße.')
    return result

class PatchJournal:
    """Retain ownership until every original byte is read back successfully."""
    def __init__(self,reader,flush=None):self.reader=reader;self.entries=[];self.flush=flush or (lambda address,size:None)
    async def apply_distance(self):
        # Resolve ALL signatures before modifying any bytes, abort on ambiguity.
        addresses=[]
        for name,pattern in DISTANCE_PATCHES:
            matches=await self.reader.pattern_scan(pattern,module='WizardGraphicalClient.exe',return_multiple=True)
            if len(matches)!=1:raise RuntimeError(f'{name}: {len(matches)} Treffer; keine Angel-Patches angewendet.')
            address=matches[0]
            if any(abs(address-other)<6 for _,other in addresses):raise RuntimeError('Überlappende Angel-Patterns.')
            addresses.append((name,address))
        # Capture the full original set before the first write.
        originals=[(name,address,await self.reader.read_bytes(address,6)) for name,address in addresses]
        for name,address,original in originals:
            if original[:2] not in (b'\x0f\x84',b'\x0f\x86',b'\x0f\x82'):raise RuntimeError(name+': Originalcode unerwartet.')
        for name,address,original in originals:
            self.entries.append((name,address,original))
            await self.reader.write_bytes(address,b'\x90'*6)
            self.flush(address,6)
            if await self.reader.read_bytes(address,6)!=b'\x90'*6:raise RuntimeError(name+': Patch-Prüfung fehlgeschlagen.')
            logger.info('fishing.patch.apply name=%s address=%#x original=%s',name,address,original.hex())
    async def restore(self):
        errors=[]
        for entry in list(reversed(self.entries)):
            name,address,original=entry
            try:
                async with asyncio.timeout(5):
                    await self.reader.write_bytes(address,original)
                    self.flush(address,len(original))
                    if await self.reader.read_bytes(address,len(original))!=original:raise RuntimeError('Originalbytes stimmen nicht überein')
                self.entries.remove(entry)
                logger.info('fishing.patch.restored name=%s address=%#x verified=true',name,address)
            except Exception as exc:
                logger.exception('fishing.patch.restore_failed name=%s address=%#x',name,address)
                errors.append(name+': '+str(exc))
        if errors:raise RuntimeError('Angel-Patches nicht vollständig wiederhergestellt: '+'; '.join(errors))

def native_flush(client):
    def flush(address,size):
        if sys.platform!='win32':return
        import ctypes
        from ctypes import wintypes
        api=ctypes.WinDLL('kernel32',use_last_error=True).FlushInstructionCache
        api.argtypes=[wintypes.HANDLE,ctypes.c_void_p,ctypes.c_size_t];api.restype=wintypes.BOOL
        if not api(client._pymem.process_handle,address,size):raise ctypes.WinError(ctypes.get_last_error())
    return flush

class Fishing:
    def __init__(self,bridge):
        self.bridge=bridge;self.task=None;self.stop_lock=asyncio.Lock();self.data={'running':False,'phase':'Bereit','catches':0,'error':None,'restored':True,'client':None};self.client=None
    @property
    def running(self):return bool(self.task and not self.task.done())
    async def publish(self,phase=None):
        if phase:
            self.data['phase']=phase
            logger.info('fishing.phase phase=%s client=%s catches=%s',phase,self.data['client'],self.data['catches'])
        self.data['running']=self.running
        await self.bridge.send({'type':'fishing','fishing':dict(self.data)})
    async def start(self,ids,config):
        config=options(config)
        if self.bridge.demo:raise ValueError('Angeln benötigt die Live-Bridge und Wizard101 DE.')
        if self.running:raise ValueError('Der Fisch-Bot läuft bereits.')
        if not isinstance(ids,list) or len(ids)!=1:raise ValueError('Genau einen Angel-Client auswählen.')
        if self.bridge.script_task and not self.bridge.script_task.done():raise ValueError('Skript zuerst stoppen.')
        if any(self.bridge.automations.state().values()):raise ValueError('Andere Automatiken zuerst stoppen.')
        self.client=self.bridge.adapter.selected(ids)[0]
        if ids[0] in self.bridge.adapter.freecam:raise ValueError('Freecam vor dem Angeln beenden.')
        self.data={'running':True,'phase':'Vorbereiten','catches':0,'error':None,'restored':True,'client':ids[0]}
        self.task=asyncio.create_task(self.run(config))
        return dict(self.data)
    async def stop(self):
        async with self.stop_lock:
            if self.running:
                self.task.cancel()
                try:await self.task
                except asyncio.CancelledError:pass
            if not self.data['restored']:raise RuntimeError(self.data['error'] or 'Angel-Aufräumen fehlgeschlagen.')
            return dict(self.data)
    async def call(self,operation):
        # Complete mouse/key operations before cancellation so cursor hooks and
        # key-up are never abandoned halfway through an action.
        async def perform():
            async with self.bridge.lock:
                async with asyncio.timeout(12):return await operation()
        task=asyncio.create_task(perform())
        try:return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:await task
            except Exception:logger.exception('fishing.action.failed_during_stop')
            raise
    async def windows(self,name):
        async def read():
            return [w for w in await self.client.root_window.get_windows_with_name(name) if await w.is_visible()]
        return await self.call(read)
    async def click(self,name):
        async def click():
            async with self.client.mouse_handler:await self.client.mouse_handler.click_window_with_name(name)
        await self.call(click);await asyncio.sleep(.15)
    async def icon(self,name):
        async def click():
            windows=await self.client.root_window.get_windows_with_name('FishingWindow')
            visible=[w for w in windows if await w.is_visible()]
            if not visible:raise RuntimeError('Angelfenster ist geschlossen.')
            sub=await visible[0].get_child_by_name('FishingSubWindow')
            bottom=await sub.get_child_by_name('BottomFrame');button=await bottom.get_child_by_name(name)
            async with self.client.mouse_handler:await self.client.mouse_handler.click_window(button)
        await self.call(click)
    async def wait(self,check,seconds,message):
        try:
            async with asyncio.timeout(seconds):
                while not await check():await asyncio.sleep(.1)
        except TimeoutError:raise RuntimeError(message+': Zeitlimit erreicht.')
    async def prepare_pond(self,config,manager):
        from wizwalker.memory.memory_objects.fish import FishStatusCode
        async def filter_fish():
            kept=[]
            for fish in await manager.fish_list():
                template=await fish.template();size=await fish.size()
                accepted=(await fish.is_chest())==config['chests'] and config['size_min']<=size<=config['size_max']
                if config['school']!='Any':accepted=accepted and await template.school_name()==config['school']
                if config['rank']:accepted=accepted and await template.rank()==config['rank']
                if config['fish_id']:accepted=accepted and await fish.template_id()==config['fish_id']
                if await fish.status_code()==FishStatusCode.escaped:continue
                if accepted:kept.append(fish)
                else:await fish.write_status_code(FishStatusCode.escaped)
            return kept
        fish=await self.call(filter_fish)
        if not fish:
            await self.publish('Teich erneuern · Filter prüfen')
            await self.icon('Icon2');await asyncio.sleep(2)
            fish=await self.call(filter_fish)
            if not fish:raise RuntimeError('Keine passenden Fische nach Teicherneuerung. Filter oder Angelzauber prüfen.')
        return fish
    async def close_catch(self):
        client=self.client
        windows=await client.root_window.get_windows_with_name('CaughtFishModalWindow')
        visible=[w for w in windows if await w.is_visible()]
        if not visible:return
        caught=await visible[0].get_child_by_name('CaughtFish');button=await caught.get_child_by_name('exit')
        async with client.mouse_handler:await client.mouse_handler.click_window(button)
    async def run(self,config):
        client=self.client;journal=None;zone=None
        try:
            from wizwalker import Keycode
            from wizwalker.memory import MemoryReader
            from wizwalker.memory.memory_objects.fish import FishStatusCode
            async def initial():
                if await client.is_loading() or await client.in_battle():raise RuntimeError('Angeln nur außerhalb von Kampf und Ladebildschirm.')
                return await client.zone_name()
            zone=await self.call(initial)
            if config['distance_patch']:
                journal=PatchJournal(MemoryReader(client._pymem),native_flush(client))
                self.bridge.adapter.fishing_patches[str(client.process_id)]=journal
                self.data['restored']=False
                await self.publish('Angel-Patterns prüfen und sichern')
                await self.call(journal.apply_distance)
            manager=await self.call(client.game_client.fishing_manager)
            async with asyncio.timeout(config['minutes']*60):
                while not config['max_catches'] or self.data['catches']<config['max_catches']:
                    async def check_zone():
                        if await client.is_loading() or await client.zone_name()!=zone:raise RuntimeError('Zonenwechsel erkannt: Angeln wird gestoppt.')
                    await self.call(check_zone)
                    if not await self.windows('FishingWindow'):await self.click('OpenFishingButton')
                    await self.wait(lambda:self.windows('FishingWindow'),10,'Angelfenster')
                    await self.prepare_pond(config,manager)
                    await self.publish('Angel auswerfen');await self.icon('Icon1')
                    async def bite():
                        await self.call(check_zone)
                        if await self.windows('MessageBoxModalWindow'):raise RuntimeError('Spielmeldung: Fischkorb, Energie und Angelzauber prüfen. Keine Fische wurden gelöscht.')
                        async def read():
                            return any([await f.status_code()==FishStatusCode.unknown2 for f in await manager.fish_list()])
                        return await self.call(read)
                    await self.publish('Warten auf Biss');await self.wait(bite,90,'Biss')
                    await self.call(lambda:client.send_key(Keycode.SPACEBAR))
                    await self.publish('Fang bestätigen')
                    await self.wait(lambda:self.windows('CaughtFishModalWindow'),20,'Fangfenster')
                    await self.call(self.close_catch)
                    async def closed():return not await self.windows('CaughtFishModalWindow')
                    await self.wait(closed,10,'Fangfenster schließen')
                    self.data['catches']+=1;await self.publish('Fang abgeschlossen');await asyncio.sleep(.5)
        except asyncio.CancelledError:self.data['phase']='Gestoppt'
        except TimeoutError:
            self.data['error']='Zeitlimit beim Angeln erreicht. Angelzauber, Fangfenster und Energie prüfen.'
            await self.bridge.log(self.data['error'],'warning')
        except Exception as exc:
            self.data['error']=str(exc);logger.exception('fishing.failed')
            await self.bridge.log('Angeln: '+str(exc),'error')
        finally:
            self.data['phase']='Aufräumen'
            await self.publish()
            try:
                if journal:
                    await self.call(journal.restore)
                    self.bridge.adapter.fishing_patches.pop(str(client.process_id),None)
                self.data['restored']=True
                # Finish normal modal lifecycle and cancel any outstanding cast.
                if await self.windows('CaughtFishModalWindow'):await self.call(self.close_catch)
                if await self.windows('FishingWindow'):await self.click('CloseFishingButton')
            except Exception as exc:
                self.data['error']=str(exc);logger.exception('fishing.cleanup.failed')
                if journal and journal.entries:
                    self.data['restored']=False;self.bridge.cleanup_error=str(exc)
                await self.bridge.log('Angel-Aufräumen: '+str(exc),'error')
            self.data['running']=False
            self.data['phase']='Fehler' if self.data['error'] else 'Gestoppt · Änderungen wiederhergestellt'
            await self.bridge.send({'type':'fishing','fishing':dict(self.data)})
