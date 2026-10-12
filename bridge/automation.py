"""Session-scoped automation tasks, sharing the bridge's serialized memory access."""
import asyncio

MODES={'combat','dialogue','questing','sigil'}
class Automations:
    def __init__(self,bridge):self.bridge=bridge;self.tasks={};self.targets={}
    def state(self):return {k:bool(self.tasks.get(k) and not self.tasks[k].done()) for k in MODES}
    async def stop(self,mode=None):
        for name in list(self.tasks) if mode is None else [mode]:
            task=self.tasks.pop(name,None)
            if task and not task.done():
                task.cancel()
                try:await task
                except asyncio.CancelledError:pass
            self.targets.pop(name,None)
    async def toggle(self,mode,ids,enabled=None,from_script=False):
        if mode not in MODES:raise ValueError('Unbekannte Automatik.')
        if enabled is None:enabled=not self.state()[mode]
        if type(enabled) is not bool:raise ValueError('enabled muss boolesch sein.')
        await self.stop(mode)
        if enabled:
            if getattr(self.bridge,'raids',None) and self.bridge.raids.running:raise ValueError('Raid-Aktion zuerst stoppen.')
            if self.bridge.fishing.running:raise ValueError('Fisch-Bot zuerst stoppen.')
            self.bridge.adapter.selected(ids)
            if self.bridge.script_task and not self.bridge.script_task.done() and not (from_script and mode=='combat'):raise ValueError('Skript zuerst stoppen.')
            if mode in {'questing','sigil'}:await self.stop('sigil' if mode=='questing' else 'questing')
            async with self.bridge.lock:await self.bridge.adapter.prepare_automation(mode,list(ids))
            self.targets[mode]=list(ids)
            self.tasks[mode]=asyncio.create_task(self.run(mode,list(ids)))
        return {'mode':mode,'enabled':enabled,'automations':self.state()}
    async def run(self,mode,ids):
        try:
            start=asyncio.get_running_loop().time()
            while asyncio.get_running_loop().time()-start<self.bridge.settings.data['automation']['max_minutes']*60:
                args={'ids':ids,'mode':mode,'config':self.bridge.settings.data['automation'],'movement':self.bridge.settings.data['movement']}
                for pid in ids:
                    async with self.bridge.lock:await self.bridge.protected_step('automation_step',{**args,'ids':[pid]})
                await asyncio.sleep(self.bridge.settings.data['automation']['interval'])
            await self.bridge.log(mode+': Zeitlimit erreicht.','warning')
        except asyncio.CancelledError:raise
        except Exception as exc:await self.bridge.log(mode+': '+str(exc),'error')
        finally:await self.bridge.send({'type':'automation_done','mode':mode})
