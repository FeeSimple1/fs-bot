"""A34 Divination: a chosen non-German player commands real German pieces."""
from fs_bot import rules_consts as rc
from fs_bot.engine.free_actions import (consult_free_action, execute_free_action_plan,
                                        validate_free_action_response)

NON_GERMAN_PLAYERS = (rc.ROMANS, rc.AEDUI, rc.BELGAE)


def resolve_divination(state, chooser, limit=3):
    """A Card Reference A34: choose March OR Battle, in/from up to 3 Regions.

    Choosing the action never changes ownership: the trusted grant actor is
    German, while the decision recipient is the selected non-German player.
    The shared validator checks the complete plan on a copy before execution.
    """
    if chooser not in NON_GERMAN_PLAYERS:
        raise ValueError('Divination requires a non-German player to choose the action')
    request = {'kind': 'free_action', 'request_type': 'event_command',
               'card_id': 'A34', 'acting_faction': rc.GERMANS,
               'allowed_commands': ['March', 'Battle'], 'max_regions': min(3, limit),
               'with_sa': False, 'free': True}
    response = consult_free_action(state, chooser, request)
    if response is None:
        # Swords decline choosing the Event, not a Command granted by another
        # player (§8.2.1). The beneficiary's chart governs this action (§8.2.3).
        from fs_bot.cards.divination_np import choose_divination_action
        response = choose_divination_action(state, chooser, min(3, limit))
    if response is None:
        result = {'executed': False, 'reason':
                  'The beneficiary flowchart found no applicable German March or Battle'}
    elif response.get('decline'):
        result = {'executed': False, 'reason': 'Divination action declined'}
    else:
        error = validate_free_action_response(state, chooser, request, response)
        if error:
            raise ValueError(error)
        result = execute_free_action_plan(state, chooser, request, response)
    return [{'free_action': 'german_command', 'flag': 'card_A34',
             'chooser': chooser, 'acting_faction': rc.GERMANS, 'result': result}]


def collect_beneficiary(state, faction, shaded, stdin, stdout):
    from fs_bot.cli.menus import prompt_choice
    allowed = (rc.GERMANS, rc.BELGAE) if shaded else NON_GERMAN_PLAYERS
    selected = prompt_choice(stdin, stdout, 'Divination: which player receives the action?',
                             [(candidate, candidate) for candidate in allowed])
    return {'faction': selected}
