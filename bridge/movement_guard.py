"""Keep WizWalker's collision bypass scoped to one teleport, not the hook lifetime."""
import asyncio
from diagnostics import event
from fishing import native_flush

class MovementGuard:
    def __init__(self, client, hook):
        self.client=client;self.hook=hook;self.lock=asyncio.Lock()
        self.original_teleport=client.teleport
        self.entries=list(zip(hook._collision_je_addrs,hook._old_collision_jes_bytes))
        if len(self.entries)!=2 or any(len(value)!=2 for _,value in self.entries):
            raise RuntimeError('Movement-Hook: Originalbytes fehlen; Hook wird abgebrochen.')
        self.flush=native_flush(client)
    async def write(self,address,value):
        await self.client.hook_handler.write_bytes(address,value)
        self.flush(address,len(value))
        if await self.client.hook_handler.read_bytes(address,len(value))!=value:
            raise RuntimeError('Movement-Hook: Schreibprüfung fehlgeschlagen.')
    async def restore(self):
        # Never leave the second patch modified when restoring the first fails.
        errors=[]
        for address,original in self.entries:
            try:await self.write(address,original)
            except Exception as exc:errors.append(str(exc))
        if errors:raise RuntimeError('Movement-Aufräumen: '+'; '.join(errors))
    async def install(self):
        await self.restore()
        self.client.teleport=self.teleport
        event('movement.guard.installed',pid=self.client.process_id,collision_bypass=False)
    async def teleport(self,*args,**kwargs):
        async with self.lock:
            async def operation():
                try:
                    for address,_ in self.entries:await self.write(address,b'\x90\x90')
                    return await self.original_teleport(*args,**kwargs)
                finally:
                    if self.client.is_running():await self.restore()
            task=asyncio.create_task(operation())
            try:return await asyncio.shield(task)
            except asyncio.CancelledError:
                await task
                raise
    def release(self):self.client.teleport=self.original_teleport

async def install_movement_guard(client):
    # A native Client always has this handler. Portable adapter test doubles do not.
    if not hasattr(client,'hook_handler'):return None
    hook=next((h for kind,h in client.hook_handler._active_hooks.items() if kind.__name__=='MovementTeleportHook'),None)
    if hook is None:raise RuntimeError('Movement-Teleport-Hook fehlt nach Aktivierung.')
    guard=MovementGuard(client,hook)
    await guard.install()
    return guard
