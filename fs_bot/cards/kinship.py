"""A65 unshaded: one chosen side Battles the other without its Leader."""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.battle.excluded_leader import without_attacker_leader
from fs_bot.board.pieces import count_pieces
from fs_bot.commands.common import free_action_scope
from fs_bot.map.map_data import get_playable_regions_for_state

ATTACKERS = (rc.BELGAE, rc.GERMANS)


def _copy(state):
    return deepcopy({key: value for key, value in state.items() if key != 'decision_agent'})


def opponent(faction):
    if faction not in ATTACKERS:
        raise ValueError('Kinship attackers must be Belgae or Germans')
    return rc.GERMANS if faction == rc.BELGAE else rc.BELGAE


def legal_regions(state, faction):
    if state['scenario'] not in rc.ARIOVISTUS_SCENARIOS:
        return []
    enemy = opponent(faction)
    return sorted(region for region in get_playable_regions_for_state(state, faction)
                  if count_pieces(state, region, faction, rc.WARBAND)
                  and count_pieces(state, region, enemy))


def _action(faction, regions):
    return {'command': rc.CMD_BATTLE, 'sa': 'No SA', 'regions': list(regions),
            'sa_regions': [], 'details': {'battle_plan': [
                {'region': region, 'target': opponent(faction)} for region in regions]}}


def execute_plan(state, response):
    """One actual Battle Command preserves every once-per-Command capability."""
    from fs_bot.engine.execute import _execute_battle
    faction, regions = response['faction'], response['regions']
    with free_action_scope(state, faction), without_attacker_leader(state, faction, regions):
        return _execute_battle(state, faction, _action(faction, regions))


def validate_response(state, response):
    if not isinstance(response, dict):
        return 'Choose the attacking Faction and Battle Regions.'
    if response in ({'decline': True}, {'use_default': True}):
        return None
    if set(response) != {'faction', 'regions'} or response['faction'] not in ATTACKERS:
        return 'Kinship permits only an attacking Faction and its Battle Regions.'
    regions = response['regions']
    if not isinstance(regions, list) or not regions or any(not isinstance(r, str) for r in regions):
        return 'Select at least one Battle Region, or decline.'
    if len(regions) != len(set(regions)):
        return 'Select each Battle Region only once.'
    if not set(regions).issubset(legal_regions(state, response['faction'])):
        return 'Each Region needs attacking Warbands and pieces of the other Faction.'
    from fs_bot.engine.free_actions import _result_error
    result = execute_plan(_copy(state), response)
    return _result_error(result) or (None if result.get('executed') else 'No Battle can execute.')


def default_plan(state, chooser):
    """§8.2.3: apply the actual Battle box to the permitted enemy and Regions."""
    from fs_bot.engine.execute import _free_command_planning_state, _commit_planning_rng
    from fs_bot.bots.belgae_bot import node_b_battle, _get_threat_regions as belgic_threats
    from fs_bot.bots.german_bot import node_g_battle, _get_threat_regions as german_threats
    # A Non-player may select only itself as beneficiary (§8.2.3). A human
    # requesting a bot default can receive a proposal for either printed side.
    if chooser in state.get('non_player_factions', set()) and chooser not in ATTACKERS:
        return None
    candidates = (chooser,) if chooser in ATTACKERS else ATTACKERS
    for faction in candidates:
        regions = legal_regions(state, faction)
        if not regions:
            continue
        planning = _free_command_planning_state(
            state, faction, regions, exclude_commands=[rc.CMD_MARCH, rc.CMD_RALLY, rc.CMD_RAID],
            forced_command=rc.CMD_BATTLE, with_sa=False)
        planning['_command_target_factions'] = {opponent(faction)}
        # The diamond asks whether the Faction HAS its Leader in the
        # Region; Kinship does not remove that physical piece. Its subsequent
        # Battle nevertheless excludes the Leader from strength and losses.
        threats = (belgic_threats if faction == rc.BELGAE else german_threats)(
            planning, planning['scenario'])
        with without_attacker_leader(planning, faction, regions):
            action = (node_b_battle if faction == rc.BELGAE else node_g_battle)(
                planning, threat_regions=threats)
        if action.get('command') != rc.CMD_BATTLE:
            continue
        selected = [entry['region'] for entry in action['details']['battle_plan']]
        if selected:
            _commit_planning_rng(state, planning)
            return {'faction': faction, 'regions': selected}
    return None


def resolve_kinship(state, chooser):
    from fs_bot.engine.agent import consult_agent
    from fs_bot.cards.card_effects import _event_step
    _event_step(state, "A65.selection")
    request = {'kind': 'kinship', 'card_id': 'A65', 'attackers': list(ATTACKERS),
               'regions_by_faction': {f: legal_regions(state, f) for f in ATTACKERS}}
    response = consult_agent(state, chooser, request)
    if response is None or response == {'use_default': True}:
        response = default_plan(state, chooser)
    if response is None or response == {'decline': True}:
        result = {'executed': False, 'declined_no_effect': response is None,
                  'declined': response is not None,
                  'reason': 'Kinship Battle declined' if response else 'No applicable Kinship Battle'}
        return [{'free_action': 'battle', 'flag': 'card_A65', 'chooser': chooser, 'result': result}]
    error = validate_response(state, response)
    if error:
        raise ValueError(error)
    result = execute_plan(state, response)
    return [{'free_action': 'battle', 'flag': 'card_A65', 'chooser': chooser,
             'faction': response['faction'], 'defender': opponent(response['faction']),
             'regions': response['regions'], 'result': result}]
