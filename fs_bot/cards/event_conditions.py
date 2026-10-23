"""Bounded NP applicability checks for Event grants with specific prerequisites.

§8.1.1/8.2.1 require declining an unavailable Event before committing to it.
The generic flag table cannot establish that a scoped Battle or conditional
Morbihan/Procillus action is possible. Previews use isolated board/RNG copies
and never query a human decision agent.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc


def np_event_available(state, card_id, faction, shaded):
    """Return False for a known unavailable grant, otherwise None/True."""
    if card_id == 72 and shaded:
        from fs_bot.cards.impetuosity import np_choices
        return bool(np_choices(state, faction))
    if not ((card_id in (6, 11, 17, 25, 36) and not shaded)
            or (card_id in (21, 45, 58) and shaded)
            or card_id in (26, 62, 64, 'A20', 'A21')
            or (card_id == 'A37' and (shaded or faction == rc.AEDUI))
            or (card_id == 'A65' and not shaded)
            or (card_id in ('A19', 'A45') and shaded and faction == rc.GERMANS)):
        return None
    from fs_bot.commands.common import free_action_scope
    trial = deepcopy({key: value for key, value in state.items()
                      if key != 'decision_agent'})
    # Event movement is not blocked by Frost and never charges Resources.
    # Availability must use exactly the same scope as actual execution.
    with free_action_scope(trial):
        return _available(trial, card_id, faction, shaded)


def _available(trial, card_id, faction, shaded):
    from fs_bot.engine import execute as ex
    from fs_bot.board.pieces import count_pieces, get_available
    from fs_bot.board.control import is_controlled_by
    if card_id == 'A65' and not shaded:
        from fs_bot.cards.kinship import default_plan
        return faction in (rc.BELGAE, rc.GERMANS) and bool(default_plan(trial, faction))
    if card_id == 62:
        from fs_bot.cards.war_fleet import np_war_fleet_available
        return np_war_fleet_available(trial, faction)
    if card_id == 6 and not shaded:
        # Marcus Antonius grants two independent optional Roman actions.
        # Existing Auxilia or enemies somewhere on the map do not establish
        # that either action can affect the board (§8.1.1). Scout may create
        # a Battle target, so inspect Battle on its resulting board.
        scout = ex._execute_scout(trial, rc.ROMANS, {
            'sa': rc.SA_SCOUT, 'sa_regions': [], 'details': {}})
        if scout.get('errors') or (scout.get('reason')
                                   and not scout.get('declined_no_effect')):
            return None  # Preserve diagnostics for a malformed Scout plan.
        if scout.get('executed'):
            return True
        plan = ex._card6_battle_plan(trial)
        if plan is None:
            return False
        from fs_bot.battle.losses import calculate_losses
        target = plan['details']['battle_plan'][0]
        # §8.1.1 explicitly excludes a Battle unable to cause enemy Losses.
        # Predict Losses, not removals after random hard-piece saving rolls.
        return calculate_losses(trial, target['region'], rc.ROMANS,
                                target['target'], double_auxilia=True) > 0
    if card_id == 'A37':
        if trial['scenario'] not in rc.ARIOVISTUS_SCENARIOS:
            return False
        if shaded:
            from fs_bot.cards.all_gaul_gathers import removal_options
            return bool(removal_options(trial))
        from fs_bot.cards.all_gaul_gathers import derive_params, execute
        trial['event_params'] = derive_params(trial, faction, False) or {}
        trial['executing_faction'] = faction
        before = get_available(trial, faction, rc.ALLY)
        execute(trial)
        # Aedui's "Move no pieces" instruction leaves only actual legal
        # own Ally placements as an effect. Other owners' discs are not a
        # substitute under §8.2.3's select-yourself-only guideline.
        return get_available(trial, faction, rc.ALLY) < before
    if card_id in (26, 64):
        from fs_bot.cards.ally_events import derive_gobannitio, derive_correus
        from fs_bot.cards.card_effects import execute_card_26, execute_card_64
        before = deepcopy({key: trial[key] for key in ('spaces', 'tribes', 'available')})
        before_allies = sum(count_pieces(trial, region, rc.BELGAE, piece)
                            for region in trial['spaces'] for piece in (rc.ALLY, rc.CITADEL))
        derive = derive_gobannitio if card_id == 26 else derive_correus
        trial['event_params'] = derive(trial, faction, shaded) or {}
        if not trial['event_params'] and not shaded:
            return False
        trial['executing_faction'] = faction
        (execute_card_26 if card_id == 26 else execute_card_64)(trial, shaded)
        if shaded:
            (ex._resolve_card26_arverni_rally if card_id == 26
             else ex._resolve_card64_belgae_rally)(trial)
        if card_id == 64 and shaded and faction == rc.BELGAE:
            # Correus' explicit instruction requires adding Allies+Citadels
            # across the whole Event, including its later Rally.
            return sum(count_pieces(trial, region, rc.BELGAE, piece)
                       for region in trial['spaces'] for piece in (rc.ALLY, rc.CITADEL)) > before_allies
        return {key: trial[key] for key in before} != before
    if card_id == 11 and not shaded:
        return ex._derive_card_11(trial, faction, False) is not None
    if card_id == 25 and not shaded:
        return ex._derive_card_25(trial, faction, False) is not None
    if card_id == 36 and not shaded:
        return ex._card36_battle_target(trial, faction) is not None
    if card_id == 45 and shaded:
        from fs_bot.map.map_data import get_playable_regions_for_state
        return any(count_pieces(trial, region, rc.ROMANS)
                   and (ex._attacker_has_force(trial, region, faction)
                        or ex._attacker_has_force(trial, region, rc.AEDUI))
                   for region in get_playable_regions_for_state(trial, faction))
    if card_id == 21 and shaded:
        # The Senate branch is independent of placement/Battle. With no
        # Control, at least existing or Available Arverni Warbands are needed.
        return (is_controlled_by(trial, rc.PROVINCIA, rc.ARVERNI)
                or get_available(trial, rc.ARVERNI, rc.WARBAND) > 0
                or ex._attacker_has_force(trial, rc.PROVINCIA, rc.ARVERNI))
    if card_id == 'A21':
        region, _ = ex._choose_free_battle(
            trial, faction, ex._free_battle_region_set(trial, 'card_A21_first_no_retreat'))
        return region is not None
    if card_id == 'A45' and shaded and faction == rc.GERMANS:
        from fs_bot.map.map_data import get_playable_regions_for_state
        from fs_bot.board.pieces import count_pieces_by_state
        from fs_bot.bots.german_bot import _select_intimidate_targets
        for region in get_playable_regions_for_state(trial, rc.GERMANS):
            hidden = count_pieces_by_state(trial, region, rc.GERMANS, rc.WARBAND, rc.HIDDEN)
            if hidden and _select_intimidate_targets(trial, region, min(2, hidden)):
                return True
        return False
    if card_id == 'A19' and shaded and faction == rc.GERMANS:
        # Its specific instruction requires the move; eligibility alone
        # cannot make a forbidden NP choice acceptable.
        result = ex._resolve_a19_march_romans(trial, faction)
        return bool(result and result[0].get('executed') is not False)
    if card_id == 'A20':
        if shaded:
            result = ex._resolve_a20_arverni_ambush(trial)
            return bool(result and result[0].get('executed') is not False)
        from fs_bot.map.map_data import get_adjacent_for_state
        near = {rc.VENETI, *get_adjacent_for_state(trial, rc.VENETI)}
        return (any(count_pieces(trial, region, rc.ROMANS) for region in near)
                and bool(count_pieces(trial, rc.VENETI, rc.ARVERNI)
                         or count_pieces(trial, rc.VENETI, rc.ROMANS)))
    if card_id == 17 and not shaded:
        result = ex._resolve_card17_march_ambush(trial, 3)
        return bool(result and result[0].get('executed') is not False)
    if card_id == 58 and shaded:
        result = ex._resolve_card58_german_ambush(trial)
        return bool(result and result[0].get('executed') is not False)
    return None
