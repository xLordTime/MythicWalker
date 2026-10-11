import asyncio
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import AsyncMock,patch

@dataclass(unsafe_hash=True)
class Point:
    x:float
    y:float
    z:float

def nav_data():
    data=struct.pack('<hhh',3,3,0)
    for i,x in enumerate([100.,200.,300.]):data+=struct.pack('<fffh',x,0.,0.,i)
    return data+struct.pack('<i',2)+struct.pack('<hhhh',0,1,1,2)

def load_nav():
    wiz=types.ModuleType('wizwalker');wiz.XYZ=Point;wiz.Orient=object;wiz.Client=object;wiz.Keycode=types.SimpleNamespace(A='A',D='D')
    wad=types.ModuleType('wizwalker.file_readers.wad');wad.Wad=types.SimpleNamespace(from_game_data=lambda path:types.SimpleNamespace(get_file=AsyncMock(return_value=nav_data())))
    logger=types.ModuleType('loguru');logger.logger=types.SimpleNamespace(debug=lambda *a:None)
    spec=importlib.util.spec_from_file_location('test_nav_source',Path(__file__).resolve().parents[1]/'bridge/navmap.py');module=importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,{'wizwalker':wiz,'wizwalker.file_readers':types.ModuleType('wizwalker.file_readers'),'wizwalker.file_readers.wad':wad,'loguru':logger}):spec.loader.exec_module(module)
    return module

class NavmapTests(unittest.IsolatedAsyncioTestCase):
    async def test_zone_nav_fallback_when_direct_teleport_rejected(self):
        nav=load_nav();position=[Point(0,0,0)];target=Point(500,0,0)
        async def teleport(p):
            if p!=target:position[0]=p
        client=types.SimpleNamespace(title='test',in_battle=AsyncMock(return_value=False),is_loading=AsyncMock(return_value=False),is_in_dialog=AsyncMock(return_value=False),zone_name=AsyncMock(return_value='WizardCity/Commons'),body=types.SimpleNamespace(position=AsyncMock(side_effect=lambda:position[0])),teleport=AsyncMock(side_effect=teleport),goto=AsyncMock())
        with patch.object(nav.asyncio,'sleep',AsyncMock()):await nav.navmap_tp(client,target)
        self.assertGreater(client.teleport.await_count,1);client.goto.assert_awaited_once_with(500,0)
        vertices,edges=nav.parse_nav_data(nav_data());self.assertEqual(len(vertices),3);self.assertEqual(edges,[(0,1),(1,2)])
    async def test_busy_client_is_not_teleported(self):
        nav=load_nav();client=types.SimpleNamespace(in_battle=AsyncMock(return_value=True),teleport=AsyncMock())
        await nav.navmap_tp(client,Point(1,2,3));client.teleport.assert_not_awaited()
