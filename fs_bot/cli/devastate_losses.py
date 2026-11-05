"""Choose Devastate casualties by physical type and visibility."""
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.devastate_losses import validate_response


def collect_devastate_losses(state,faction,request,stdin,stdout):
    remaining=request['count'];entries=[];available=request['available']
    stdout.write(f"\n{faction}: choose {remaining} Devastate casualties in {request['region']}.\n")
    with inspect_board(state,stdout):
        for index,entry in enumerate(available):
            if not remaining:break
            minimum=max(0,remaining-sum(e['count'] for e in available[index+1:]))
            maximum=min(remaining,entry['count'])
            label=entry['piece_type']+(f" ({entry['piece_state']})" if entry['piece_state'] else '')
            count=(minimum if minimum==maximum else prompt_choice(stdin,stdout,
                f'How many {label} to remove?',[(f'{n} {label}',n) for n in range(minimum,maximum+1)]))
            if count:entries.append(dict(entry,count=count));remaining-=count
    return validate_response(state,request,{'removals':entries})
