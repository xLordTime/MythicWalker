# Adapted from Lxghtend/raid-utility-tools (GPL-3.0). See UPSTREAM.json.
import time
import asyncio
from wizwalker.memory import Window
from wizwalker.errors import HookNotActive
from wizwalker import ClientHandler, Client, XYZ
from wizwalker.constants import Keycode, Primitive
from wizwalker.memory.memory_objects.enums import WindowFlags
from .worlds_collide import WorldsCollideTP

class Utils:

    def __init__(self, client):
        self.foreground_client = client

    async def is_visible_by_path(self, base_window: Window, path: list[str]):
        if (window := (await self.window_from_path(base_window, path))):
            return await window.is_visible()
        return False

    async def window_from_path(self, base_window: Window, path: list[str]) -> Window:
        if not path:
            return base_window
        for child in await base_window.children():
            if await child.name() == path[0]:
                if (found_window := (await self.window_from_path(child, path[1:]))):
                    return found_window
        return False

    async def handle_basic_teleport(self, location_x: float, location_y: float, location_z: float, yaw: float=None):
        client = self.foreground_client
        if client:
            await client.teleport(XYZ(location_x, location_y, location_z), yaw)

    async def grab_item(self, entity_name: str):
        client = self.foreground_client
        if client:
            original_location = await client.body.position()
            item = await client.get_base_entities_with_name(entity_name)
            if not item:
                print(f'{client.title} did not find {entity_name}.')
                return
            item_position = await item[0].location()
            await WorldsCollideTP(client, item_position)
            await asyncio.sleep(0.1)
            if await client.body.position() == original_location:
                return
            while not await self.is_visible_by_path(client.root_window, ['WorldView', 'NPCRangeWin', 'wndTitleBackground']):
                if await client.body.position() == original_location:
                    break
                await asyncio.sleep(0.1)
            while True:
                if not await self.is_visible_by_path(client.root_window, ['WorldView', 'NPCRangeWin', 'wndTitleBackground']):
                    break
                await client.send_key(Keycode.X, 0.1)
                await asyncio.sleep(0.1)
            if await client.body.position() != original_location:
                await client.teleport(original_location)
            print(f'{client.title} grabbed {entity_name}.')
