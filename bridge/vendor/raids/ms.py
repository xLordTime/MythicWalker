# Adapted from Lxghtend/raid-utility-tools (GPL-3.0). See UPSTREAM.json.
import time
import asyncio
from wizwalker.memory import Window
from wizwalker.errors import HookNotActive
from wizwalker import ClientHandler, Client, XYZ
from wizwalker.constants import Keycode, Primitive
from wizwalker.memory.memory_objects.client_object import DynamicClientObject
from wizwalker.memory.memory_objects.enums import WindowFlags
from .worlds_collide import WorldsCollideTP
excluded_drums = [XYZ(-3.07, -900.0, 680.0), XYZ(-126.96, -900.0, 680.0), XYZ(117.797, -900.0, 680.0), XYZ(-249.35, -900.0, 680.0), XYZ(-993.921, -900.0, 680.0), XYZ(-1113.587, -900.0, 680.0), XYZ(-1232.52, -900.0, 680.0), XYZ(-1351.739, -900.0, 679.999)]

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

    async def wait_for_range(self, client: Client):
        while True:
            if await self.is_visible_by_path(client.root_window, ['WorldView', 'NPCRangeWin']):
                return
            await asyncio.sleep(0.1)

    async def binding_buttons(self, layout: str='straight'):
        button_sets = {'straight': (((935.2365112304688, -997.5791625976562, 327.5176086425781), 4.16), ((1369.3870849609375, -3018.9912109375, 327.517578125), 5.194), ((-245.64674377441406, -4401.7724609375, 327.517578125), 6.179)), 'alt_one': (((943.3026123046875, -988.5377197265625, 327.5176086425781), 4.16), ((-200.7386474609375, -4449.11767578125, 327.517578125), 6.259), ((-2562.184814453125, -1634.2911376953125, 327.517578125), 2.21)), 'alt_two': (((-1005.826, -242.829, 327.517), 3.131), ((1422.57, -3035.672, 327.517), 4.774), ((-2239.302, -3732.226, 327.517), 1.021))}
        buttons = button_sets[layout]
        client = self.foreground_client
        if client:
            for position, yaw in buttons:
                await client.teleport(XYZ(*position), yaw)
                await self.wait_for_range(client)
                await asyncio.sleep(0.8)
                await client.send_key(Keycode.X)

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

    async def wisp_teleport(self, object: DynamicClientObject):
        client = self.foreground_client
        if client:
            wisp_pos = await object.location()
            if wisp_pos:
                await WorldsCollideTP(client, wisp_pos)

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
