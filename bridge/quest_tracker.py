"""Read-only quest journal using the pinned WizWalker API; no extra hooks/offsets."""
import asyncio
import html
import re
import time


def clean(value, limit=500):
    return html.unescape(re.sub(r'<[^>]*>', '', str(value or ''))).strip()[:limit]


class QuestReader:
    def __init__(self):
        self.names = {}

    async def name(self, client, key):
        key = clean(key, 200)
        cache = client.cache_handler
        root = cache._root_wad
        ident = (str(root.file_path), key)
        if ident in self.names:
            return self.names[ident]
        value, language = key, 'key'
        # Upstream's language resolver is en-US only. Prefer the local DE file.
        if '_' in key:
            filename, code = key.split('_', 1)
            if re.fullmatch(r'[\w-]{1,100}', filename):
                names = await root.names()
                for locale in ('de-DE', 'en-US'):
                    path = f'Locale/{locale}/{filename}.lang'
                    if path not in names:
                        continue
                    parsed = cache._parse_lang_file(await root.get_file(path)) or {}
                    mapping = parsed.get(filename, {})
                    for k, v in mapping.items():
                        self.names[(ident[0], filename+'_'+k)] = (clean(v), locale)
                    if code in mapping:
                        value, language = clean(mapping[code]), locale
                        break
        if len(self.names) > 50000:
            self.names.clear()
        self.names[ident] = (value, language)
        return value, language

    async def label(self, client, obj, fallback):
        try:
            key = await obj.name_lang_key()
            try:
                name, language = await self.name(client, key)
            except Exception:
                name, language = clean(key), 'key'
            return {'name': name or fallback, 'name_key': clean(key, 200), 'language': language}
        except Exception:
            return {'name': fallback, 'name_key': '', 'language': 'unavailable'}

    async def goal_text(self, client):
        try:
            window = client.root_window
            for part in ['WorldView', 'windowHUD', 'QuestHelperHud', 'ElementWindow', '', 'txtGoalName']:
                window = await window.get_child_by_name(part)
            return clean(await window.maybe_text())
        except Exception:
            return ''

    async def read(self, client):
        async with asyncio.timeout(6):
            return await self._read(client)

    async def _read(self, client):
        result = {'id': str(client.process_id), 'status': 'loading', 'active_id': None,
                  'goal_id': None, 'goal_text': '', 'quests': [], 'zone': '', 'truncated': False, 'metadata_available': True}
        if await client.is_loading():
            return result
        active, goal = await client.quest_id(), await client.goal_id()
        result.update(zone=clean(await client.zone_name(), 200))
        if active <= 0:
            result['status'] = 'no_active'
            return result
        try:
            manager = await client.quest_manager()
            journal = await manager.quest_data()
        except Exception:
            # The active IDs remain useful for a locally supplied quest plan.
            journal = {};result['metadata_available'] = False
        # Put the selected quest first, even when a very large journal is capped.
        keys = ([active] if active in journal else []) + [k for k in journal if k != active]
        result['truncated'] = len(keys) > 256
        deadline = time.monotonic() + 3
        for ident in keys[:256]:
            if time.monotonic() > deadline:
                result['truncated'] = True
                break
            quest = journal[ident]
            row = {'id': str(ident), **await self.label(client, quest, f'Quest {ident}'),
                   'mainline': None, 'ready': None, 'world': '', 'area': '', 'goals': []}
            try:
                row['mainline'] = bool(await quest.mainline())
                row['ready'] = bool(await quest.ready_to_turn_in())
            except Exception:
                pass
            try:
                goals = await quest.goal_data()
            except Exception:
                goals = {};result['metadata_available'] = False
            destination = goals.get(goal) if ident == active else next(iter(goals.values()), None)
            if destination is not None:
                try:
                    row['area'] = clean(await destination.goal_destination_zone(), 200)
                    row['world'] = row['area'].split('/')[0]
                except Exception:
                    pass
            if ident == active:
                for gid, data in list(goals.items())[:64]:
                    item = {'id': str(gid), **await self.label(client, data, f'Teilziel {gid}')}
                    try:
                        item['zone'] = clean(await data.goal_destination_zone(), 200)
                        item['kind'] = (await data.goal_type()).name
                    except Exception:
                        item.update(zone='', kind='unknown')
                    row['goals'].append(item)
            result['quests'].append(row)
        if active not in journal:
            result['quests'].insert(0, {'id': str(active), 'name': f'Quest {active}',
                'name_key': '', 'language': 'unavailable', 'mainline': None, 'ready': None, 'world': '', 'area': '', 'goals': []})
        goal_text = await self.goal_text(client)
        # Discard mixed snapshots during a quest/character/zone transition.
        if await client.is_loading() or (active, goal) != (await client.quest_id(), await client.goal_id()):
            result.update(quests=[], status='transition')
            return result
        result.update(status='ready', active_id=str(active), goal_id=str(goal), goal_text=goal_text)
        return result
