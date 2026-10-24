"""A28: a free combined Battle Command in and adjacent to Sequani.

The Event owns the scope and obtains each human lender's consent. The Battle
engine then sees the combined force through battle.combined, while physical
owners retain all counters and Available pools. Provisional project ruling
PR-02 applies the A8.6.6 participation condition to both non-player Aedui and
Belgae; it is subject to correction by an authoritative source. See
docs/provisional-rulings.md#pr-02.
"""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_leader_in_region
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


def nonplayer_warband_agreement(state, executing_faction, region):
    """PR-02: both NP Aedui and Belgae require a native attacking piece.

    Read physical counters: automatic Arverni or already-lent pieces cannot
    satisfy the executor's contribution. Allies, Forts, Citadels and
    Settlements do not join an attacking force. This adopted provisional
    ruling may be corrected by later authoritative clarification.
    """
    if (state.get('scenario') not in rc.ARIOVISTUS_SCENARIOS
            or executing_faction not in rc.FACTIONS
            or region not in allowed_regions(state)):
        return False
    pieces = state['spaces'].get(region, {}).get('pieces', {}).get(
        executing_faction, {})
    return (pieces.get(rc.LEADER) is not None
            or pieces.get(rc.LEGION, 0) > 0
            or any(pieces.get(visibility, {}).get(piece, 0) > 0
                   for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)
                   for piece in TYPES))


def _possible_owners(state, faction, region, target, *, include_humans=False):
    """Known NP loans, plus optional human loans only for human menus."""
    owners = _automatic_owners(faction)
    nonplayers = state.get('non_player_factions', set())
    for owner in rc.FACTIONS:
        if owner in (faction, rc.ARVERNI, target) or not _mobile(state, region, owner):
            continue
        if owner in nonplayers:
            if (owner in (rc.AEDUI, rc.BELGAE)
                    and nonplayer_warband_agreement(state, faction, region)):
                owners.append(owner)
        elif include_humans:
            owners.append(owner)
    return owners


def target_options(state, faction):
    """Human targets include every force its owners could legally lend."""
    from fs_bot.engine.execute import _attacker_has_force
    options = {}
    for region in allowed_regions(state):
        enemies = []
        for target in rc.FACTIONS:
            if target == faction:
                continue
            owners = _possible_owners(state, faction, region, target,
                                      include_humans=True)
            with combined_force(state, faction, {region: owners}):
                if (_attacker_has_force(state, region, faction)
                        and count_pieces(state, region, target)):
                    enemies.append(target)
        if enemies:
            options[region] = enemies
    return options


def _default_plan(state, faction):
    """Apply the existing free-Battle priorities with guaranteed NP loans.

    The defender cannot lend its own Warbands. Evaluate the actual force for
    each candidate separately so borrowing neither removes a candidate from
    consideration nor makes a refused loan look like a viable attack.
    Human agreements remain live decisions, never guessed in this preview.
    """
    from fs_bot.engine.execute import (
        _attacker_has_force, _predicted_legion_losses, _german_warband_floor_ok,
    )
    candidates = []
    for region in allowed_regions(state):
        best = None
        for target in rc.FACTIONS:
            if target == faction or (faction == rc.BELGAE and target != rc.ROMANS):
                continue
            owners = _possible_owners(state, faction, region, target)
            with combined_force(state, faction, {region: owners}):
                if (not _attacker_has_force(state, region, faction)
                        or not count_pieces(state, region, target)):
                    continue
                if faction == rc.BELGAE:
                    score = _predicted_legion_losses(state, region, faction)
                    if score <= 0:
                        continue
                    defender_priority = (score,)
                else:
                    score = sum(count_pieces(state, region, target, piece)
                                for piece in (rc.WARBAND, rc.LEGION, rc.AUXILIA))
                    defender_priority = (
                        bool(get_leader_in_region(state, region, target)), score,
                        sum(count_pieces(state, region, target, piece)
                            for piece in (rc.ALLY, rc.CITADEL)))
                floor_ok = (faction != rc.GERMANS
                            or _german_warband_floor_ok(state, region, faction, target))
                if best is None or defender_priority > best[0]:
                    best = (defender_priority, score, target, floor_ok)
        if best is not None and best[3]:
            candidates.append((best[1], region, best[2]))
    # Stable sorting retains sorted Region order for equal priorities, as in
    # the existing repeated free-Battle chooser, without consuming RNG.
    candidates.sort(key=lambda candidate: -candidate[0])
    return [{'region': region, 'target_faction': target}
            for _, region, target in candidates]


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
                or any(owner not in rc.FACTIONS or owner in (faction, rc.ARVERNI, target)
                       for owner in lenders) or len(set(lenders)) != len(lenders)):
            raise ValueError('A28 allied_factions must name distinct other player factions excluding the defender')
        normalized.append({'region': region, 'target': target,
                           'allied_factions': lenders})
        seen.add(region)
    return normalized


def _agreement(state, faction, owner, region, target):
    if owner in state.get('non_player_factions', set()):
        if owner == rc.ROMANS:
            return False, None  # A8.8.8: never lend Auxilia.
        if owner in (rc.AEDUI, rc.BELGAE):
            return nonplayer_warband_agreement(state, faction, region), None
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
