import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from adapter import WizAdapter

class FreecamTeleportTests(unittest.IsolatedAsyncioTestCase):
    def setup_client(self, teleport):
        camera=Obj(position=AsyncMock(return_value=Obj(x=100,y=200,z=300)))
        client=Obj(process_id=42, game_client=Obj(is_freecam=AsyncMock(return_value=True),free_camera_controller=AsyncMock(return_value=camera)),
                   _unpatch_movement_update=AsyncMock(),_patch_movement_update=AsyncMock(),teleport=teleport,
                   body=Obj(position=AsyncMock(return_value=Obj(x=100,y=200,z=300))))
        adapter=WizAdapter.__new__(WizAdapter);adapter.selected=lambda ids:[client];adapter.XYZ=lambda x,y,z:Obj(x=x,y=y,z=z)
        return adapter,client
    async def test_teleport_runs_unfrozen_and_reports_verified_position(self):
        adapter,client=self.setup_client(AsyncMock())
        async def teleport(target):
            client._unpatch_movement_update.assert_awaited_once()
            client._patch_movement_update.assert_not_awaited()
            self.assertEqual([target.x,target.y,target.z],[100,200,300])
        client.teleport.side_effect=teleport
        result=await adapter.execute('camera_tp',{'ids':['42']})
        self.assertTrue(result[0]['verified'])
        client._patch_movement_update.assert_awaited_once()
    async def test_failed_or_cancelled_teleport_always_refreezes(self):
        for failure in [RuntimeError('test failure'),asyncio.CancelledError()]:
            adapter,client=self.setup_client(AsyncMock(side_effect=failure))
            with self.assertRaises(type(failure)):await adapter.execute('camera_tp',{'ids':['42']})
            client._patch_movement_update.assert_awaited_once()
