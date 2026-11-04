"""Executor-owned numeric65 German March and Ambush choices."""
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.free_actions import validate_free_action_response


def collect_response(state,faction,request,stdin,stdout):
    with inspect_board(state,stdout):
        while True:
            default_label=('Use bot default for the whole grant'
                           if request['request_type']=='german_guided_march' else 'Use bot default')
            mode=prompt_choice(stdin,stdout,'German Allegiances: choose the granted action.',
                [('Choose exact action','plan'),(default_label,'default')])
            if mode=='default':
                return {'use_default':True}
            if request['request_type']=='german_guided_ambush':
                choices=request['defenders_by_region']
                region=prompt_choice(stdin,stdout,'Ambush in which next Region?',[(r,r) for r in choices])
                enemy=prompt_choice(stdin,stdout,'Ambush which defender?',[(f,f) for f in choices[region]])
                response={'region':region,'defender':enemy}
            else:
                from fs_bot.cards.german_guidance import destinations
                remaining=dict(request['origins']);marches=[]
                while remaining and len(marches)<request['max_origins']:
                    origin=prompt_choice(stdin,stdout,'Select next German origin:',
                        [(r,r) for r in remaining]+[('Finish March selection',None)])
                    if origin is None:
                        break
                    count=prompt_choice(stdin,stdout,'How many German Warbands move?',
                        [('0 (hide only)',0)]+[(f'{n} Warbands',n) for n in range(1,remaining[origin]+1)])
                    target=None
                    if count:
                        legal=destinations(state,origin,count)
                        if not legal:
                            stdout.write('No legal route for that group; choose another quantity.\n')
                            continue
                        target=prompt_choice(stdin,stdout,'Which adjacent destination?',[(r,r) for r in legal])
                    marches.append({'origin':origin,'destination':target,'warbands':count})
                    remaining.pop(origin)
                response={'marches':marches}
            error=validate_free_action_response(state,faction,request,response)
            if error:
                stdout.write(f'Cannot use this action: {error}\n')
                continue
            return response
