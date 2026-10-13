import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import AsyncMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from movement_guard import MovementGuard,install_movement_guard

class MovementGuardTests(unittest.IsolatedAsyncioTestCase):
    def setup_guard(self):
        memory={100:b'\x90\x90',200:b'\x90\x90'}
        async def read(a,n):return memory[a]
        async def write(a,v):memory[a]=v
        client=Obj(process_id=42,is_running=lambda:True,hook_handler=Obj(read_bytes=read,write_bytes=write),teleport=AsyncMock())
        hook=Obj(_collision_je_addrs=(100,200),_old_collision_jes_bytes=(b'\x74\x01',b'\x74\x02'))
        with patch('movement_guard.native_flush',return_value=lambda *a:None):guard=MovementGuard(client,hook)
        return guard,client,memory
    async def test_no_collision_bypass_while_only_hooked(self):
        guard,c,m=self.setup_guard();await guard.install()
        self.assertEqual(m,{100:b'\x74\x01',200:b'\x74\x02'})
        async def tp(*args,**kwargs):self.assertEqual(m,{100:b'\x90\x90',200:b'\x90\x90'})
        guard.original_teleport.side_effect=tp
        await c.teleport('pos',yaw=1.2)
        guard.original_teleport.assert_awaited_once_with('pos',yaw=1.2)
        self.assertEqual(m,{100:b'\x74\x01',200:b'\x74\x02'})
        guard.release();self.assertIs(c.teleport,guard.original_teleport)
    async def test_restore_on_exception_and_partial_patch_write(self):
        for partial in [False,True]:
            guard,c,m=self.setup_guard();await guard.install()
            if partial:
                async def write(a,v):
                    m[a]=v
                    if a==200 and v==b'\x90\x90':raise RuntimeError('partial patch')
                c.hook_handler.write_bytes=write
            else:guard.original_teleport.side_effect=RuntimeError('TP failed')
            with self.assertRaises(RuntimeError):await c.teleport('pos')
            self.assertEqual(m,{100:b'\x74\x01',200:b'\x74\x02'})
    async def test_cancel_drains_native_teleport_before_restoring(self):
        guard,c,m=self.setup_guard();await guard.install();started=asyncio.Event();release=asyncio.Event()
        async def tp(*args):started.set();await release.wait()
        guard.original_teleport.side_effect=tp
        task=asyncio.create_task(c.teleport('pos'));await started.wait();task.cancel();await asyncio.sleep(0)
        self.assertFalse(task.done());release.set()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(m,{100:b'\x74\x01',200:b'\x74\x02'})
