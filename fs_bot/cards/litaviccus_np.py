"""Numeric 45 Belgic targeting under provisional PR-12.

The printed objective is the most forced Legion Losses; zero means No
Belgae. The owner-adopted forecast follows NP Roman reactions and takes
the lower outcome across a human defender's legal standing/Retreat choices.
Defender Loss rolls remove their targets (§8.5.1), using the existing
physical casualty priority. This forecast is not an official rules ruling.
"""
from copy import deepcopy
from json import dumps
from random import Random

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_leader_in_region
from fs_bot.map.map_data import get_playable_regions_for_state


def _copy(state):
    return deepcopy({key: value for key, value in state.items()
                     if key != 'decision_agent'})


def _signature(state):
    from fs_bot.state.serialize import encode
    return dumps(encode({key: value for key, value in state.items()
                         if key not in ('rng', 'decision_agent')}), sort_keys=True)


def _action(region):
    return {'command': rc.CMD_BATTLE, 'regions': [region],
            'details': {'battle_plan': [{'region': region, 'target': rc.ROMANS}]}}


def _outcomes(state, region, *, frost=False):
    """Run the actual one-Battle grant on detached, explicitly branched boards."""
    from fs_bot.cards.divination_np import _OutcomeBranch, _legal_loss_choices
    from fs_bot.cards.migration import _frost_ok
    from fs_bot.commands.common import free_action_scope
    from fs_bot.battle.retreat import disposition_options, disposition_response
    from fs_bot.engine.agent import AGREEMENT, LOSS_ORDER, RETREAT, RETREAT_DISPOSITION
    from fs_bot.engine.execute import _execute_card45_battle_plan
    from fs_bot.engine.free_actions import _result_error

    initial_legions = sum(count_pieces(state, r, rc.ROMANS, rc.LEGION)
                          for r in state['spaces'])
    scripts, branched, completed = [()], set(), set()
    while scripts:
        script = scripts.pop()
        sim = _copy(state)
        sim['non_player_factions'] = set(sim.get('non_player_factions', ())) | {rc.BELGAE}
        # Actual synthetic human responses must govern prospective loans,
        # rather than the generic Diviciacus preview's automatic agreement.
        sim.pop('_diviciacus_preview', None)
        action = _action(region)
        taken, inflicted, ambiorix_risk = 0, 0, False
        prefire_requested, battle_started = 0, False

        class ForecastRng(Random):
            def __init__(self):
                super().__init__(0)
                self.index, self.owner, self.caesar_pending = 0, None, False
                self.roll_index = 0
                self.remaining, self.selected = None, None
                self.reactions = []

            def choose(self, options, stage):
                if len(options) == 1:
                    return options[0]
                if self.index < len(script):
                    selected = script[self.index]
                    self.index += 1
                    if stage[0] in ('agreement', 'retreat'):
                        self.reactions.append((stage, selected))
                    return selected
                key = (stage, _signature(sim), self.owner,
                       self.caesar_pending, self.roll_index, self.remaining,
                       self.selected, tuple(options), tuple(self.reactions),
                       taken, inflicted, ambiorix_risk,
                       prefire_requested, battle_started)
                raise _OutcomeBranch(key, options)

            def randint(self, low, high):
                self.roll_index += 1
                if self.caesar_pending:
                    # Caesar's Ambush escape is a separate die, not a
                    # Defender Loss roll covered by the printed assumption.
                    self.caesar_pending = False
                    return self.choose((low, high), ('caesar',))
                if not frost and self.owner == rc.ROMANS:
                    return low
                return self.choose((low, high), ('save', self.owner))

            def choice(self, values):
                options = tuple(dict.fromkeys(values))
                return self.choose(options, ('tie',)) if frost else values[0]

            def random(self):
                return 0.0

            def shuffle(self, values):
                if frost and values:
                    # The loss priority is rebuilt for every individual
                    # Loss. Branch its first equal-priority absorber, not
                    # factorial permutations of an unused remainder.
                    options = tuple(dict.fromkeys(values))
                    first = self.choose(options, ('loss_tie',))
                    index = values.index(first)
                    values[0], values[index] = values[index], values[0]

        rng = sim['rng'] = ForecastRng()

        def agent(board, faction, request):
            nonlocal prefire_requested, ambiorix_risk
            kind = request.get('kind')
            npc = faction in sim.get('non_player_factions', ())
            if kind == AGREEMENT and not npc:
                return rng.choose((False, True),
                                  ('agreement', faction, dumps(request, sort_keys=True)))
            if kind == RETREAT:
                if not npc:
                    return {'retreat': rng.choose((False, True),
                            ('retreat', faction, dumps(request, sort_keys=True)))}
                return None  # The canonical Roman NP Retreat policy.
            if kind == RETREAT_DISPOSITION and not npc:
                return disposition_response(rng.choose(disposition_options(request),
                    ('retreat', faction, dumps(request, sort_keys=True))))
            if kind == LOSS_ORDER:
                rng.owner = faction
                rng.remaining = request['num_losses']
                chosen = tuple(request['pieces'][0])
                if frost and not npc:
                    chosen = rng.choose(
                        _legal_loss_choices(board, request['region'], faction, request),
                        ('piece', faction, request['region']))
                rng.selected = chosen
                if faction == rc.BELGAE:
                    if not battle_started:
                        # Numeric 13's Roman Auxilia fire once before this
                        # Battle. Keep the full requested total, even if
                        # fewer attackers remain to absorb it.
                        prefire_requested = max(prefire_requested, request['num_losses'])
                    if (chosen[0] == rc.LEADER
                            and (len(chosen) < 3 or chosen[2] == rc.BELGAE)
                            and get_leader_in_region(board, region, rc.BELGAE) == rc.AMBIORIX):
                        ambiorix_risk = True
                return [chosen]
            return None

        sim['decision_agent'] = agent

        def observe(phase, board, place, enemy, result):
            nonlocal taken, inflicted, battle_started
            if phase == 'before':
                battle_started = True
                # This boundary follows prefire. Ambush skips the Retreat
                # callback, and Abatis can roll before LOSS_ORDER: identify
                # the Roman Defender now so its saves use §8.5.1 as well.
                rng.owner = rc.ROMANS
                rng.caesar_pending = (
                    result['is_ambush']
                    and get_leader_in_region(board, place, rc.ROMANS) == rc.CAESAR
                    and not count_pieces(board, place, rc.ROMANS, rc.FORT)
                    and not count_pieces(board, place, rc.ROMANS, rc.CITADEL))
            elif phase == 'after':
                attack = result.get('attack') or {}
                counterattack = result.get('counterattack') or {}
                # §8.5.1 compares caused Losses, not the number of targets
                # still available to absorb those Losses.
                inflicted = attack.get('losses_requested', 0)
                taken = prefire_requested + counterattack.get('losses_requested', 0)

        try:
            with free_action_scope(sim, rc.BELGAE):
                result = _execute_card45_battle_plan(
                    sim, rc.BELGAE, action, _battle_observer=observe)
            error = _result_error(result)
            if error:
                raise ValueError(f'Litaviccus Battle forecast failed: {error}')
        except _OutcomeBranch as branch:
            if branch.key not in branched:
                branched.add(branch.key)
                scripts.extend(script + (option,) for option in branch.options)
            continue
        final_legions = sum(count_pieces(sim, r, rc.ROMANS, rc.LEGION)
                            for r in sim['spaces'])
        outcome = (initial_legions - final_legions,
                   inflicted > taken and not ambiorix_risk,
                   not frost or _frost_ok(state, sim))
        if outcome not in completed:
            completed.add(outcome)
            yield outcome


def predicted_legion_losses(state, region):
    """Pure PR-12 forecast; live human choices and dice are never consumed."""
    outcomes = list(_outcomes(state, region))
    return min((score for score, _, _ in outcomes), default=0)


def plan(state, *, choose=False):
    """One target, or None for No Belgae; only live equal-priority ties roll."""
    if state['scenario'] not in rc.BASE_SCENARIOS:
        return None
    from fs_bot.bots.bot_common import random_select
    from fs_bot.engine.game_engine import is_frost, get_sop_factions
    frost = (state.get('frost') or is_frost(state)) and any(
        faction not in state.get('non_player_factions', ())
        for faction in get_sop_factions(state))
    best, regions = 0, []
    for region in sorted(get_playable_regions_for_state(state, rc.BELGAE)):
        if (not count_pieces(state, region, rc.ROMANS, rc.LEGION)
                or not (count_pieces(state, region, rc.BELGAE)
                        or count_pieces(state, region, rc.AEDUI))):
            continue
        outcomes = list(_outcomes(state, region))
        score = min((score for score, _, _ in outcomes), default=0)
        if not score or score < best or any(not safe for _, safe, _ in outcomes):
            continue
        if frost and any(not permitted for _, _, permitted in _outcomes(state, region, frost=True)):
            continue
        if score > best:
            best, regions = score, [region]
        else:
            regions.append(region)
    if not regions:
        return None
    region = random_select(state, regions) if choose and len(regions) > 1 else regions[0]
    return {'region': region, 'predicted_legion_losses': best}


def available(state):
    return plan(state) is not None
