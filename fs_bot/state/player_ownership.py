"""Identify the players who run Factions under §1.5.1 and A1.5.1."""

from fs_bot import rules_consts as rc

FIELD = 'faction_owners'
SETUP_FIELD = 'setup_faction_owners'


def spare_pairs(scenario):
    western = rc.GERMANS if scenario in rc.ARIOVISTUS_SCENARIOS else rc.ARVERNI
    return ((rc.ROMANS, rc.AEDUI), (western, rc.BELGAE))


def _factions(scenario):
    from fs_bot.engine.game_engine import get_sop_factions
    return get_sop_factions({'scenario': scenario})


def parse_seat(scenario, value):
    """Read a single Faction or one printed comma-separated pair."""
    assignable = _factions(scenario)
    names = {faction.casefold(): faction for faction in assignable}
    parts = [part.strip().casefold() for part in value.split(',')]
    if len(set(parts)) != len(parts) or any(part not in names for part in parts):
        raise ValueError(f'Choose distinct Factions from {", ".join(assignable)}.')
    chosen = tuple(faction for faction in assignable if faction.casefold() in parts)
    if len(chosen) != 1 and chosen not in spare_pairs(scenario):
        options = ' or '.join(','.join(pair) for pair in spare_pairs(scenario))
        raise ValueError(f'Choose one Faction or a printed pair ({options}).')
    return chosen


def validate_assignments(scenario, owners):
    if not isinstance(owners, dict) or set(owners) - set(_factions(scenario)):
        raise ValueError('Faction owners must map current playable Factions to players.')
    groups = {}
    for faction, player in owners.items():
        if not isinstance(player, str) or not player or player.strip() != player:
            raise ValueError('Each player identity must be a nonempty trimmed string.')
        groups.setdefault(player, set()).add(faction)
    pairs = [set(pair) for pair in spare_pairs(scenario)]
    if any(len(group) > 1 and group not in pairs for group in groups.values()):
        raise ValueError('A player may run one Faction or one printed Spare Factions pair.')


def assignments(scenario, humans, pairs=()):
    """Assign stable labels to the human groups chosen by a frontend."""
    humans = set(humans)
    available = spare_pairs(scenario)
    partners = {}
    for pair in pairs:
        if pair not in available or set(pair) - humans or set(pair) & partners.keys():
            raise ValueError('Choose distinct printed pairs whose Factions are both human.')
        first, second = pair
        partners[first] = second
        partners[second] = first
    owners = {}
    player_number = 0
    for faction in _factions(scenario):
        if faction not in humans or faction in owners:
            continue
        player_number += 1
        player = f'Player {player_number}'
        owners[faction] = player
        if faction in partners:
            owners[partners[faction]] = player
    if set(owners) != humans:
        raise ValueError('Select only Factions playable in this scenario.')
    return owners


def install(state, owners):
    validate_assignments(state['scenario'], owners)
    state[FIELD] = dict(owners)
    state['non_player_factions'] = set(_factions(state['scenario'])) - owners.keys()


def validate_state_owners(state):
    if FIELD not in state:
        return
    owners = state[FIELD]
    validate_assignments(state['scenario'], owners)
    expected_bots = set(_factions(state['scenario'])) - owners.keys()
    if state.get('non_player_factions') != expected_bots:
        raise ValueError('Player ownership and Non-player Factions disagree.')


def player_of(state, faction):
    return state.get(FIELD, {}).get(faction)


def factions_of(state, player):
    return tuple(faction for faction in _factions(state['scenario'])
                 if player_of(state, faction) == player) if player is not None else ()


def group_of(state, faction):
    return factions_of(state, player_of(state, faction)) or (faction,)


def shares_player(state, first, second):
    if first == second or first not in rc.FACTIONS or second not in rc.FACTIONS:
        return False
    owner = player_of(state, first)
    return owner is not None and owner == player_of(state, second)


def has_pairs(state):
    return any(shares_player(state, *pair) for pair in spare_pairs(state['scenario']))


def interlude_swap(state):
    """The German player's identity follows the Arverni role in the second half."""
    owners = dict(state[FIELD])
    german = owners.pop(rc.GERMANS, None)
    if german is not None:
        owners[rc.ARVERNI] = german
    install(state, owners)
