"""A28: a free combined Battle Command in and adjacent to Sequani.

The Event owns the scope and obtains each human lender's consent. The Battle
engine then sees the combined force through battle.combined, while physical
owners retain all counters and Available pools. The A8.6.6 Aedui/Belgae
agreement conflict remains explicitly unresolved in QUESTIONS.md.
"""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.engine.agent import consult_agent, AGREEMENT
from fs_bot.map.map_data import get_adjacent, get_playable_regions
from fs_bot.battle.combined import combined_force, TYPES


def allowed_regions(state):
    playable = set(get_playable_regions(state['scenario'], state.get('capabilities')))
    return sorted(playable & {rc.SEQUANI, *get_adjacent(
        rc.SEQUANI, state['scenario'], state.get('capabilities'))})


def _mobile(state, region, faction):
    return sum(count_pieces(state, region, faction, piece) for piece in TYPES)


def _automatic_owners(faction):
    return [] if faction == rc.ARVERNI else [rc.ARVERNI]


def target_options(state, faction):
    """Human candidate targets, including attacks using only a borrowed force."""
    from fs_bot.engine.execute import _attacker_has_force
    options = {}
    for region in allowed_regions(state):
        owners = _automatic_owners(faction)
        with combined_force(state, faction, {region: owners}):
            own_force = _attacker_has_force(state, region, faction)
            enemies = [enemy for enemy in rc.FACTIONS
                       if enemy != faction and count_pieces(state, region, enemy)]
        # A human may request another player's pieces even without an own
        # force. Consent is obtained during resolution, before any Battle.
        enemies = [enemy for enemy in enemies if own_force or any(
            _mobile(state, region, other) for other in rc.FACTIONS
            if other not in (faction, enemy))]
        if enemies:
            options[region] = enemies
    return options


def _default_plan(state, faction):
    from fs_bot.engine.execute import _choose_free_battle
    result = []
    remaining = set(allowed_regions(state))
    with combined_force(state, faction, {
            region: _automatic_owners(faction) for region in remaining}):
        while remaining:
            region, target = _choose_free_battle(state, faction, remaining)
            if region is None:
                break
            result.append({'region': region, 'target_faction': target})
            remaining.remove(region)
    return result


def _validate_plan(state, faction, plan):
    if not isinstance(plan, list):
        raise ValueError('A28 battle_plan must be a list')
    seen, normalized = set(), []
    options = target_options(state, faction)
    for entry in plan:
        if not isinstance(entry, dict) or set(entry) - {
                'region', 'target', 'target_faction', 'allied_factions'}:
            raise ValueError('A28 Battle entries need a Region and target faction')
        region = entry.get('region')
        target = entry.get('target_faction', entry.get('target'))
        if (region not in options or region in seen
                or target not in options[region]):
            raise ValueError('A28 selects each eligible Sequani/adjacent Region once with an opposing target')
        lenders = entry.get('allied_factions')
        if lenders is not None and (not isinstance(lenders, list)
                or any(owner not in rc.FACTIONS or owner in (faction, rc.ARVERNI)
                       for owner in lenders) or len(set(lenders)) != len(lenders)):
            raise ValueError('A28 allied_factions must name distinct other player factions')
        normalized.append({'region': region, 'target': target,
                           'allied_factions': lenders})
        seen.add(region)
    return normalized


def _agreement(state, faction, owner, region, target):
    if owner in state.get('non_player_factions', set()):
        if owner == rc.ROMANS:
            return False, None  # A8.8.8: never lend Auxilia.
        if owner in (rc.AEDUI, rc.BELGAE):
            return False, 'A8.6.6 names Aedui in its heading and Belgae in its text; agreement policy unresolved'
        from fs_bot.bots.german_bot import node_g_agreements
        return bool(node_g_agreements(state, faction, 'admagetobriga_warbands')), None
    reply = consult_agent(state, owner, {
        'kind': AGREEMENT, 'request_type': 'admagetobriga_warbands',
        'requesting_faction': faction,
        'context': {'region': region, 'defender': target,
                    'executing_faction': faction,
                    'piece_types': list(TYPES), 'may_take_losses': True}})
    return reply is True, None


def resolve_admagetobriga(state, faction):
    from fs_bot.engine.execute import _execute_battle, _attacker_has_force
    params = state.get('event_params') or {}
    plan = params.get('battle_plan')
    if plan is None and params.get('region') is not None:
        plan = [{'region': params['region'], 'target_faction': params.get('target_faction')}]
    if plan is None:
        plan = _default_plan(state, faction)
    plan = _validate_plan(state, faction, plan)
    owners_by_region, agreements, unresolved = {}, [], []
    for entry in plan:
        region, target = entry['region'], entry['target']
        owners = _automatic_owners(faction)
        lenders = entry['allied_factions']
        if lenders is None:
            lenders = [owner for owner in rc.FACTIONS
                       if owner not in (faction, rc.ARVERNI, target)]
        for owner in lenders:
            if not _mobile(state, region, owner):
                continue
            agreed, blocked = _agreement(state, faction, owner, region, target)
            agreements.append({'faction': owner, 'region': region,
                               'agreed': None if blocked else agreed})
            if blocked:
                unresolved.append({'faction': owner, 'region': region, 'reason': blocked})
            if agreed:
                owners.append(owner)
        owners_by_region[region] = owners
    with combined_force(state, faction, owners_by_region):
        battles = [{'region': entry['region'], 'target': entry['target']}
                   for entry in plan
                   if _attacker_has_force(state, entry['region'], faction)
                   and count_pieces(state, entry['region'], entry['target'])]
        result = _execute_battle(state, faction, {
            'command': 'Battle', 'sa': 'No SA', 'sa_regions': [],
            'details': {'battle_plan': battles, 'no_retreat': True}})
    report = {'free_action': 'battle', 'flag': 'card_A28_combined_battle',
              'result': result, 'agreements': agreements,
              'unresolved_agreements': unresolved}
    if len(battles) == 1:
        report.update(region=battles[0]['region'], defender=battles[0]['target'])
    return [report]


def collect_battle_plan(state, faction, stdin, stdout):
    """Choose every Battle target explicitly; agreement is each lender's choice."""
    from fs_bot.cli.menus import prompt_choice, prompt_yes_no
    options = target_options(state, faction)
    selected = []
    while options:
        region = prompt_choice(stdin, stdout, 'A28: Battle in which Region?',
            [('Finish selecting Battles', None)] + [(r, r) for r in options])
        if region is None:
            break
        target = prompt_choice(stdin, stdout, f'A28: target in {region}?',
                               [(f, f) for f in options.pop(region)])
        lenders = [other for other in rc.FACTIONS
                   if other not in (faction, rc.ARVERNI, target)
                   and _mobile(state, region, other)
                   and prompt_yes_no(stdin, stdout,
                       f'Ask {other} to lend Warbands/Auxilia in {region}?',
                       default=False)]
        selected.append({'region': region, 'target_faction': target,
                         'allied_factions': lenders})
    return {'battle_plan': selected}
