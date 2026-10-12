"""Single-client, cancellable raid actions from Lxghtend's GPL-3.0 tools."""
import asyncio
import contextlib
from diagnostics import logger
from fishing import PatchJournal, native_flush
from raid_catalog import CATALOG


def native_modules():
    # Explicit imports also make all headless modules visible to PyInstaller.
    from vendor.raids import ds, az, pl, lm, ms
    return dict(ds=ds, az=az, pl=pl, lm=lm, ms=ms)


class ClientProxy:
    """Never cancel key-up or a teleport while WizWalker is changing memory."""
    def __init__(self, client): self.client = client
    def __getattr__(self, name): return getattr(self.client, name)
    async def complete(self, method, *args, **kwargs):
        task = asyncio.create_task(getattr(self.client, method)(*args, **kwargs))
        try: return await asyncio.shield(task)
        except asyncio.CancelledError:
            await task
            raise
    async def send_key(self, *args, **kwargs): return await self.complete('send_key', *args, **kwargs)
    async def teleport(self, *args, **kwargs): return await self.complete('teleport', *args, **kwargs)


class RaidSession:
    def __init__(self, module, client, emit):
        self.module = module
        self.old_print = module.__dict__.get('print')
        self.old_reader = module.__dict__.get('MemoryReader')
        self.journal = None
        module.print = lambda *args, **kwargs: emit(' '.join(map(str, args)))
        if self.old_reader:
            self.journal = PatchJournal(self.old_reader(client._pymem), native_flush(client))
            journal = self.journal
            class Reader:
                def __init__(self, pymem): pass
                async def pattern_scan(self, pattern, **kwargs):
                    matches = await journal.reader.pattern_scan(pattern, return_multiple=True)
                    if not isinstance(matches, list) or len(matches) != 1:
                        raise RuntimeError('Raid-Angelpattern nicht eindeutig gefunden. Keine Ersatzadresse verwendet.')
                    return matches[0]
                async def read_bytes(self, address, size): return await journal.reader.read_bytes(address, size)
                async def write_bytes(self, address, value):
                    task = asyncio.create_task(journal.write(address, value))
                    try: return await asyncio.shield(task)
                    except asyncio.CancelledError:
                        await task
                        raise
            module.MemoryReader = Reader
    async def restore(self):
        if self.journal: await self.journal.restore()
    def release(self):
        if self.old_reader: self.module.MemoryReader = self.old_reader
        if self.old_print is None: self.module.__dict__.pop('print', None)
        else: self.module.print = self.old_print


class Raids:
    def __init__(self, bridge):
        self.bridge = bridge
        self.task = None
        self.stop_lock = asyncio.Lock()
        self.stop_requested = False
        self.data = dict(running=False, client=None, raid=None, action=None, phase='Bereit', error=None, restored=True, wisps=[])
    @property
    def running(self): return bool(self.task and not self.task.done())
    async def publish(self): await self.bridge.send({'type':'raid', 'raid':dict(self.data)})
    def emit(self, text):
        logger.info('raid.upstream %s', text)
        self.data['phase'] = text[-500:]
        if any(part in text for part in ('did not find', 'No fish found', 'not in freecam')):
            raise ValueError(text)
    async def start(self, ids, raid, action, target=None):
        if self.bridge.demo: raise ValueError('Raid-Tools benötigen eine Live-Bridge.')
        if self.running: raise ValueError('Laufende Raid-Aktion zuerst stoppen.')
        if self.bridge.fishing.running: raise ValueError('Fisch-Bot zuerst stoppen.')
        if self.bridge.script_task and not self.bridge.script_task.done(): raise ValueError('Skript zuerst stoppen.')
        if any(self.bridge.automations.state().values()): raise ValueError('Automatiken zuerst stoppen.')
        if not isinstance(ids, list) or len(ids) != 1: raise ValueError('Genau einen Raid-Account auswählen.')
        selected = next((r for r in CATALOG if r['id'] == raid), None)
        spec = next((a for a in selected['actions'] if a['id'] == action), None) if selected else None
        if raid == 'ms' and action == 'wisp_target':
            if type(target) is not str or not target.isdecimal(): raise ValueError('Ungültiges Wisp-Ziel.')
            spec = dict(method='wisp_target', args=[], kwargs={}, label='Wisp Teleport')
        if not spec: raise ValueError('Unbekannte Raid-Aktion.')
        client = self.bridge.adapter.selected(ids)[0]
        if await client.is_loading() or await client.in_battle(): raise ValueError('Raid-Aktion erst außerhalb von Ladebildschirm und Kampf starten.')
        self.stop_requested = False
        self.data = dict(running=True, client=ids[0], raid=raid, action=action, phase=spec['label'], error=None, restored=True, wisps=[])
        self.task = asyncio.create_task(self.run(client, raid, spec, target))
        return dict(self.data)
    async def stop(self):
        async with self.stop_lock:
            self.stop_requested = True
            if self.running:
                # Let a newly created task enter its cleanup scope before cancellation.
                await asyncio.sleep(0)
            if self.running:
                self.task.cancel()
                await asyncio.shield(self.task)
            if not self.data['restored']: raise RuntimeError(self.data['error'] or 'Raid-Patches konnten nicht wiederhergestellt werden.')
            return dict(self.data)
    async def run(self, client, raid, spec, target):
        session = None
        monitor = None
        stopped = False
        pid = str(client.process_id)
        async def watch():
            previous = None
            while True:
                status = (self.data['phase'], self.data['restored'])
                if previous != status:
                    await self.publish()
                    previous = status
                await asyncio.sleep(.2)
        try:
            module = native_modules()[raid]
            session = RaidSession(module, client, self.emit)
            util = module.Utils(ClientProxy(client))
            monitor = asyncio.create_task(watch())
            method = spec['method']
            async with asyncio.timeout(900 if method in {'auto_raid_drums','catch_all_fish'} else 120):
                if method in {'catch_fish','catch_all_fish'}:
                    self.bridge.adapter.fishing_patches[pid] = session
                    self.data['restored'] = False
                    await util.patch_fish(client)
                if method == 'list_wisps':
                    entities = await client.get_base_entities_with_name('Raid_MS_Shadow_Wisp_01')
                    self.data['wisps'] = []
                    for i, entity in enumerate(entities[:100]):
                        pos = await entity.location()
                        self.data['wisps'].append(dict(id=str(await entity.global_id_full()), label=f'Wisp {i+1}', x=pos.x, y=pos.y, z=pos.z))
                    self.data['phase'] = f'{len(self.data["wisps"])} Wisps gefunden'
                elif method == 'wisp_target':
                    entities = await client.get_base_entities_with_name('Raid_MS_Shadow_Wisp_01')
                    entity = None
                    for candidate in entities:
                        if str(await candidate.global_id_full()) == target: entity = candidate; break
                    if entity is None: raise ValueError('Wisp nicht mehr vorhanden. Liste aktualisieren.')
                    await util.wisp_teleport(entity)
                else:
                    result = await getattr(util, method)(*spec['args'], **spec['kwargs'])
                    if method == 'read_tokens': self.data['phase'] = '\n'.join(f'{name}: {pos} · {animation}' for name,pos,animation in (result or [])) or 'Keine versteckten Tokens gefunden.'
            if not self.stop_requested:await self.bridge.log('Raid: '+spec['label']+' abgeschlossen.')
        except asyncio.CancelledError:
            stopped = True
        except TimeoutError:
            self.data['error'] = 'Raid-Aktion: Zeitlimit erreicht. Zustand im Spiel prüfen.'
            await self.bridge.log(self.data['error'], 'error')
        except Exception as exc:
            self.data['error'] = str(exc)
            logger.exception('raid.failed')
            await self.bridge.log('Raid: '+str(exc), 'error')
        finally:
            if monitor:
                monitor.cancel()
                with contextlib.suppress(asyncio.CancelledError): await monitor
            try:
                if session: await session.restore()
                self.bridge.adapter.fishing_patches.pop(pid, None)
                self.data['restored'] = True
            except Exception as exc:
                self.data['error'] = str(exc)
                self.data['restored'] = False
                self.bridge.cleanup_error = str(exc)
                await self.bridge.log('Raid-Aufräumen: '+str(exc), 'error')
            finally:
                if session: session.release()
                self.data['running'] = False
                if self.data['error']: self.data['phase'] = 'Fehler · '+self.data['error']
                elif stopped or self.stop_requested: self.data['phase'] = 'Gestoppt · Originalbytes wiederhergestellt'
                await self.publish()
