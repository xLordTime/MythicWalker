"""Validated Deimos-style priorities backed by the pinned WizWalker combat API."""
import re

FILTERS={'damage','aoe','heal','heal_self','heal_other','blade','charm','ward','trap','enchant','aura','global','polymorph','shadow','shadow_creature','pierce','prism','dispel','inc_damage','out_damage','inc_heal','out_heal','mod_damage','mod_heal','mod_pierce'}
ALIASES={'dmg':'damage','fist':'mod_damage','sharp':'sharpened','potent':'potent trap'}


def split_top(source, separator):
    result=[];start=0;stack=[];quoted=None;escaped=False
    pairs={')':'(',']':'[','>':'<'}
    for i,c in enumerate(source):
        if quoted:
            if escaped:escaped=False
            elif c=='\\':escaped=True
            elif c==quoted:quoted=None
            continue
        if c in '\"\'':quoted=c
        elif c in '([' or c=='<' and source[max(0,i-3):i].lower()=='any':stack.append(c)
        elif c in ')]>' and stack and stack[-1]==pairs[c]:stack.pop()
        elif c==separator and not stack:result.append(source[start:i].strip());start=i+1
    result.append(source[start:].strip());return result


def parse_filter(source):
    source=source.strip();m=re.fullmatch(r'any<(.+)>',source,re.I)
    if m:
        kinds=[ALIASES.get(x.strip().lower(),x.strip().lower()) for x in split_top(m[1],'&')]
        unknown=set(kinds)-FILTERS
        if unknown:raise ValueError('Kartenfilter noch nicht verfügbar: '+', '.join(sorted(unknown)))
        return {'types':kinds}
    if not source or len(source)>180:raise ValueError('Ungültiger Kartenname.')
    if source[0] in '\"\'':
        if source[-1]!=source[0]:raise ValueError('Kartenname nicht geschlossen.')
        return {'literal':source[1:-1]}
    return {'name':ALIASES.get(source.lower(),source)}


def parse_style(source):
    if not isinstance(source,str) or len(source)>16000:raise ValueError('Playstyle: maximal 16 KB.')
    rows=[];client='mass'
    for raw in source.splitlines():
        line=raw.strip()
        if not line:continue
        if m:=re.fullmatch(r'###\s*p\s*(\d+)\s*',line,re.I):client='p'+m[1];continue
        if line.startswith('#'):continue
        if m:=re.match(r'^(mass|p\d+)\s*\|\s*(.+)$',line,re.I):client=m[1].lower();line=m[2]
        round_num=None
        if m:=re.match(r'^\{(\d+)\}\s*(.+)$',line):round_num=int(m[1]);line=m[2]
        for priority in split_top(line,'|'):
            if not priority:continue
            condition=None
            if priority.startswith('?('):
                depth=0;end=None
                for i,c in enumerate(priority[1:],1):
                    if c=='(':depth+=1
                    if c==')':
                        depth-=1
                        if depth==0:end=i;break
                if end is None:raise ValueError('Playstyle-Bedingung nicht geschlossen.')
                predicate=priority[2:end];priority=priority[end+1:].strip()
                m=re.fullmatch(r'(.+)\.([a-z_]+)\s*(<=|>=|==|!=|<|>)\s*(\d+(?:\.\d+)?)(%)?',predicate,re.I)
                if not m:raise ValueError('Bedingung: self.health < 30% oder enemy.wards >= 3.')
                condition={'target':m[1].strip(),'attribute':m[2].lower(),'op':m[3],'value':float(m[4]),'percent':bool(m[5])}
            moves=[]
            for entry in split_top(priority,'&'):
                parts=split_top(entry,'@')
                if len(parts)>2:raise ValueError('Zu viele Ziele in Playstyle-Eintrag.')
                card=parts[0];target=parts[1] if len(parts)>1 else 'enemy'
                enchants=[]
                while (m:=re.search(r'\[([^\[\]]+)\]\s*$',card)):
                    enchants.insert(0,parse_filter(m[1]));card=card[:m.start()].strip()
                special=re.fullmatch(r'(pass|willcast|draw)(?:\((\d+)\))?',card,re.I)
                moves.append({'special':special[1].lower(),'count':int(special[2] or 1),'target':target} if special else {'card':parse_filter(card),'enchants':enchants,'target':target})
            rows.append({'client':client,'round':round_num,'condition':condition,'moves':moves})
    if not rows:raise ValueError('Playstyle enthält keine Regeln. Platzhalter zuerst ersetzen.')
    if len(rows)>100:raise ValueError('Maximal 100 Playstyle-Prioritäten.')
    return rows


async def matches(card,query):
    if 'literal' in query:return query['literal'] in (await card.name(),await card.display_name())
    if 'name' in query:
        name=query['name'].casefold();return name in (await card.name()).casefold() or name in (await card.display_name()).casefold()
    typename=(await card.type_name()).lower();effects=await card.get_spell_effects();types=[];targets=[];rounds=[]
    for effect in effects:
        types.append((await effect.effect_type()).name.lower());targets.append((await effect.effect_target()).name.lower());rounds.append(await effect.num_rounds())
    for kind in query['types']:
        if kind=='aoe':ok=typename in {'aoe','steal'} and any('damage' in t for t in types)
        elif kind=='damage':ok=any('damage' in t and 'modify' not in t for t in types)
        elif kind.startswith('heal'):ok=any('heal' in t and 'modify' not in t for t in types) and (kind=='heal' or any(('self' if kind=='heal_self' else 'friendly') in t for t in targets))
        elif kind in {'blade','charm'}:ok=any('modify_outgoing_damage' in t for t in types)
        elif kind in {'trap','ward'}:ok=any('modify_incoming_damage' in t for t in types)
        elif kind=='aura':ok=any(n>0 for n in rounds) and typename in {'charm','ward','aura'}
        elif kind=='global':ok=any('global' in t for t in targets)
        elif kind=='enchant':ok=typename=='enchantment'
        elif kind.startswith('mod_'):ok=any('modify_card_'+kind[4:] in t for t in types)
        elif kind in {'inc_damage','out_damage','inc_heal','out_heal'}:ok=any(('modify_'+('incoming' if kind.startswith('inc') else 'outgoing')+'_'+kind.split('_')[1]) in t for t in types)
        else:ok=any(kind in t for t in types) or kind in typename
        if not ok:return False
    return True


async def find_card(cards,query,castable=False):
    for card in cards:
        if castable and not await card.is_castable():continue
        if await matches(card,query):return card
    return None


async def target_for(handler,source):
    source=source.strip();lower=source.lower()
    if lower in {'none','aoe'}:return None
    if lower=='self':return await handler.get_client_member()
    if lower.startswith('spell(') and lower.endswith(')'):
        query=parse_filter(source[6:-1]);return await find_card(await handler.get_cards(),query)
    if lower.startswith('select(') and lower.endswith(')'):
        targets=[await target_for(handler,item) for item in split_top(source[7:-1],',')]
        return targets if all(target is not None for target in targets) else None
    m=re.fullmatch(r'(enemy|ally|enemies|allies|boss)(?:\((\d+)\))?',lower)
    if m:
        family=m[1];members=await (handler.get_all_monster_members() if family in {'enemy','enemies','boss'} else handler.get_all_player_members())
        members=[member for member in members if not await member.is_dead()]
        if family=='boss':
            for member in members:
                if await member.is_boss():return member
            return None
        if family in {'enemies','allies'}:return members or None
        index=int(m[2] or 0);return members[index] if index<len(members) else None
    members=await handler.get_members();name=source.strip('\"\'').casefold()
    for member in members:
        if name in (await member.name()).casefold():return member
    return None


async def member_attribute(member,name):
    if hasattr(member,name) and not name.startswith('_'):return await getattr(member,name)()
    disposition=None
    for prefix in ['beneficial_','harmful_']:
        if name.startswith(prefix):disposition=prefix[:-1];name=name[len(prefix):]
    name={'charm':'charms','ward':'wards','ot':'over_time','aura':'auras'}.get(name,name)
    if name not in {'charms','wards','over_time','auras'}:raise ValueError('Playstyle-Messwert nicht verfügbar: '+name)
    participant=await member.get_participant();effects=await (participant.aura_effects() if name=='auras' else participant.hanging_effects());count=0
    for effect in effects:
        kind=(await effect.effect_type()).name.lower();side=(await effect.disposition()).name.lower()
        if disposition and disposition not in side:continue
        category='charms' if 'outgoing' in kind else 'wards' if 'incoming' in kind else 'over_time' if 'over_time' in kind else 'auras'
        if category==name:count+=1
    return count


async def condition_passes(handler,condition):
    if not condition:return True
    source=condition['target'];group=re.fullmatch(r'(any|all|avg)\((enemies|allies)\)',source,re.I)
    target=await target_for(handler,group[2] if group else source);members=target if isinstance(target,list) else [target] if target else []
    if not members:return False
    values=[]
    for member in members:
        value=await member_attribute(member,condition['attribute'])
        if condition['percent']:
            maximum=await member_attribute(member,'max_'+condition['attribute']);value=100*value/maximum if maximum else 0
        values.append(value)
    compare=lambda a:{'<':a<condition['value'],'>':a>condition['value'],'<=':a<=condition['value'],'>=':a>=condition['value'],'==':a==condition['value'],'!=':a!=condition['value']}[condition['op']]
    if group and group[1].lower()=='avg':return compare(sum(values)/len(values))
    return any(map(compare,values)) if group and group[1].lower()=='any' else all(map(compare,values))


async def play_round(adapter,client,rows,round_num):
    handler=adapter.CombatHandler(client);pinned=[row for row in rows if row['round']==round_num]
    for row in pinned or [row for row in rows if row['round'] is None]:
        if not await condition_passes(handler,row['condition']):continue
        performed=False
        for move in row['moves']:
            if move.get('special')=='pass':await adapter.mouse_action(client,handler.pass_button);return True
            if move.get('special')=='draw':
                for _ in range(min(move['count'],7)):await adapter.mouse_action(client,handler.draw_button)
                performed=True;continue
            target=await target_for(handler,move['target'])
            if move.get('special')=='willcast':
                await adapter.mouse_action(client,handler.attempt_willcast,on_client=move['target'].lower()=='self',on_member=await target.name() if target is not None and not isinstance(target,list) and move['target'].lower()!='self' else None);performed=True;continue
            if target is None and move['target'].lower() not in {'none','aoe'}:break
            cards=await handler.get_cards();candidate=await find_card(cards,move['card'],True)
            if candidate is None:break
            for enchant_query in move['enchants']:
                enchant=await find_card(await handler.get_cards(),enchant_query)
                if enchant:
                    await adapter.mouse_action(client,enchant.cast,candidate)
                    candidate=await find_card(await handler.get_cards(),move['card']) or candidate
            await adapter.mouse_action(client,candidate.cast,target);performed=True
            if not move['target'].lower().startswith('spell('):return True
        # Enchants, draws and willcasts may precede a normal card selection.
    return False
