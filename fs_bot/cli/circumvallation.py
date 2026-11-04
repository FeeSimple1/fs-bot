"""Roman-owned optional Circumvallation March selection."""
from fs_bot import rules_consts as rc
from fs_bot.cards import circumvallation as card
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.diviciacus import choose_regions,planning_scope
from fs_bot.cli.human_plan import _planning_copy
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.free_actions import validate_free_action_response


def collect_march(state,faction,request,stdin,stdout):
    with inspect_board(state,stdout):
        if request.get('previous_error'):
            stdout.write(request['previous_error']+'\n')
        while True:
            mode=prompt_choice(stdin,stdout,'Romans: Circumvallation benefit?',[
                ('Choose Citadel and exact March groups','plan'),
                ('Use bot default for the whole benefit','default'),('Decline the whole benefit','decline')])
            if mode!='plan':
                return {'use_default' if mode=='default' else 'decline':True}
            destination=prompt_choice(stdin,stdout,'Which non-Roman Citadel?',[(r,r) for r in request['destinations']])
            sim=_planning_copy(state)
            cooperation=choose_regions(sim,faction,'command',stdin,stdout)
            marches=[]
            with planning_scope(sim,faction,cooperation,'command'):
                remaining=card.pools(sim)
                while True:
                    candidates=[r for r,pool in remaining.items() if any(pool.values())
                                and card.routes(sim,r,destination,pool)]
                    origin=prompt_choice(stdin,stdout,'Select next adjacent Roman origin:',
                        [(r,r) for r in candidates]+[('Finish March; place marker if possible',None)])
                    if origin is None:
                        break
                    pool=remaining[origin]
                    legions=prompt_choice(stdin,stdout,'How many Legions?',[(f'{n} Legions',n) for n in range(pool[rc.LEGION]+1)])
                    auxilia=prompt_choice(stdin,stdout,'How many Auxilia?',[(f'{n} Auxilia',n) for n in range(pool[rc.AUXILIA]+1)])
                    leader=(prompt_choice(stdin,stdout,'March the Leader?',[
                        ('Leave Leader here',False),('March Leader',True)]) if pool[rc.LEADER] else False)
                    entry={'origin':origin,'legions':legions,'auxilia':auxilia,'leader':leader}
                    if not (legions or auxilia or leader):
                        stdout.write('Select at least one piece in a moving group.\n');continue
                    if not card.routes(sim,origin,destination,card.group_for(entry,pool)):
                        stdout.write('That group cannot take the adjacent route.\n');continue
                    marches.append(entry)
                    pool[rc.LEGION]-=legions;pool[rc.AUXILIA]-=auxilia
                    if leader:
                        pool[rc.LEADER]=None
            response={'destination':destination,'marches':marches}
            if cooperation is not None:
                used={e['origin'] for e in marches}
                response['diviciacus_regions']=[r for r in cooperation if r in used]
            error=validate_free_action_response(state,faction,request,response)
            if error:
                stdout.write(f'Cannot use this March: {error}\n');continue
            return response
