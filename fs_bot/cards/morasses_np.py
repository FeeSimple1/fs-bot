"""Detached, exhaustive outcomes for Morasses' §8.4.4 Frost restriction."""
from copy import deepcopy
from json import dumps

from fs_bot.cards.divination_np import _OutcomeBranch, _legal_loss_choices, _game_run_arverni
from fs_bot.state.serialize import encode


def outcomes(state, faction, run):
    """Real Command execution, branching at rolls and legal player decisions.

    Rejoin identical loss continuations using the board, remaining Losses and
    selected absorber. An Ambush's Caesar roll is also an ordinary endpoint
    branch; normal Battles in the same Aedui Command can Retreat or Counterattack.
    """
    scripts, visited, completed = [()], set(), set()
    while scripts:
        script = scripts.pop()
        sim = deepcopy({k:v for k,v in state.items() if k != 'decision_agent'})
        context = [None, None, None, None]
        decisions = []
        class Rng:
            index = 0
            def choose(self, options, stage):
                if len(options) == 1:
                    return options[0]
                if self.index < len(script):
                    result = script[self.index]
                    self.index += 1
                    return result
                board = dumps(encode({k:v for k,v in sim.items()
                                      if k not in ('rng', 'decision_agent')}), sort_keys=True)
                raise _OutcomeBranch((stage, board, tuple(context), tuple(decisions), tuple(options)), options)
            def randint(self, low, high):
                return self.choose((low, high), 'roll')
            def choice(self, values): return values[0]
            def random(self): return 0.0
            def shuffle(self, values): pass
        rng = Rng()
        sim['rng'] = rng
        def agent(board, actor, request):
            kind = request.get('kind')
            np = (actor in state.get('non_player_factions', set())
                  or _game_run_arverni(state, actor))
            if kind == 'loss_order':
                context[:] = [actor, request['region'], request['num_losses'], None]
                choice = (tuple(request['pieces'][0]) if np else rng.choose(
                    _legal_loss_choices(board, request['region'], actor, request), 'loss'))
                context[-1] = choice
                return None if np else [choice]
            if np:
                return None
            if kind == 'agreement':
                identity = dumps(encode(dict(request, faction=actor)), sort_keys=True)
                answer = rng.choose((False, True), ('agreement', identity))
                decisions.append((identity, answer))
                return answer
            if kind == 'retreat':
                identity = dumps(encode(dict(request, faction=actor)), sort_keys=True)
                choice = rng.choose((None, *request.get('legal_regions', [])), ('retreat', identity))
                decisions.append((identity, choice))
                return {'retreat': choice is not None, 'region': choice}
            return None
        sim['decision_agent'] = agent
        try:
            result = run(sim)
        except _OutcomeBranch as branch:
            if branch.key not in visited:
                visited.add(branch.key)
                scripts.extend(script + (choice,) for choice in branch.options)
            continue
        from fs_bot.engine.free_actions import _result_error
        error = _result_error(result)
        if error:
            raise ValueError(f'Invalid Morasses outcome preview: {error}')
        sim.pop('decision_agent', None)
        signature = dumps(encode({k:v for k,v in sim.items() if k != 'rng'}), sort_keys=True)
        if signature not in completed:
            completed.add(signature)
            yield sim


def frost_restricted(state):
    from fs_bot.engine.game_engine import is_frost, get_sop_factions
    return ((state.get('frost') or is_frost(state))
            and bool(set(get_sop_factions(state)) - set(state.get('non_player_factions', set()))))


def safe(state, faction, run):
    if not frost_restricted(state):
        return True
    from fs_bot.cards.impetuosity import _frost_ok
    found = False
    for outcome in outcomes(state, faction, run):
        found = True
        if not _frost_ok(state, outcome):
            return False
    if not found:
        raise ValueError('Morasses outcome preview produced no completed board')
    return True


def safe_battle_plan(state, faction, action):
    """Keep each next priority only when the entire Command remains safe.

    The Command is previewed whole, so Card13/59 remain once per Command;
    repeated safe individual Battles may not collectively cross victory.
    """
    if not frost_restricted(state):
        return action
    from fs_bot.cards.morasses import battle_request, _battle_action
    from fs_bot.engine.free_actions import execute_free_action_plan
    selected = []
    for entry in action['details']['battle_plan']:
        candidate = selected + [entry]
        regions = {e['region'] for e in candidate}
        ambush = [r for r in action['sa_regions'] if r in regions]
        trial_action = _battle_action(candidate, ambush)
        if safe(state, faction, lambda board: execute_free_action_plan(
                board, faction, battle_request(), trial_action)):
            selected = candidate
    if not selected:
        return None
    from fs_bot.rules_consts import AEDUI
    if faction == AEDUI:
        selected_regions = {e['region'] for e in selected}
        if (not any(r in selected_regions for r in action['sa_regions'])
                or not any(e.get('priority') == 'high_value' for e in selected)):
            return None  # Keep both the grant and §8.6.2's initial condition.
    regions = {e['region'] for e in selected}
    return _battle_action(selected, [r for r in action['sa_regions'] if r in regions])
