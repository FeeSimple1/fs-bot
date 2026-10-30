"""Optional human choices at complete rules-procedure boundaries.

The outer Sequence-of-Play executor owns voluntary removal (§1.4.1).
Unlocked boxed Vercingetorix belongs to the Arverni independently of that
executor. Piece helpers never open windows inside an atomic operation.
"""
from contextlib import contextmanager
from copy import deepcopy
from functools import wraps

from fs_bot import rules_consts as rc

SCOPE = '_action_window_scope'
BUSY = '_action_window_busy'
FIELD = 'timing_actions'
COHORTS = '_action_window_cohorts'


def set_cohorts(state, key, faction, cohorts):
    """Register an Event's exact participating pieces across later windows.

    The ledger contains data only, so detached previews and durable replay
    reconstruct the same physical membership without live callbacks.
    Callers update its Regions/visibility after their own moves or flips.
    """
    from fs_bot.engine.voluntary_removal import _checked_cohorts
    state.setdefault(COHORTS, {})[key] = {
        'faction': faction, 'pieces': _checked_cohorts(cohorts)}


def get_cohorts(state, key):
    return deepcopy(state.get(COHORTS, {}).get(key, {}).get('pieces', []))


def clear_cohorts(state, key):
    state.get(COHORTS, {}).pop(key, None)
    if not state.get(COHORTS):
        state.pop(COHORTS, None)


def _combined_cohorts(state, faction, local):
    result = list(local or [])
    for ledger in state.get(COHORTS, {}).values():
        if ledger['faction'] == faction:
            result.extend(ledger['pieces'])
    return result


def _advance(cohorts, effects):
    from fs_bot.engine.voluntary_removal import advance_cohorts
    ids = {c['id'] for c in cohorts or []}
    return advance_cohorts(cohorts, [e for e in effects if e.get('cohort') in ids])


def _advance_registered(state, effects):
    for ledger in state.get(COHORTS, {}).values():
        ledger['pieces'] = _advance(ledger['pieces'], effects)


def enabled(state):
    agent = state.get('decision_agent')
    return bool(getattr(agent, 'supports_action_windows', False)
                or getattr(getattr(agent, '__self__', None),
                           'supports_action_windows', False))


def is_preview(state):
    return bool(state.get('_diviciacus_preview'))


def interactive(state):
    return enabled(state) and SCOPE in state and not is_preview(state)


def has_authored(value):
    if isinstance(value, dict):
        return (bool(value.get(FIELD)) or bool(value.get('stage_timing_actions'))
                or bool(value.get('after_command_timing_actions'))
                or bool(value.get('after_sa_timing_actions'))
                or bool(value.get('movement_timing_actions'))
                or bool(value.get('raid_timing_actions'))
                or any(has_authored(v) for v in value.values()))
    if isinstance(value, (list, tuple)):
        return any(has_authored(v) for v in value)
    return False


@contextmanager
def scope(state, *, actor=None, plan=None, phase='action', force=False,
          override=False):
    """Only trusted outer orchestration creates removal authority."""
    if ((SCOPE in state and not override)
            or not (force or enabled(state) or has_authored(plan))):
        yield
        return
    if actor in state.get('non_player_factions', ()):
        actor = None
    previous = state.get(SCOPE)
    previous_cohorts = deepcopy(state.get(COHORTS))
    state[SCOPE] = {'actor': actor, 'phase': phase}
    try:
        yield
    finally:
        if previous is None:
            state.pop(SCOPE, None)
        else:
            state[SCOPE] = previous
        if previous_cohorts is None:
            state.pop(COHORTS, None)
        else:
            state[COHORTS] = previous_cohorts


def sop_action(function):
    @wraps(function)
    def wrapped(state, faction, decision, *args, **kwargs):
        plan = decision.get('player_action') or decision.get('bot_action') or {}
        actor = (faction if decision.get('player_action') is not None
                 and not decision.get('bot_action') else None)
        with scope(state, actor=actor, plan=plan, phase='sequence_of_play'):
            return function(state, faction, decision, *args, **kwargs)
    return wrapped


def _spring_request(state, context, *, authored=False):
    from fs_bot.engine.spring import mid_action_request
    if authored and is_preview(state):
        # Eligibility is identical; only automatic prompting is disabled in a
        # preview. The explicit placement still has to be simulated there.
        view = dict(state)
        view.pop('_diviciacus_preview', None)
        return mid_action_request(view, context)
    return mid_action_request(state, context)


def apply_authored(state, author, actions, *, context=None, cohorts=None):
    """Execute explicit choices on either a live or detached planning board."""
    from fs_bot.commands.common import CommandError
    from fs_bot.engine import spring, voluntary_removal
    if not isinstance(actions, list):
        raise CommandError('timing_actions must be an ordered list')
    effects = []
    for entry in actions:
        if not isinstance(entry, dict) or set(entry) != {'kind', 'response'}:
            raise CommandError('Each timing action needs kind and response')
        kind, response = entry['kind'], entry['response']
        if kind == 'voluntary_removal':
            if state.get(SCOPE, {}).get('actor') != author:
                raise CommandError('Only the executing player may remove its own pieces')
            combined = _combined_cohorts(state, author, cohorts)
            request = voluntary_removal.make_request(state, author, window=context,
                                                      cohorts=combined)
            if request is None:
                if response in ({'done': True}, {'use_default': True}):
                    continue
                raise CommandError('No voluntary removal is available at this window')
            applied = voluntary_removal.apply_response(
                state, request, response, cohorts=combined)
            effects.extend(applied)
            cohorts = _advance(cohorts, applied)
            _advance_registered(state, applied)
        elif kind == spring.KIND:
            if author != rc.ARVERNI:
                raise CommandError('Only the Arverni player may choose Vercingetorix entry')
            if response == {'defer': True}:
                # A preceding live window may already have placed him. A
                # recorded choice to do nothing does not become a new entry.
                continue
            request = _spring_request(state, context, authored=True)
            if request is None:
                raise CommandError('Vercingetorix entry is not available at this window')
            # Authored previews never use a random/default placement.
            if not isinstance(response, dict) or not (
                    set(response) == {'region'} or response == {'defer': True}):
                raise CommandError('Authored Leader timing must choose a Region or defer')
            spring.resolve_spring_box_entry(state, response)
        else:
            raise CommandError('Unknown timing action kind')
    return effects


def window(state, stage, *, author=None, timing_actions=None, cohorts=None,
           on_removal=None, prompt=True, **details):
    """Offer choices before a caller computes its next legal operation.

    ``cohorts`` and ``on_removal`` are trusted live-operation adapters, never
    player-authored fields. A caller must preserve determined die results
    and completed effects while rebuilding subsequent legal choices.
    """
    if state.get(BUSY):
        return []
    if SCOPE not in state:
        if timing_actions:
            from fs_bot.commands.common import CommandError
            raise CommandError('Authored timing requires an active Command, Event, or phase scope')
        return []
    frame = state[SCOPE]
    context = {'stage': stage, 'phase': frame['phase'], **details}
    checkpoint = state.get('_action_window_preview_checkpoint')
    if (is_preview(state) and isinstance(checkpoint, dict)
            and all(context.get(key) == value for key, value in checkpoint.items())):
        from fs_bot.cards.event_preview import EventPreviewReached
        raise EventPreviewReached(state)
    effects = []
    state[BUSY] = True
    try:
        from fs_bot.engine import spring, voluntary_removal
        authored_kinds = set()
        if timing_actions is not None:
            effects = apply_authored(state, author, timing_actions,
                                     context=context, cohorts=cohorts)
            authored_kinds = {entry['kind'] for entry in timing_actions}
            if effects and on_removal:
                on_removal(effects)
            cohorts = _advance(cohorts, effects)
        if not prompt or is_preview(state) or not enabled(state):
            return effects
        from fs_bot.engine.agent import consult_agent
        while True:
            changed = False
            actor = frame.get('actor')
            if actor is not None and 'voluntary_removal' not in authored_kinds:
                combined = _combined_cohorts(state, actor, cohorts)
                request = voluntary_removal.make_request(state, actor, window=context,
                                                          cohorts=combined)
                if request is not None:
                    answer = consult_agent(state, actor, request)
                    if answer is not None:
                        applied = voluntary_removal.apply_response(
                            state, request, answer, cohorts=combined)
                        effects.extend(applied)
                        if applied and on_removal:
                            on_removal(applied)
                        cohorts = _advance(cohorts, applied)
                        _advance_registered(state, applied)
                        changed = bool(applied)
            request = (None if spring.KIND in authored_kinds
                       else _spring_request(state, context))
            if request is not None:
                answer = consult_agent(state, rc.ARVERNI, request)
                result = spring.resolve_mid_action_entry(state, request, answer)
                changed = changed or bool(result and not result.get('deferred'))
            if not changed:
                return effects
            # Each changed board gives the other eligible player an opportunity.
            authored_kinds.clear()
    finally:
        state.pop(BUSY, None)
