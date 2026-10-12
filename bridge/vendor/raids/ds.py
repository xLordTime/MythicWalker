# Adapted from Lxghtend/raid-utility-tools (GPL-3.0). See UPSTREAM.json.
import time
import asyncio
from wizwalker.memory import Window
from wizwalker.errors import HookNotActive
from wizwalker import ClientHandler, Client, XYZ
from wizwalker.constants import Keycode, Primitive
from wizwalker.memory.memory_objects.enums import WindowFlags
from .worlds_collide import WorldsCollideTP
excluded_drums = [XYZ(156.32049560546875, 10636.1904296875, 45.247039794921875), XYZ(21.287410736083984, 10961.7099609375, 39.414398193359375), XYZ(-171.69459533691406, 10763.9296875, 40.14535140991211), XYZ(-176.74240112304688, 10495.9404296875, 40.14535140991211), XYZ(30.03204917907715, 10290.2197265625, 40.14535140991211), XYZ(296.79119873046875, 10286.2197265625, 40.14535140991211), XYZ(487.0555114746094, 10465.330078125, 40.14535140991211), XYZ(502.71148681640625, 10760.7900390625, 40.14535140991211), XYZ(311.6960144042969, 10979.5, 40.14535140991211), XYZ(-7533.02099609375, 3650.97998046875, 30.14211082458496)]

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

    def are_xyzs_within_threshold(self, xyz_1: XYZ, xyz_2: XYZ, threshold: int=200):
        threshold_check = [abs(abs(xyz_1.x) - abs(xyz_2.x)) < threshold, abs(abs(xyz_1.y) - abs(xyz_2.y)) < threshold, abs(abs(xyz_1.z) - abs(xyz_2.z)) < threshold]
        return all(threshold_check)

    async def handle_basic_teleport(self, location_x: float, location_y: float, location_z: float, yaw: float=None):
        client = self.foreground_client
        if client:
            await client.teleport(XYZ(location_x, location_y, location_z), yaw)

    async def entity_teleport(self, entity_name: str):
        client = self.foreground_client
        if client:
            entity = await client.get_base_entities_with_name(entity_name)
            if not entity:
                print(f'{client.title} did not find {entity_name}')
                return
            await WorldsCollideTP(client, await entity[0].location())
            print(f'{client.title} teleported to {entity_name}.')

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

    async def raid_drum_teleport(self):
        client = self.foreground_client
        if client:
            drum_list = await client.get_base_entities_with_name('Raid_LightPad')
            if not drum_list:
                print(f'{client.title} did not find Raid_LightPad.')
                return
            filtered_drums = []
            for drum in drum_list:
                drum_pos = await drum.location()
                if not any((self.are_xyzs_within_threshold(drum_pos, excluded) for excluded in excluded_drums)):
                    filtered_drums.append(drum)
            if len(filtered_drums) > 0:
                drum = filtered_drums[0]
                await client.teleport(await drum.location())

    async def auto_raid_drums(self):
        client = self.foreground_client
        if client:
            try:
                for i in range(8):
                    filtered_drums = []
                    while filtered_drums == []:
                        drum_list = await client.get_base_entities_with_name('Raid_LightPad')
                        for drum in drum_list:
                            drum_pos = await drum.location()
                            if not any((self.are_xyzs_within_threshold(drum_pos, excluded) for excluded in excluded_drums)):
                                filtered_drums.append(drum)
                        await asyncio.sleep(0.1)
                    if filtered_drums != []:
                        target_drum = filtered_drums[0]
                        target_drum_gid = await target_drum.global_id_full()
                        await client.teleport(await target_drum.location())
                        while True:
                            current_drums = await client.get_base_entities_with_name('Raid_LightPad')
                            current_drum_gids = [await drum.global_id_full() for drum in current_drums]
                            if target_drum_gid not in current_drum_gids:
                                break
                            await asyncio.sleep(0.1)
                        print(f'{client.title} activated drum {i + 1}.')
                print(f'[AUTO DRUMS] completed drums.')
            except asyncio.CancelledError:
                print(f'[AUTO DRUMS] cancelled at drum #{i + 1}.')
