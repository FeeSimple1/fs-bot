# Self-Play Strategy & Balance Playbook — Falling Sky

Instructions for an AI agent working in the Falling Sky repository. The goal is to
reproduce a process that worked on the Liberty or Death project (`lod-bot`): research
faction strategy, encode competing strategy hypotheses as cheap heuristic policies,
run large self-play batches against the rule-based bots, write evidence-based strategy
notes — and treat every anomaly in the aggregate statistics as a potential rules bug
or balance defect worth chasing to root cause. On lod-bot this process found, in one
pass: two infinite-loop CLI bugs, a Winter-Quarters supply rule misimplementation that
silently bled ~5 Support per game and drove a 95% faction win-rate skew, and
hash-seed-dependent nondeterminism in game outcomes. None of those were visible to
1,100+ passing unit tests. The statistics are the instrument; strategy notes are the
deliverable; bugs are the bycatch that ends up mattering most.

Reference implementations to crib from (in the lod-bot repo, if available to you):
`lod_ai/llm/` (harness, policies, provider, observation), `lod_ai/llm/heuristic.py`
(strategy profiles), `lod_ai/tools/heuristic_selfplay.py` (batch runner),
`lod_ai/tools/balance_smoke.py` + `balance_baseline.json` (drift guardrail), and
`selfplay-strategy-notes.md` (the deliverable's shape).

Throughout: obey this repo's own AGENTS/CLAUDE instructions where they conflict with
anything here. In particular, if the repo designates source-of-truth documents (rules
text, bot flowcharts, scenario references), never change them; when a rules or
bot-behavior question is ambiguous after consulting them, record the question and the
candidate readings with data, and ask the owner rather than guessing. Balance fixes
are rules-compliance fixes; they must be justified by the reference documents, not by
a desire to make the win rates prettier.

## Phase 0 — Verify the substrate before building anything

Confirm, by running them, that these exist and work; build or fix them first if not:

1. **A headless game runner**: programmatically play a full bot-only game from any
   scenario and seed, no stdin, returning a winner. If only an interactive CLI exists,
   add a pluggable input provider at the single point where the CLI reads input
   (lod-bot pattern: `set_input_provider(provider)` where `provider.prompt(label,
   menu)` returns the string a human would have typed, and every menu constructor
   records a structured `{kind, prompt, options, min, max}` description of itself).
   This is the keystone: it lets any policy — random, scripted, heuristic, or an LLM —
   sit in a human seat while the bots play everyone else.
2. **A Policy interface** answering one prompt at a time: `choose(observation, label,
   menu, faction) -> str`, plus a RandomPolicy (uniform over *legal* answers — derive
   legality from the structured menu, never parse prose) and a FirstChoicePolicy.
   These two baselines are not throwaways; they are the controls every result is
   measured against, and RandomPolicy is your fuzzer.
3. **Winner detection** that returns a *faction name* for every termination path:
   mid-game victory checks, final scoring, deck exhaustion. On lod-bot the mid-game
   victory path logged no faction and had to be recomputed from victory margins —
   check this early, it corrupts every downstream table.
4. **A full test-suite pass** before you start. You will be changing engine-adjacent
   code; you need a clean baseline to attribute breakage.

Smoke the harness with RandomPolicy in every seat, every scenario, full games, before
proceeding. Expect this alone to find bugs: deterministic and random policies exercise
wizard paths humans rarely hit. Two specific classes to watch for, both found on
lod-bot: **impossible-range count prompts** (a wizard demanding "place 1..0 of a piece
with 0 available" loops forever for any input source — guard the prompt primitive
itself, not just the call site) and **deterministic replay loops** (a turn plan that
fails validation restarts the turn; a deterministic policy then replays the identical
failing answers forever — see Phase 2's degrade ladder).

## Phase 1 — Research, in priority order

1. The repo's own strategy documents and bot flowchart references, if present. These
   are the richest, most testable source and are already in the implementation's
   vocabulary.
2. Published play advice: BGG strategy threads for Falling Sky (note: BGG is
   client-rendered; fetch via API or browser tooling, plain HTTP returns a shell),
   The Players' Aid COIN Workshop series, InsideGMT articles, the playbook PDF's
   designer notes. Falling Sky has a substantial body of COIN-series lore: Roman
   logistics/dispersal tension, Arverni Devastate timing, Aedui economic play,
   Belgae rampage-and-retreat, Germans as semi-random spoiler.
3. Generic COIN principles (eligibility/initiative cycling, event vs ops timing,
   pass economics, "second eligible" discipline).

Output of this phase is not prose — it is **2 competing, falsifiable strategy
hypotheses per faction**, each expressible as a preference ordering over commands and
special activities plus simple space-selection rules. "Arverni: Devastate-led terror
vs Battle-led conquest" is testable; "play flexibly" is not. Write them down with the
source for each before encoding anything.

## Phase 2 — Encode hypotheses as heuristic profiles

Before writing the policy, **map the menu vocabulary empirically**: run a dozen
random-policy games with a recording wrapper that logs every `(prompt, options)` pair,
then aggregate. Build keyword matching against the actual strings the wizards emit,
not the strings you expect. Budget an hour for this; it prevents days of silent
mismatch (a preference for "Battle" does nothing if the menu says "Assault").

A profile is data, not code: ordered command preferences, ordered SA preferences,
event-side preference (in COIN terms: which factions take shaded vs unshaded by
default), yes/no rules for add-on prompts, count rules as regex→mode pairs (`max` for
placing/moving own pieces, `min` for losses and payments), and named space-scorers
(parse the rendered observation into per-space support/control/pieces; score
Rally/Devastate/Battle targets per hypothesis; return ≤0 to mean "stop selecting").
Condition preferences on observable phase state where the hypothesis demands it
(lod-bot keyed the French switch on "Treaty of Alliance=played" appearing in the
observation; Falling Sky equivalents might be Vercingetorix on-map or winter
proximity).

Two robustness mechanisms are mandatory, learned the hard way:

- **Degrade ladder.** Give the provider an optional `policy.begin_turn(...)` hook so
  the policy knows when a real turn starts, and count how many times the top-level
  action menu reappears within one turn — each reappearance means the engine rejected
  the last plan. On retry N: rotate the command preference list by N−1, answer No to
  all optional add-ons, then fall back to Limited Command, then Pass. Without this, a
  deterministic policy will eventually wedge a batch.
- **Provider-side retry valve.** Independently of the policy, after ~12 identical
  rejected prompts force the first legal option. Belt and suspenders.

Add a unit test that plays a few cards with every profile in its faction's seat.

## Phase 3 — Run the experiment matrix

Build a resumable batch runner (one JSON line per game: label, faction, scenario,
seed, winner, cards, decisions, error; skip keys already present on restart — this
makes interrupted batches free). Matrix per scenario: every profile + RANDOM and
FIRST baselines for every seat, identical seed sets for all configurations, plus a
bot-only reference batch. On lod-bot, 540 games at under a second each covered three
scenarios; size yours to at least 20 seeds per cell for the headline scenario.

Statistical discipline: at n=20, the 95% noise band is roughly ±20 points — only
report gaps bigger than that, and say so in the notes. Use identical seeds across
configurations (paired comparison). Treat *zero* crashes as a hard requirement;
every error line is a bug to fix before trusting the batch.

## Phase 4 — Read the tables like an instrument

For each seat × scenario, tabulate: own-faction win rate, full winner distribution,
and average game length. Three distinct kinds of signal:

- **Strategy signal** (the deliverable): profile A beats profile B and both beat
  RANDOM. Note not just *whether* a profile loses but *who wins instead* — on
  lod-bot, "military Patriots lose specifically to the British" exposed the causal
  mechanism (battle casualties feed the enemy's victory margin). The analogous
  Falling Sky question: who profits when the Romans overextend, or when the Arverni
  battle instead of devastating?
- **Skill-elasticity signal**: compare RANDOM's win rate per seat to the bots' and
  profiles'. A seat where random wins often is structurally carried; a seat where
  nothing simple ever wins is where move quality concentrates. Both are worth a
  finding.
- **Anomaly signal** (the bycatch): any seat winning ~0% or ~80%+ regardless of what
  sits in it; any game-length collapse; any "winner" string that isn't a faction
  name; bots passing on internal errors. Each anomaly gets the Phase 5 treatment.

## Phase 5 — Chase every anomaly to root cause

The lod-bot template, reusable verbatim:

1. **Audit setup first**: diff the scenario's initial state against the scenario
   reference document, totals and per-space. Cheap, and eliminates the boring
   explanation.
2. **Instrument the mechanism, not the outcome**: if a victory margin is skewed,
   classify every event that moves that margin (per-source counters over many games
   — e.g. support shifts attributed to commands vs winter phases vs supply vs
   events). The dominant term names the suspect. On lod-bot the winter Supply Phase
   was bleeding −5 Support/game, equal to the entire opposing program.
3. **Read the reference for the suspect mechanism** and compare with the code path —
   including the *bot's* documented decision rule, which is often where the
   divergence lives (the engine implemented the rule but ignored the bot's
   "pay only where it matters" clause).
4. **Fix to the reference's letter; measure before/after** with the same seed sets;
   put the before/after table in the commit message.
5. **When the letter and the apparent intent diverge** (the fix swings balance
   implausibly far, or the literal reading does something absurd like deleting field
   armies), stop. Write the candidate readings with their measured consequences into
   the repo's questions file and ask the owner to pick. Do not tune to taste.
6. Re-run the affected experiment cells and annotate the strategy notes with what
   changed — never leave published numbers standing on a fixed engine without a
   stale-data warning.

## Phase 6 — Write the strategy notes

One markdown document in the repo root. Shape that worked: a preamble stating these
are findings *about this implementation's bots*, not about human play; a short
method section with game counts and the noise band; the results table; numbered
findings in prose, each tied to specific numbers and, where possible, a mechanism;
a caveats-and-next-experiments section; sources for the strategy priors. Keep
qualitative claims separable from win-rate numbers so engine fixes can stale the
numbers without staling the document. If an engine bug was found and fixed mid-study,
write the addendum: what the bug was, before/after balance, which findings survive.

## Phase 7 — Leave a guardrail behind

The class of bug this process catches is invisible to unit tests, so automate the
instrument before leaving:

- A balance-smoke tool: replay a fixed matrix of bot-only games (e.g. 20 seeds × all
  scenarios), diff winners against a committed baseline JSON, fail when any faction's
  win rate moves beyond ±15%, with an `--update` flag to rebaseline after intended
  changes.
- **Pin the hash seed.** Check whether outcomes change across processes with
  different `PYTHONHASHSEED` values (on lod-bot they did — set/dict iteration order
  reached bot decisions). Pin it (re-exec) in the tool so the guardrail is exact, and
  file the underlying iteration-order sensitivity as its own issue.
- A small pytest canary (a few fixed-seed games, any winner flip fails) with an
  error message that tells the developer exactly how to rebaseline intentionally.
- **Validate by mutation**: temporarily revert your own rules fix and confirm the
  guardrail trips. A guardrail that has never fired is a hypothesis, not a tool.

## Working agreements

Commit in coherent units with measured effects in the messages; run the full test
suite before every commit; add a regression test with every bug fix; don't track
generated artifacts (batch results, baselines excepted — the baseline is
deliberately committed); update the README when you add entry points. Where the
choice is between matching the reference documents and improving the win rates,
the reference documents win, and disagreements go to the owner with data attached.
