"""
Scout Special Ability — §4.2.2 (Roman).

Scout may accompany any type of Command. No Britannia (§4.1.3).

Two capabilities:
1. Scout Movement: Move Auxilia from any Regions to adjacent Regions
   (even if no Leader nearby). Revealed stay Revealed, Hidden stay Hidden.
   No piece may move more than once. Cannot move into or out of Britannia.

2. Scout Reveal: In Regions within one of Caesar or with Successor —
   each Hidden Auxilia may flip to Revealed to Reveal up to two Warbands
   in that Region, placing Scouted markers on them.

Reference: §4.2.2, §4.1.2, §4.1.3, A4.2
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS,
    # Piece types
    AUXILIA, WARBAND, FLIPPABLE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    CAESAR,
    # Regions
    BRITANNIA,
    # Scenarios
    ARIOVISTUS_SCENARIOS,
    # Markers
    MARKER_SCOUTED,
)
from fs_bot.board.pieces import (
    count_pieces_by_state,
    move_piece, flip_piece,
)
from fs_bot.map.map_data import is_adjacent, get_adjacent
from fs_bot.commands.common import CommandError, check_leader_proximity


def clear_scout_cohorts(state):
    from fs_bot import rules_consts as rc
    from fs_bot.engine.action_windows import clear_cohorts
    for owner in (ROMANS, rc.AEDUI):
        clear_cohorts(state, f'scout:{owner}')


def scout_moved_count(state, region, visibility, owner=None):
    from fs_bot import rules_consts as rc
    from fs_bot.engine.action_windows import get_cohorts
    owners = (owner,) if owner is not None else (ROMANS, rc.AEDUI)
    return sum(c['count'] for faction in owners
               for c in get_cohorts(state, f'scout:{faction}')
               if c['region'] == region and c.get('piece_state') == visibility)


def scout_movement_step(state, move, *, index=0):
    """One Scout move, reserving the exact pieces that have already moved."""
    from fs_bot import rules_consts as rc
    from fs_bot.engine.action_windows import window, get_cohorts, set_cohorts
    from fs_bot.engine.diviciacus import KEY, choose_owners, validate_response
    origin, target = move['from_region'], move['to_region']
    count, visibility = move['count'], move['piece_state']
    window(state, 'scout_move', author=ROMANS, index=index,
           from_region=origin, to_region=target,
           timing_actions=move.get('timing_actions'))
    if type(count) is not int or count < 1 or visibility not in (HIDDEN, REVEALED):
        raise CommandError('Scout needs a positive count of Hidden or Revealed Auxilia')
    if origin == BRITANNIA or target == BRITANNIA:
        raise CommandError('Scout movement cannot move into or out of Britannia (§4.1.3)')
    if not is_adjacent(origin, target):
        raise CommandError(f'{origin} and {target} are not adjacent')
    context = state.get(KEY, {})
    borrowed = (context.get('faction') == ROMANS
                and origin in context.get('pieces', {}))
    raw = state['spaces'][origin].get('pieces', {})
    available = {ROMANS: raw.get(ROMANS, {}).get(visibility, {}).get(AUXILIA, 0)
                 - scout_moved_count(state, origin, visibility, ROMANS)}
    if borrowed:
        available[rc.AEDUI] = (context['pieces'][origin].get(visibility, 0)
                              - scout_moved_count(state, origin, visibility, rc.AEDUI))
    if min(available.values()) < 0 or sum(available.values()) < count:
        raise CommandError(f'Not enough unmoved {visibility} Auxilia in {origin}; '
                           'no Scout piece may move twice (§4.2.2)')
    selected = move.get('physical_owners')
    if selected is not None:
        try:
            validate_response({'available': available, 'count': count}, {'counts': selected})
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        allocation = selected
    elif borrowed:
        allocation = choose_owners(state, ROMANS, origin, count, available, 'scout_movement')
    else:
        allocation = {ROMANS: count}
    for owner, amount in allocation.items():
        if not amount:
            continue
        move_piece(state, origin, target, ROMANS, AUXILIA, count=amount,
                   piece_state=visibility, physical_owner=owner if borrowed else None)
        ledger = get_cohorts(state, f'scout:{owner}')
        identifier = f'scout:{owner}:{target}:{visibility}'
        item = next((c for c in ledger if c['id'] == identifier), None)
        if item is None:
            item = {'id': identifier, 'label': 'Already moved by Scout',
                    'region': target, 'piece_type': AUXILIA if owner == ROMANS else WARBAND,
                    'piece_state': visibility, 'count': 0}
            if owner != ROMANS:
                item['loan_kind'] = 'diviciacus'
            ledger.append(item)
        item['count'] += amount
        set_cohorts(state, f'scout:{owner}', owner, ledger)
    return (origin, target, count, visibility)


def scout_move(state, movements, *, after_movements=None):
    """Execute Scout movement — move Auxilia to adjacent Regions.

    §4.2.2: "Move Auxilia as desired from any Regions to adjacent Regions,
    but not into or out of Britannia (Revealed stay Revealed, Hidden stay
    Hidden; no piece may move more than once)."

    No Leader proximity requirement for Scout movement.

    Args:
        state: Game state dict. Modified in place.
        movements: List of dicts, each with:
            "from_region": Source region.
            "to_region": Destination region.
            "count": Number of Auxilia to move.
            "piece_state": HIDDEN or REVEALED.

    Returns:
        dict with:
            "moved": List of (from_region, to_region, count, piece_state).

    Raises:
        CommandError: If movement violates rules.
    """
    from copy import deepcopy
    saved = deepcopy({key: value for key, value in state.items()
                      if key not in ('decision_agent', '_card_turn')})
    agent, card_turn = state.get('decision_agent'), state.get('_card_turn')
    clear_scout_cohorts(state)
    try:
        result = {'moved': [scout_movement_step(state, move, index=index)
                           for index, move in enumerate(movements)]}
        from fs_bot.engine.action_windows import window
        window(state, 'scout_movement_complete', author=ROMANS,
               timing_actions=after_movements)
        return result
    except BaseException:
        state.clear()
        state.update(saved)
        if agent is not None:
            state['decision_agent'] = agent
        if card_turn is not None:
            state['_card_turn'] = card_turn
        raise
    finally:
        clear_scout_cohorts(state)


def scout_reveal(state, region, auxilia_count, targets):
    """Execute Scout reveal — flip Auxilia to Revealed to Reveal Warbands.

    §4.2.2: "each Hidden Auxilia piece may flip to Revealed in order to
    Reveal up to two Warbands (flip from Hidden to Revealed, or leave
    Revealed, 1.4.3) in that Region and place Scouted markers on them"

    Requires region within one of Caesar or with Successor.

    Args:
        state: Game state dict. Modified in place.
        region: Region where Scout Reveal occurs.
        auxilia_count: Number of Hidden Auxilia to flip to Revealed.
        targets: List of dicts, each with:
            "faction": Faction whose Warbands to reveal.
            "count": Number of Warbands to reveal (max 2 per Auxilia
                flipped).

    Returns:
        dict with:
            "auxilia_flipped": Number of Auxilia flipped.
            "warbands_revealed": List of (faction, count) revealed.
            "scouted_placed": List of (faction, count) Scouted markers.

    Raises:
        CommandError: If reveal violates rules.
    """
    scenario = state["scenario"]

    # Check Leader proximity — within 1 of Caesar or with Successor
    valid, reason = check_leader_proximity(
        state, region, ROMANS, CAESAR, "Scout Reveal"
    )
    if not valid:
        raise CommandError(reason)

    # Check Hidden Auxilia available
    hidden_auxilia = count_pieces_by_state(
        state, region, ROMANS, AUXILIA, HIDDEN
    )
    if hidden_auxilia < auxilia_count:
        raise CommandError(
            f"Only {hidden_auxilia} Hidden Auxilia in {region}, "
            f"need {auxilia_count}"
        )

    # Total Warbands to reveal: max 2 per Auxilia flipped — §4.2.2
    max_reveals = auxilia_count * 2
    total_targets = sum(t["count"] for t in targets)
    if total_targets > max_reveals:
        raise CommandError(
            f"Can only reveal up to {max_reveals} Warbands with "
            f"{auxilia_count} Auxilia (2 per Auxilia), but {total_targets} "
            f"requested"
        )

    result = {
        "auxilia_flipped": auxilia_count,
        "warbands_revealed": [],
        "scouted_placed": [],
    }

    # Flip Auxilia from Hidden to Revealed
    flip_piece(state, region, ROMANS, AUXILIA,
               count=auxilia_count,
               from_state=HIDDEN, to_state=REVEALED)

    # Reveal target Warbands and place Scouted markers
    for target in targets:
        target_faction = target["faction"]
        target_count = target["count"]

        if target_faction == ROMANS:
            raise CommandError("Cannot Scout-reveal Roman pieces")

        # Check Hidden Warbands available for this faction
        hidden_warbands = count_pieces_by_state(
            state, region, target_faction, WARBAND, HIDDEN
        )
        # Also count Revealed (already revealed stay Revealed but get Scouted)
        revealed_warbands = count_pieces_by_state(
            state, region, target_faction, WARBAND, REVEALED
        )

        # §4.2.2: "Reveal up to two Warbands (flip from Hidden to Revealed,
        # or leave Revealed, 1.4.3) in that Region and place Scouted markers
        # on them (if none already)."
        # Warbands already Scouted don't get re-scouted.
        scouted_warbands = count_pieces_by_state(
            state, region, target_faction, WARBAND, SCOUTED
        )

        # Flip Hidden Warbands to Scouted (Revealed + Scouted marker)
        hidden_to_flip = min(target_count, hidden_warbands)
        remaining = target_count - hidden_to_flip

        if hidden_to_flip > 0:
            # Flip Hidden → Scouted (which is Revealed + Scouted marker)
            flip_piece(state, region, target_faction, WARBAND,
                       count=hidden_to_flip,
                       from_state=HIDDEN, to_state=SCOUTED)
            result["scouted_placed"].append(
                (target_faction, hidden_to_flip)
            )

        # Revealed Warbands → Scouted (place Scouted marker)
        if remaining > 0:
            revealed_to_scout = min(remaining, revealed_warbands)
            if revealed_to_scout > 0:
                flip_piece(state, region, target_faction, WARBAND,
                           count=revealed_to_scout,
                           from_state=REVEALED, to_state=SCOUTED)
                result["scouted_placed"].append(
                    (target_faction, revealed_to_scout)
                )
            remaining -= revealed_to_scout

        result["warbands_revealed"].append(
            (target_faction, target_count - remaining)
        )

    return result


