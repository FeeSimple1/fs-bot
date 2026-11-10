"""Collect concrete Event entries on the board after the preceding steps."""
from fs_bot.cards import event_piece_plans as rules
from fs_bot.cards.event_preview import preview_event_prefix
from fs_bot.cli.action_windows import inspect_board, prepare
from fs_bot.cli.menus import prompt_choice


def _label(entry):
    return ' '.join(str(entry[key]) for key in
                    ('count', 'faction', 'piece_state', 'piece_type', 'tribe', 'region')
                    if key in entry)


def collect_params(state, actor, card, shaded, stdin, stdout):
    params = {}
    if card == 'A65':
        sources = rules.kinship_sources(state)
        if sources:
            with inspect_board(state, stdout):
                params['from_faction'] = prompt_choice(stdin, stdout,
                    'Kinship source faction?', [(source, source) for source in sources])
    for key, step, minimum, maximum in rules.STEPS[card]:
        entries = params.setdefault(key, [])
        used = 0
        while used < maximum:
            stage = preview_event_prefix(state, actor, card, shaded, params,
                                         step=step, index=len(entries))
            stage, actions = prepare(stage, actor, stdin, stdout, stage='event_step',
                                     step=step, index=len(entries))
            options = rules.options(stage, card, key, params, maximum - used)
            selected = None
            if options:
                choices = [(_label(entry), entry) for entry in options]
                if rules.may_finish(stage, card, key, used, minimum, options):
                    choices.append(('Finish this step', None))
                with inspect_board(stage, stdout):
                    selected = prompt_choice(stdin, stdout,
                        f'{card} {key.replace("_", " ")}', choices)
            if selected is None:
                if actions:
                    params.setdefault('stage_timing_actions', {})[
                        f'{step}:{len(entries)}'] = actions
                break
            entries.append(dict(selected, timing_actions=actions) if actions else selected)
            used += selected.get('count', 1)
    return params
