"""Surus shaded: the executor's flowchart, actual German mechanics (§8.2.3).

Only the replacement Warbands participate. Named faction objectives remain
native: German arrivals never become Aedui/Belgic Control, and a German Raid
cannot meet a Gallic chart's requirement to gain two Resources (§3.4.3).
Card A51 replaces Surus in Ariovistus; this is the original card's procedure.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_leader_in_region
from fs_bot.board.control import calculate_control
from fs_bot.bots.bot_common import count_faction_allies_and_citadels, roll_die
from fs_bot.cards.divination_np import (
    _action, _bases, _enemies, _march_action, _preview_move, _shuffle_sort,
    _battle_frost_outcomes,
)
from fs_bot.commands.sa_enlist import FREE_FORCE_KEY
from fs_bot.map.map_data import get_adjacent, get_playable_regions_for_state, get_control_value


def _copy(state):
    return deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})


def _native(state):
    """Read strategic objectives without hiding resident German pieces."""
    native = dict(state)
    native.pop(FREE_FORCE_KEY, None)
    return native


def _frost_ok(before, after):
    from fs_bot.bots.bot_common import is_frost_active
    from fs_bot.engine.victory import calculate_victory_margin
    if not is_frost_active(before):
        return True
    # Base Germans have no victory threshold; Arverni do (§7.2).
    for faction in (rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE):
        if faction not in before.get('non_player_factions', set()):
            start = calculate_victory_margin(_native(before), faction)
            end = calculate_victory_margin(_native(after), faction)
            if end > max(0, start):
                return False
    return True


def _prediction(state, region, enemy):
    """Command pre-fire and intrinsic Ambush, with best-case Defender rolls.

    The flowchart's best-case assumption does not suppress Caesar's possible
    Counterattack. The high-value test observes the post-pre-fire force.
    """
    from fs_bot.battle.losses import calculate_losses
    from fs_bot.commands.common import free_action_scope
    from fs_bot.engine.execute import _execute_battle
    from fs_bot.engine.free_actions import _result_error
    trial = _copy(state)
    initial = count_pieces(trial, region, rc.GERMANS)
    initial_enemy = count_pieces(trial, region, enemy)
    high = (rc.LEADER, rc.LEGION, rc.ALLY, rc.CITADEL)
    high_before = sum(count_pieces(trial, region, enemy, p) for p in high)
    pred = {'inflicted': 0, 'taken': 0, 'high': False}

    class RemovalRng:
        caesar = False
        def randint(self, low, high):
            if self.caesar:
                self.caesar = False
                return high
            return low
        def choice(self, values): return values[0]
        def random(self): return 0.0
        def shuffle(self, values): pass

    rng = RemovalRng()
    trial['rng'] = rng
    def observe(phase, board, selected_region, defender, result):
        if phase == 'before':
            losses = calculate_losses(board, region, rc.GERMANS, enemy)
            pred['inflicted'] = initial_enemy - count_pieces(board, region, enemy) + losses
            pred['taken'] = initial - count_pieces(board, region, rc.GERMANS)
            high_now = sum(count_pieces(board, region, enemy, p) for p in high)
            expendable = sum(count_pieces(board, region, enemy, p)
                             for p in (rc.WARBAND, rc.AUXILIA))
            # A Fort is not an A4 high-value target and may absorb repeated
            # Losses, but cannot protect a surviving mobile high-value piece.
            mobile_high = any(count_pieces(board, region, enemy, p)
                              for p in (rc.LEADER, rc.LEGION))
            pred['high'] = (high_now < high_before or (high_now > 0
                and losses > expendable and (mobile_high
                    or not count_pieces(board, region, enemy, rc.FORT))))
            rng.caesar = (get_leader_in_region(board, region, enemy) == rc.CAESAR
                          and not count_pieces(board, region, enemy, rc.FORT)
                          and not count_pieces(board, region, enemy, rc.CITADEL))
        else:
            counter = result.get('counterattack') or {}
            pred['taken'] += counter.get('losses_taken', 0) + counter.get('losses_absorbed', 0)
    with free_action_scope(trial, rc.GERMANS):
        result = _execute_battle(trial, rc.GERMANS, _action(rc.CMD_BATTLE,
            {'battle_plan': [{'region': region, 'target': enemy}]}), _battle_observer=observe)
    return None if _result_error(result) else pred


def _battle(state, chooser, region):
    from fs_bot.commands.sa_ambush import validate_ambush_region
    from fs_bot.bots.bot_common import is_frost_active
    # At most four Warbands, no Leader or Legions: Roman R1 and Arverni V1
    # cannot be triggered by this grant, even if native armies are nearby.
    if chooser not in (rc.AEDUI, rc.BELGAE):
        return None, False
    enemies = _enemies(state, chooser)
    targets = [e for e in enemies if count_pieces(state, region, e)]
    threatened = chooser == rc.BELGAE and count_pieces(state, region, rc.GERMANS, rc.WARBAND) >= 4 and any(
        _bases(state, region, e) or count_pieces(state, region, e, rc.LEGION)
        or count_pieces(state, region, e) >= 4 for e in targets)
    if chooser == rc.BELGAE and not threatened:
        return None, False
    candidates = []
    for enemy in targets:
        if not validate_ambush_region(state, region, rc.GERMANS, enemy)[0]:
            continue
        pred = _prediction(state, region, enemy)
        if pred is None:
            continue
        if chooser == rc.AEDUI:
            favorable = pred['high']  # A4 must first force a high-value Loss.
            key = enemies.index(enemy)
        else:
            favorable = pred['inflicted'] > pred['taken']
            # B_BATTLE first fights the upper-left qualifying enemies, then
            # others. Equal factions are random (§8.5.1, §8.3.4).
            key = not (_bases(state, region, enemy)
                       or count_pieces(state, region, enemy, rc.LEGION)
                       or count_pieces(state, region, enemy) >= 4)
        if favorable and (not is_frost_active(state) or all(
                _frost_ok(state, outcome) for outcome in
                _battle_frost_outcomes(state, region, enemy, command=True))):
            candidates.append((enemy, key))
    if not candidates:
        return None, threatened
    enemy = _shuffle_sort(state, candidates, lambda item: item[1])[0][0]
    return _action(rc.CMD_BATTLE, {'battle_plan': [{'region': region, 'target': enemy}]}), threatened


def _destinations(state, origin):
    playable = set(get_playable_regions_for_state(state, rc.GERMANS))
    return sorted(r for r in get_adjacent(origin) if r in playable)


def _spread(state, chooser, origin):
    # §§8.6.5/8.7.4 leave one Warband and add one Hidden where none. Base
    # §3.4.2 permits ONE moving group to ONE adjacent Region, not a split.
    if count_pieces(state, origin, rc.GERMANS, rc.WARBAND) < 2:
        return None
    if not sum(count_pieces_by_state(state, origin, rc.GERMANS, rc.WARBAND, ps)
               for ps in (rc.HIDDEN, rc.REVEALED)):
        return None
    enemies = _enemies(state, chooser, battle=False)
    native = _native(state)
    totals = {e: count_faction_allies_and_citadels(native, e) for e in enemies}
    options = []
    for dest in _destinations(state, origin):
        if count_pieces_by_state(native, dest, rc.GERMANS, rc.WARBAND, rc.HIDDEN):
            continue
        after = _preview_move(state, origin, dest, {rc.WARBAND: 1})
        if not _frost_ok(state, after):
            continue
        bases = [e for e in enemies if _bases(native, dest, e)]
        key = ((not bool(bases), -max((totals[e] for e in bases), default=0))
               if chooser == rc.AEDUI else 0)
        options.append((dest, key))
    if not options:
        return None
    dest = _shuffle_sort(state, options, lambda item: item[1])[0][0]
    return _march_action([(origin, dest, {rc.WARBAND: 1})])


def _belgic_withdrawal(state, origin):
    native = _native(state)
    group = {rc.WARBAND: count_pieces(state, origin, rc.GERMANS, rc.WARBAND)}
    playable = set(get_playable_regions_for_state(state, rc.GERMANS))
    options = []
    for dest in _destinations(state, origin):
        after = _preview_move(state, origin, dest, group)
        if not _frost_ok(state, after):
            continue
        nearby = sum(count_pieces(native, r, rc.BELGAE) > 0
                     for r in {dest, *get_adjacent(dest)} & playable)
        control = sum(get_control_value(r, state['scenario']) for r in playable
                      if calculate_control(after, r) == rc.BELGIC_CONTROL)
        options.append((dest, (-nearby, -control)))
    if not options:
        return None
    dest = _shuffle_sort(state, options, lambda item: item[1])[0][0]
    return _march_action([(origin, dest, group)])


def _roman_march(state, origin):
    from fs_bot.bots.roman_bot import _rank_march_destinations
    native = _native(state)
    enemies = _enemies(native, rc.ROMANS, battle=False)
    # No commanded Caesar/Legions means no threat origins. The third origin
    # priority permits one Region with no native enemy Ally/Citadel.
    if any(_bases(native, origin, e) for e in enemies):
        return None
    # Resolve legality and Frost protection before choosing a priority tier:
    # an unsafe high-priority destination must not hide a safe lower one.
    groups = {}
    for dest in _destinations(state, origin):
        # §8.8.1 mandates one troop, then most additional troops that do not
        # lose Roman Control or add enemy Control beyond that first departure.
        mandatory = _preview_move(state, origin, dest, {rc.WARBAND: 1})
        baseline = calculate_control(mandatory, origin)
        for number in range(count_pieces(state, origin, rc.GERMANS, rc.WARBAND), 0, -1):
            group = {rc.WARBAND: number}
            after = _preview_move(state, origin, dest, group)
            control = calculate_control(after, origin)
            if baseline == rc.ROMAN_CONTROL and control != rc.ROMAN_CONTROL:
                continue
            if baseline == rc.NO_CONTROL and control not in (rc.ROMAN_CONTROL, rc.NO_CONTROL):
                continue
            if _frost_ok(state, after):
                groups[dest] = group
                break
    destinations = _rank_march_destinations(native, state['scenario'],
        allowed_regions=set(groups), acting_faction=rc.GERMANS)
    if destinations:
        dest = destinations[0][0]
        return _march_action([(origin, dest, groups[dest])])
    return None


def choose_surus_action(state, chooser, region):
    """Choose a concrete free German Command inside Surus's selected-force scope."""
    if state['scenario'] not in rc.BASE_SCENARIOS:
        raise ValueError('Surus is replaced by A51 in Ariovistus')
    if chooser not in (rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE):
        raise ValueError('Surus requires a base-game player executor')
    force = state.get(FREE_FORCE_KEY, {})
    if force.get('source') != 'Surus' or force.get('region') != region:
        raise ValueError('Surus must select only its newly placed German Warbands')
    planning = _copy(state)
    planning['rng'] = state['rng']
    if not count_pieces(planning, region, rc.GERMANS, rc.WARBAND):
        return None
    action, threatened = _battle(planning, chooser, region)
    if action:
        return action
    if chooser == rc.ROMANS:
        return _roman_march(planning, region)
    if chooser == rc.BELGAE and threatened:
        return _belgic_withdrawal(planning, region)
    if chooser == rc.ARVERNI:
        from fs_bot.bots.arverni_bot import node_v4
        if node_v4(_native(planning)) == 'Yes':
            return _spread(planning, chooser, region)
    # Ineligible Rally/Recruit and Event/SoP Pass nodes cannot consume this
    # explicit grant. A low-resource Raid branch ends without an action:
    # actual base Germans gain ZERO Resources, failing every Gallic Raid box.
    if planning.get('resources', {}).get(chooser, 0) <= 3 and roll_die(planning) <= 4:
        return None
    if chooser == rc.AEDUI:
        return _spread(planning, chooser, region)
    # Belgae's bottom March must add native Belgic Control at a destination;
    # Arverni's mass March needs a commanded Leader. Neither can do so here.
    return None
