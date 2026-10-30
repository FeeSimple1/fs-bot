"""Explicit action timing on detached human planning boards.

The returned choices travel with the plan and are revalidated on execution.
No planning choice consumes the live board, decision agent, or random stream.
"""

from contextlib import contextmanager
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.cli import menus
from fs_bot.cli.display import HumanTurnDisplay, format_board
from fs_bot.engine import action_windows, spring, voluntary_removal


def available(state):
    return bool(state.get('_cli_action_windows') or action_windows.enabled(state))


def planning_copy(state):
    result = deepcopy({key: value for key, value in state.items()
                       if key != 'decision_agent'})
    result['_diviciacus_preview'] = True
    if available(state):
        result['_cli_action_windows'] = True
    return result


@contextmanager
def inspect_board(state, stdout):
    """Keep board/b inspection on the board actually used by this menu."""
    previous = menus._BOARD_HOOK[0]
    menus.set_board_hook(lambda: stdout.write('\n' + format_board(state) + '\n'))
    try:
        yield
    finally:
        menus.set_board_hook(previous)


def apply_planned(state, faction, actions, *, stage, **context):
    """Apply an authored list exactly once to a detached planning board."""
    if not actions:
        return []
    # Nonempty authored data opens a scope without enabling live prompts.
    existing_scope = action_windows.SCOPE in state
    with action_windows.scope(state, actor=faction,
                              plan={action_windows.FIELD: actions},
                              phase='sequence_of_play'):
        effects = action_windows.apply_authored(
            state, faction, actions,
            context={'stage': stage, 'phase': 'sequence_of_play', **context})
        cohorts = deepcopy(state.get(action_windows.COHORTS))
    # A collector's moved/selected ledger lives across many small planning
    # windows. Closing our temporary authority frame must not resurrect the
    # cohort counters just removed from this same detached board.
    if not existing_scope:
        if cohorts is None:
            state.pop(action_windows.COHORTS, None)
        else:
            state[action_windows.COHORTS] = cohorts
    return effects


def prepare(state, faction, stdin, stdout, *, stage, **context):
    """Return (preview, choices) before a menu computes pools or legality.

    Legacy/raw collectors remain input-compatible unless their frontend has
    explicitly opted into the new timing protocol.
    """
    if not available(state):
        return state, []
    sim = planning_copy(state)
    actions = []
    window = {'stage': stage, 'phase': 'sequence_of_play', **context}
    view = HumanTurnDisplay(stdout)
    view.remember(state, (faction,))
    frame = state.get(action_windows.SCOPE)
    actor = frame.get('actor') if frame is not None else faction
    with inspect_board(sim, stdout):
        request = (voluntary_removal.make_request(
                       sim, faction, window=window,
                       cohorts=action_windows._combined_cohorts(sim, faction, None))
                   if actor == faction else None)
        if request is not None:
            from fs_bot.cli.voluntary_removal import collect_removals
            stdout.write('\nPlanning preview before the next operation:\n')
            view.before_decision(sim, faction)
            response = collect_removals(sim, faction, request, stdin, stdout)
            choice = {'kind': voluntary_removal.KIND, 'response': response}
            apply_planned(sim, faction, [choice], stage=stage, **context)
            actions.append(choice)
        # Authored plans can choose only their own Leader's entry. Another
        # human Arverni seat receives its independent live reactive request.
        view_state = dict(sim)
        view_state.pop('_diviciacus_preview', None)
        request = (spring.mid_action_request(view_state, window)
                   if faction == rc.ARVERNI else None)
        if request is not None:
            if not actions:
                stdout.write('\nPlanning preview before the next operation:\n')
            view.before_decision(sim, faction)
            options = [('Leave in the Spring box for now', None)]
            options.extend((region, region) for region in request['legal_regions'])
            region = menus.prompt_choice(stdin, stdout,
                'Vercingetorix entry before this next step?', options)
            response = {'defer': True} if region is None else {'region': region}
            choice = {'kind': spring.KIND, 'response': response}
            apply_planned(sim, faction, [choice], stage=stage, **context)
            actions.append(choice)
        if actions:
            view.before_decision(sim, faction)
    return sim, actions
