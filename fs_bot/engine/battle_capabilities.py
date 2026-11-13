"""Capability choices and opening Losses for Battles and Battle Commands."""

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.cards.capabilities import get_capability_owner, is_capability_active
from fs_bot.engine import horse_choice, slingers_choice


def select_for_plan(state, attacker, plan, *, ignore_fort=False, ignore_citadel=False):
    """Collect the owners' choices before a selected Battle plan resolves."""
    slingers_region = slingers_choice.choose_region(state, attacker, plan)
    horse_choice.select_for_command(state, attacker, plan, ignore_fort=ignore_fort,
                                    ignore_citadel=ignore_citadel)
    return slingers_region


def select_for_queue(state, region, attacker, defender, remaining, used):
    """Offer PR-13 windows at this actual Battle and spend each use once."""
    from fs_bot.engine.capability_queue import choose_window as mandatory_window
    from fs_bot.engine.horse_queue import choose_window as optional_window

    fire_slingers = False
    if 13 not in used and slingers_choice.is_active_for(state, attacker):
        fire_slingers = slingers_choice.choose_for_queue(
            state, region, attacker, defender, remaining)
        if fire_slingers:
            used.add(13)

    if ('59u' not in used and rc.ROMANS in (attacker, defender)
            and is_capability_active(state, 59, rc.EVENT_UNSHADED)
            and count_pieces(state, region, rc.ROMANS, rc.AUXILIA)):
        choice = optional_window(state, region, attacker, defender, remaining)
        if choice != 'reserve':
            used.add('59u')
        if choice == 'activate':
            state.setdefault('event_modifiers', {})[horse_choice.FLAGS[0]] = region

    if '59s' not in used and is_capability_active(state, 59, rc.EVENT_SHADED):
        owner = get_capability_owner(state, 59)
        if owner in (attacker, defender):
            blocked = (horse_choice.attack_blocked(state, region, attacker, defender)
                       if owner == attacker else bool(count_pieces(
                           state, region, owner, rc.CITADEL)))
            choice = mandatory_window(state, 59, owner, region, attacker, defender,
                                      remaining, applicable=not blocked, blocked=blocked)
            if choice == 'activate':
                state.setdefault('event_modifiers', {})[horse_choice.FLAGS[1]] = region
                used.add('59s')
    return fire_slingers


def apply_archers(state, region, attacker, defender, *, auto_legion_loss=False):
    """Resolve Card 27's opening Loss before Retreat and the Attack.

    Return the Battle result if the Loss ends combat, and whether Legiones
    has used its automatic first Legion removal.
    """
    from fs_bot.battle.losses import (
        _remove_battle_piece, card27_shaded_absorption, resolve_losses,
    )

    if attacker == rc.ARVERNI:
        recipient = defender
    elif defender == rc.ARVERNI:
        recipient = attacker
    else:
        return None, False
    if (not card27_shaded_absorption(state, region, recipient, rc.ARVERNI)
            or not count_pieces(state, region, recipient)):
        return None, False

    legion_removed = (recipient == defender and auto_legion_loss
                      and count_pieces(state, region, defender, rc.LEGION) > 0)
    if legion_removed:
        _remove_battle_piece(state, region, defender, rc.LEGION, None)
    else:
        resolve_losses(state, region, recipient, 1, inflicting_faction=rc.ARVERNI)
    stopped = not count_pieces(state, region, recipient)
    return ({'card27_wiped': True} if stopped else None), legion_removed


@horse_choice.command_scope
def resolve_single(state, region, attacker, defender, *, is_ambush=False,
                   choose_retreat=False, **options):
    """Resolve a one-Region grant after applying its Command's capabilities."""
    from fs_bot.battle import elite
    from fs_bot.battle.resolve import resolve_battle
    from fs_bot.engine.diviciacus import defense_scope

    plan = [{'region': region, 'target': defender}]
    with defense_scope(state, region, attacker, defender), elite.scope(
            state, region, attacker, defender):
        slingers_region = select_for_plan(
            state, attacker, plan, ignore_fort=options.get('ignore_fort', False),
            ignore_citadel=options.get('ignore_citadel', False))
        if slingers_region == region:
            slingers_choice.fire(state, region, attacker)
        # Retain starting protection if Archers remove a structure.
        for option, piece in (('fort_at_start', rc.FORT), ('citadel_at_start', rc.CITADEL)):
            if options.get(option) is None:
                options[option] = count_pieces(state, region, defender, piece) > 0
        stopped, legion_removed = apply_archers(
            state, region, attacker, defender,
            auto_legion_loss=options.get('auto_legion_loss', False))
        # Aquitani's extra Losses can resolve with zero friendly Forces.
        if stopped is not None and not (options.get('extra_losses', 0) > 0
                                        and count_pieces(state, region, defender)):
            return stopped
        if legion_removed:
            options['auto_legion_loss'] = False
        if choose_retreat and 'retreat_declaration' not in options:
            from fs_bot.engine.execute import _battle_retreat_options
            options.update(_battle_retreat_options(
                state, region, attacker, defender, is_ambush, **options))
        return resolve_battle(state, region, attacker, defender,
                              is_ambush=is_ambush, **options)


def resolve_in_queue(state, region, attacker, defender, remaining, used):
    """Resolve an automatic Ambush after its capability choices."""
    from fs_bot.battle.resolve import resolve_battle
    from fs_bot.engine.diviciacus import defense_scope

    with defense_scope(state, region, attacker, defender):
        if select_for_queue(state, region, attacker, defender, remaining, used):
            slingers_choice.fire(state, region, attacker)
        had_fort = count_pieces(state, region, defender, rc.FORT) > 0
        had_citadel = count_pieces(state, region, defender, rc.CITADEL) > 0
        stopped, _ = apply_archers(state, region, attacker, defender)
        if stopped is not None:
            return stopped
        return resolve_battle(state, region, attacker, defender, is_ambush=True,
                              fort_at_start=had_fort, citadel_at_start=had_citadel)
