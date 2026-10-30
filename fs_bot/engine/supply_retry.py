"""Retain a real PR-07 refusal when §8.6.6 lets human Rome rechoose.

Only the engine writes these receipts. Ordinary invalid plans and paused
decisions retain full rollback. A replayable refusal records the attempted
plan in the frontend, rather than trusting a player-supplied random result.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc

RECEIPT = 'np_aedui_supply_reply'
RECONSIDERATION = 'supply_reconsideration'


def current_receipt(state):
    turn = state.get('_card_turn')
    if not isinstance(turn, dict):
        return None
    receipt = turn.get(RECEIPT)
    return receipt if receipt and receipt['actor_index'] == turn.get('idx') else None


def resolve_np_supply(state, controller, requester):
    """Resolve policy once; only actual uncertain Aedui dice get a receipt."""
    from fs_bot.bots.bot_common import np_agrees_to_supply_line
    from fs_bot.commands.rally import np_aedui_supply_key
    relevant = np_aedui_supply_key(state, requester, controller) is not None
    receipt = current_receipt(state) if relevant else None
    if receipt is not None:
        return receipt['answer']
    before = state['rng'].getstate()
    answer = np_agrees_to_supply_line(controller, requester, state)
    after = state['rng'].getstate()
    if (relevant and before != after and '_card_turn' in state
            and not state.get('_diviciacus_preview')):
        state['_card_turn'][RECEIPT] = {
            'answer': bool(answer), 'actor_index': state['_card_turn'].get('idx'),
            'rng_before': before, 'rng_after': after,
        }
    return answer


def reconsideration_for_failure(state, snapshot, faction, action):
    """Identify a fresh refusal that prevented an otherwise legal Command."""
    if state.get('_diviciacus_preview') or faction != rc.ROMANS:
        return None
    receipt = current_receipt(state)
    if (not receipt or receipt['answer'] or current_receipt(snapshot) is not None):
        return None
    from fs_bot.engine.moves import validate_player_action
    allowed, preview = validate_player_action(snapshot, faction, action)
    if not allowed or not isinstance(preview, dict) or preview.get('errors'):
        return None
    return deepcopy(receipt)


def retain_reconsideration(state, receipt):
    """Restore only the refusal and the RNG through that genuine die roll."""
    turn = state.get('_card_turn')
    if turn is None or turn.get('idx') != receipt['actor_index']:
        raise RuntimeError('Supply reconsideration does not match the current decision')
    turn[RECEIPT] = deepcopy(receipt)
    state['rng'].setstate(receipt['rng_after'])
