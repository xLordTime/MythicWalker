"""Run the complete, pinned FishBot-DE core through the shared bridge session.
Upstream logic is vendored unchanged; this layer owns configuration and cleanup.
"""
import asyncio
import math
import re
import sys
import time
from diagnostics import logger

SCHOOLS={'Any','Fire','Ice','Storm','Myth','Life','Death','Balance','Sun','Moon','Star','Shadow','Astral'}
CONFIG={
 'chests':('IS_CHEST',False),'school':('SCHOOL','Any'),'rank':('RANK',2),
 'fish_id':('ID',0),'size_min':('SIZE_MIN',0),'size_max':('SIZE_MAX',999),
 'skip_popup':('SKIP_CAUGHT_FISH_POPUP',True),'speed_enabled':('SPEEDHACK_ENABLED',False),
 'speed':('SPEEDHACK_SPEED',1.0),'require_all_patches':('REQUIRE_ALL_PATCHES',True),
 'poll_interval':('SLEEP_POLL_INTERVAL',.005),'after_click':('SLEEP_AFTER_CLICK',.01),
 'retry_delay':('SLEEP_RETRY_DELAY',.01),'window_wait':('SLEEP_WINDOW_WAIT',.02),
 'game_state_wait':('SLEEP_GAME_STATE',.05),
}

def options(value):
    if not isinstance(value,dict):raise ValueError('Angel-Einstellungen fehlen.')
    result={key:default for key,(_,default) in CONFIG.items()}
    result.update(max_catches=0,minutes=0)
    if set(value)-set(result):raise ValueError('Unbekannte Angel-Einstellung. Weboberfläche neu laden.')
    result.update(value)
    for name in ('chests','skip_popup','speed_enabled','require_all_patches'):
        if type(result[name]) is not bool:raise ValueError(name+' muss boolesch sein.')
    if not isinstance(result['school'],str) or result['school'] not in SCHOOLS:raise ValueError('Unbekannte Fischschule.')
    for name,lo,hi in [('rank',0,20),('fish_id',0,2147483647),('max_catches',0,10000),('minutes',0,1440)]:
        n=result[name]
        if type(n) is not int or not lo<=n<=hi:raise ValueError(name+': ungültiger Wert.')
    for name,lo,hi in [('size_min',0,9999),('size_max',0,9999),('speed',.1,10)]+[(k,.001,10) for k in ('poll_interval','after_click','retry_delay','window_wait','game_state_wait')]:
        n=result[name]
        if type(n) not in (int,float) or not math.isfinite(n) or not lo<=n<=hi:raise ValueError(name+': ungültiger Wert.')
    if result['size_min']>result['size_max']:raise ValueError('Minimalgröße größer als Maximalgröße.')
    return result

class PatchJournal:
    """Capture originals before any write, retain failed entries for retry."""
    def __init__(self,reader,flush=None):self.reader=reader;self.entries=[];self.flush=flush or (lambda a,n:None)
    async def write(self,address,value):
        entry=next((e for e in self.entries if e[1]==address),None)
        if entry:
            if len(entry[2])!=len(value):raise RuntimeError('Patch-Länge während des Laufes verändert.')
        else:
            if any(address<a+len(b) and a<address+len(value) for _,a,b in self.entries):raise RuntimeError('Überlappende Angel-Patches.')
            original=await self.reader.read_bytes(address,len(value))
            if len(original)!=len(value):raise RuntimeError('Unvollständige Originalbytes.')
            self.entries.append((hex(address),address,original))
            logger.info('fishing.patch.backup address=%#x original=%s',address,original.hex())
        await self.reader.write_bytes(address,value)
        self.flush(address,len(value))
        if await self.reader.read_bytes(address,len(value))!=value:raise RuntimeError(f'Patch-Schreibprüfung fehlgeschlagen: {address:#x}')
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
                logger.info('fishing.patch.restored address=%#x verified=true',address)
            except Exception as exc:
                logger.exception('fishing.patch.restore_failed address=%#x',address);errors.append(name+': '+str(exc))
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

class CoreSession:
    """Temporarily bind an unchanged upstream module to one bridge client."""
    def __init__(self,core,client,on_log):
        self.core=core;self.client=client;self.original={name:getattr(core,name) for name in ('MemoryReader','patch','reset_patch','Speedhack','logger')}
        self.old_print=core.__dict__.get('print');self.code_writes=False;self.speeds=[]
        self.journal=PatchJournal(self.original['MemoryReader'](client._pymem),native_flush(client))
        session=self
        class Reader:
            def __init__(self,pymem):self.reader=session.original['MemoryReader'](pymem)
            def __getattr__(self,name):return getattr(self.reader,name)
            async def write_bytes(self,address,value):
                if session.code_writes:return await session.journal.write(address,value)
                return await self.reader.write_bytes(address,value)
        async def apply(client):
            session.code_writes=True
            try:return await session.original['patch'](client)
            finally:session.code_writes=False
        async def reset(client,address_bytes):
            try:await session.journal.restore()
            finally:
                core._cleanup_state['address_bytes']=[(a,b) for _,a,b in session.journal.entries]
                core._cleanup_state['patches_applied']=bool(session.journal.entries)
        class Log:
            def __getattr__(self,level):
                def emit(message,*args,**kwargs):
                    text=str(message)
                    getattr(logger,level if level in ('debug','info','warning','error','exception') else 'info')('fishbot.de %s',text)
                    on_log(text,level)
                return emit
        class Speed(self.original['Speedhack']):
            def __init__(self,client):
                super().__init__(client);self.saved={};session.speeds.append(self)
            def _get_process(self):
                raw=super()._get_process();owner=self
                class Process:
                    def __getattr__(self,name):return getattr(raw,name)
                    def write_memory(self,address,value):
                        targets=[owner._gettickcount_addr,owner._gettickcount64_addr,owner._qpc_addr,owner._timegettime_addr]
                        if address in targets and address not in owner.saved:
                            owner.saved[address]=raw.read_memory(address,len(value))
                        return raw.write_memory(address,value)
                return Process()
            def detach(self):
                raw=super()._get_process();errors=[]
                for address,original in list(self.saved.items()):
                    try:
                        self._make_writable(address,len(original));raw.write_memory(address,original);self._flush_cache(address,len(original))
                        if raw.read_memory(address,len(original))!=original:raise RuntimeError('Speedhack-Originalbytes stimmen nicht überein')
                        del self.saved[address]
                    except Exception as exc:errors.append(str(exc))
                if errors:raise RuntimeError('; '.join(errors))
                self._attached=False;self._current_speed=1.0
            def cleanup(self):
                if self.saved:raise RuntimeError('Speedhack-Hooks sind noch aktiv; Speicher bleibt erhalten.')
                return super().cleanup()
        core.MemoryReader=Reader;core.patch=apply;core.reset_patch=reset;core.Speedhack=Speed;core.logger=Log();core.print=lambda *args,**kwargs:core.logger.info(' '.join(map(str,args)))
    async def restore(self):
        errors=[]
        for speed in self.speeds:
            try:speed.detach();speed.cleanup()
            except Exception as exc:errors.append('Speedhack: '+str(exc))
        try:await self.journal.restore()
        except Exception as exc:errors.append(str(exc))
        if errors:raise RuntimeError('; '.join(errors))
    def release(self):
        for name,value in self.original.items():setattr(self.core,name,value)
        if self.old_print is None:self.core.__dict__.pop('print',None)
        else:self.core.print=self.old_print
        self.core.clear_external_client()

class Fishing:
    def __init__(self,bridge):
        self.bridge=bridge;self.task=None;self.core=None;self.stop_requested=False;self.stop_lock=asyncio.Lock()
        self.data={'running':False,'phase':'Bereit','catches':0,'error':None,'restored':True,'client':None}
    @property
    def running(self):return bool(self.task and not self.task.done())
    async def publish(self):await self.bridge.send({'type':'fishing','fishing':dict(self.data)})
    def on_log(self,text,level):
        match=re.search(r'total catches=(\d+)',text)
        if match:
            self.data['catches']=int(match[1]);self.data['phase']='Fang abgeschlossen'
            if getattr(self,'config',{}).get('max_catches') and self.data['catches']>=self.config['max_catches']:
                self.core.request_shutdown()
        for fragment,phase in [('Preparing','Alle Angel-Patches vorbereiten'),('Ready for Fish','Bereit zum Angeln'),('opening the fishing window to refresh','Teich erneuern'),('Icon1 click sent','Warten auf Biss'),('Sending SPACEBAR','Fisch einholen'),('Basket cleanup requested','Fischkorb leeren'),('Unhooking patches','Originalbytes wiederherstellen')]:
            if fragment in text:self.data['phase']=phase
        if level in ('error','exception'):self.data['error']=text
    async def start(self,ids,config):
        config=options(config)
        if self.bridge.demo:raise ValueError('Angeln benötigt die Live-Bridge und Wizard101 DE.')
        if self.running:raise ValueError('Der Fisch-Bot läuft bereits.')
        if getattr(self.bridge,'raids',None) and self.bridge.raids.running:raise ValueError('Raid-Aktion zuerst stoppen.')
        if not isinstance(ids,list) or len(ids)!=1:raise ValueError('Genau einen Angel-Client auswählen.')
        if self.bridge.script_task and not self.bridge.script_task.done():raise ValueError('Skript zuerst stoppen.')
        if any(self.bridge.automations.state().values()):raise ValueError('Andere Automatiken zuerst stoppen.')
        client=self.bridge.adapter.selected(ids)[0]
        if ids[0] in self.bridge.adapter.freecam:raise ValueError('Freecam vor dem Angeln beenden.')
        from vendor import fishbot_de
        self.core=fishbot_de
        for key,(name,_) in CONFIG.items():setattr(self.core,name,config[key])
        self.stop_requested=False;self.config=config
        self.data={'running':True,'phase':'Original-FishBot starten','catches':0,'error':None,'restored':False,'client':ids[0]}
        self.task=asyncio.create_task(self.run(client,config))
        return dict(self.data)
    async def stop(self):
        async with self.stop_lock:
            self.stop_requested=True
            if self.core:self.core.request_shutdown()
            if self.running:await asyncio.shield(self.task)
            if not self.data['restored']:raise RuntimeError(self.data['error'] or 'Angel-Aufräumen fehlgeschlagen.')
            return dict(self.data)
    async def run(self,client,config):
        session=None;monitor=None;started=time.monotonic()
        async def watch():
            previous=None
            while True:
                if self.stop_requested or config['minutes'] and time.monotonic()-started>=config['minutes']*60 or config['max_catches'] and self.data['catches']>=config['max_catches']:
                    self.core.request_shutdown()
                current=tuple(self.data.items())
                if current!=previous:
                    await self.publish();previous=current
                await asyncio.sleep(.1)
        try:
            session=CoreSession(self.core,client,self.on_log)
            self.bridge.adapter.fishing_patches[str(client.process_id)]=session
            self.core.set_external_client(self.bridge.adapter.handler,client)
            if self.stop_requested:return
            monitor=asyncio.create_task(watch())
            await self.core.main()
        except Exception as exc:
            logger.exception('fishing.original.failed');self.data['error']=str(exc)
            await self.bridge.log('Angeln: '+str(exc),'error')
        finally:
            if monitor:
                monitor.cancel()
                try:await monitor
                except asyncio.CancelledError:pass
            try:
                if session:await session.restore()
                self.bridge.adapter.fishing_patches.pop(str(client.process_id),None)
                self.data['restored']=True
            except Exception as exc:
                self.data['error']=str(exc);self.data['restored']=False;self.bridge.cleanup_error=str(exc)
                logger.exception('fishing.original.cleanup_failed');await self.bridge.log(str(exc),'error')
            finally:
                if session:session.release()
                self.data['running']=False;self.data['phase']='Fehler · Protokoll prüfen' if self.data['error'] else 'Gestoppt · Originalbytes wiederhergestellt'
                await self.publish()
