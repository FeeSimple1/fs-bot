"""Each physical owner chooses exact Devastate casualties (§4.3.2)."""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces,count_pieces_by_state
from fs_bot.commands.common import CommandError
from fs_bot.engine.agent import consult_agent

KIND='devastate_losses'


def removal_request(state,region,faction):
    pieces=(rc.WARBAND,) if faction==rc.ARVERNI else (rc.WARBAND,rc.AUXILIA,rc.LEGION)
    available=[]
    for piece in pieces:
        states=(None,) if piece==rc.LEGION else (rc.SCOUTED,rc.REVEALED,rc.HIDDEN)
        for visibility in states:
            count=(count_pieces(state,region,faction,piece) if visibility is None else
                   count_pieces_by_state(state,region,faction,piece,visibility))
            if count:
                available.append({'piece_type':piece,'piece_state':visibility,'count':count})
    divisor=4 if faction==rc.ARVERNI else 3
    return {'kind':KIND,'region':region,'faction':faction,
            'count':sum(e['count'] for e in available)//divisor,'available':available}


def _cell(entry):return entry['piece_type'],entry['piece_state']


def validate_response(state,request,response):
    if (isinstance(response,dict) and set(response)=={'use_default'}
            and response['use_default'] is True):
        return response
    if not isinstance(response,dict) or set(response)!={'removals'} or not isinstance(response['removals'],list):
        raise ValueError('Choose the exact Devastate casualties for this owner.')
    current=removal_request(state,request['region'],request['faction'])
    if current['count']!=request['count']:
        raise ValueError('The required Devastate casualty count has changed.')
    offered={_cell(e):e['count'] for e in request['available']}
    live={_cell(e):e['count'] for e in current['available']}
    used={}
    for entry in response['removals']:
        if (not isinstance(entry,dict) or set(entry)!={'piece_type','piece_state','count'}
                or not isinstance(entry['piece_type'],str)
                or entry['piece_state'] not in (None,rc.HIDDEN,rc.REVEALED,rc.SCOUTED)
                or type(entry['count']) is not int or entry['count']<=0):
            raise ValueError('Each Devastate casualty needs an offered type, visibility and positive count.')
        cell=_cell(entry);used[cell]=used.get(cell,0)+entry['count']
        if used[cell]>min(offered.get(cell,0),live.get(cell,0)):
            raise ValueError('Devastate casualties exceed an offered physical cohort.')
    if sum(used.values())!=request['count']:
        raise ValueError('Remove exactly the required Devastate casualty count.')
    return response


def _default(request):
    # §8.4.1: remove own pieces in reverse order — Scouted, Revealed,
    # Hidden soft pieces before Legions. Do not preserve the old helper's
    # accidental Hidden-first generic remove_piece fallback.
    remaining=request['count'];entries=[]
    for entry in request['available']:
        take=min(remaining,entry['count'])
        if take:entries.append(dict(entry,count=take));remaining-=take
    return entries


def _legacy(state,request,entries):
    """Retain trusted tuple plans; None visibility uses its legacy H/R/S order."""
    if not isinstance(entries,(list,tuple)):
        raise CommandError('Devastate removals must be a list of triples.')
    remaining={_cell(e):e['count'] for e in request['available']};result=[]
    for entry in entries:
        if not isinstance(entry,(list,tuple)) or len(entry)!=3:
            raise CommandError('Each supplied Devastate removal needs type, visibility and count.')
        piece,visibility,count=entry
        if (not isinstance(piece,str) or visibility not in (None,rc.HIDDEN,rc.REVEALED,rc.SCOUTED)
                or type(count) is not int or count<=0):
            raise CommandError('Invalid supplied Devastate casualty.')
        states=((rc.HIDDEN,rc.REVEALED,rc.SCOUTED) if visibility is None and piece in (rc.WARBAND,rc.AUXILIA)
                else (visibility,))
        for ps in states:
            take=min(count,remaining.get((piece,ps),0))
            if take:
                result.append({'piece_type':piece,'piece_state':ps,'count':take})
                remaining[piece,ps]-=take;count-=take
        if count:raise CommandError('Supplied Devastate casualties are not present or eligible.')
    try:validate_response(state,request,{'removals':result})
    except ValueError as exc:raise CommandError(str(exc)) from exc
    return result


def collect_removals(state,region,provided=None):
    """Freeze all owner counts and validate every plan before any removal."""
    if provided is not None and (not isinstance(provided,dict) or set(provided)-set(rc.FACTIONS)):
        raise CommandError('Supplied Devastate removals must name physical owner Factions.')
    provided=provided or {}
    requests={f:removal_request(state,region,f) for f in rc.FACTIONS}
    plans={f:_legacy(state,requests[f],entries) for f,entries in provided.items()}
    authored=bool(provided)
    for faction,request in requests.items():
        if faction in plans or not request['count']:continue
        response=consult_agent(state,faction,request)
        if response is None:
            plans[faction]=_default(request);continue
        validate_response(state,request,response)
        if response.get('use_default') is True:
            plans[faction]=_default(request)
        else:
            plans[faction]=response['removals'];authored=True
    return plans,authored
