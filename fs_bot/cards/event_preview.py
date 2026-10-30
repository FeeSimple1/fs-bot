"""Pure previews of completed Event steps for successive human choices."""
from copy import deepcopy


class EventPreviewReached(BaseException):
    """Carry the reached board through an Event's ordinary atomic rollback."""

    def __init__(self, state):
        self.state = deepcopy({key: value for key, value in state.items()
                               if key not in ('decision_agent',
                                              '_action_window_preview_checkpoint')})
        self.state['_diviciacus_preview'] = True
        super().__init__('Event planning checkpoint reached')


class EventStepUnavailable(ValueError):
    pass


def preview_event_prefix(state, faction, card_id, shaded, params, *, step, index):
    """Return the actual board immediately before the next authored operation.

    Earlier choices and timing actions execute only on a detached board.
    The empty next-index tail exposes a checkpoint without adding a fake
    placement or executing the Event's later grants and effects.
    """
    from fs_bot.cards.card_effects import execute_event
    from fs_bot.engine.action_windows import scope
    sim = deepcopy({key: value for key, value in state.items()
                    if key != 'decision_agent'})
    sim['_diviciacus_preview'] = True
    sim['_action_window_preview_checkpoint'] = {
        'stage': 'event_step', 'step': step, 'index': index}
    sim['executing_faction'] = faction
    sim['event_params'] = deepcopy(params)
    staged = sim['event_params'].setdefault('stage_timing_actions', {})
    staged[f'{step}:{index}'] = []
    try:
        with scope(sim, actor=faction, phase='sequence_of_play', force=True):
            execute_event(sim, card_id, shaded=shaded)
    except EventPreviewReached as reached:
        return reached.state
    raise EventStepUnavailable('This Event side does not use the selected step.')
