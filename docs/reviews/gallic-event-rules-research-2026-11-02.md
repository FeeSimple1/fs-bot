# Gallic Event rules questions — research on 2 November 2026

The owner expressly requested external research of the newly raised rules
questions. This scoped request permits consultation beyond the repository's
usual closed reference set. No protected reference has been edited. Dates
here use America/Chicago;
research took place on 3 November UTC.

I checked GMT's published 2018 rules for both games, the base Playbook,
the listed second-edition erratum, and targeted searches for designer
clarifications. I did not locate an authoritative answer to either complete
question. Some BoardGameGeek material was inaccessible or absent from search
results, so this is not a claim that no answer exists anywhere. Search crawl
dates do not turn the 2018 PDFs into new editions.

## Automatic Arverni receiving one Command

In plain language, Celtic Rites can give the Arverni one free action, but in
Ariovistus the game normally runs them through a complete sequence of actions.
The question is which one they should take, and whether they may act while
At Peace.

A8.2.3 points to their A6.2 phase procedure. That procedure runs Rally,
March, Raid and Battle, with no activation at Peace. It does not expressly
convert the sequence into a priority list for choosing one Command. Generic
§8.2.3 allows random choices when no other priority applies, providing a
plausible alternative reading.

Research did clarify Battle: A3.1 and A4.3.3 require automatic Arverni to
pair it with Ambush, including the Hidden-piece superiority condition.
The base Germans' free Limited Command under §4.5.1 likewise includes their
inherent Ambush. The earlier suggestion to remove Ambush from this grant
was therefore withdrawn.

**Recommendation, subsequently adopted as PR-10:** while At War, take the first possible
permitted Command in normal phase order: Rally, March, Raid, then Battle.
Execute only that Command, with its normal targeting and inherent Ambush if
Battle; retain At Peace inactivity. This follows the procedure A8.2.3 points
to and avoids importing the base-game Arverni strategy or inventing a rule
that wakes peaceful Arverni. The choice of first-possible priority and its
At Peace application remain interpretations, subject to later correction.

## Arduenna's instruction to maximize Legion Losses

In plain language, the Arverni bot must move and attack to hurt Roman Legions
as much as possible. But a plan can look best if the Romans stand and fight,
and worse if they Retreat. The bot also cannot know future dice.

The published rules already provide several limits. Roman bots have their
own Retreat policy (§8.4.3). Arverni Battle evaluation uses the printed
favorable Defender Loss-roll convention (§8.7.1); it does not predict actual
deaths. Vercingetorix's normal March uses the least Harassment and allows at
most three Losses and none on him. Section 8.2.3 generally carries bot
conditions into Event actions unless the Event instructions supersede them.

**Recommendation, subsequently adopted as PR-11:** use a Roman bot's actual Retreat
rules. Against a human, evaluate both standing and legal Retreat choices and
prefer the plan with the better result after the more protective Roman
choice. Retain the stated Defender-roll convention and ordinary Harassment
safety restrictions; do not plan around a lucky Leader saving roll. Then
resolve real player choices and dice normally.

This avoids treating a human as certain to cooperate with the attack, while
preserving the game's explicit evaluation conventions. It is a conservative
prediction policy, not a guarantee of actual losses or a designer ruling.
The original incomplete optimizer remains an unaccepted historical artifact;
its assumptions are not retroactively approved. The adopted model requires
its own implementation and validation.

## Primary sources checked

- [GMT Ariovistus rules (2018)](https://s3-us-west-2.amazonaws.com/gmtwebsiteassets/Ariovistus/Ariovisus_Rules_Final_Lo-Res.pdf): A3.1, A4.3.3, A5.1.1, A5.4, A6.2 and A8.2.3.
- [GMT Falling Sky second-edition rules (2018)](https://gmtwebsiteassets.s3-us-west-2.amazonaws.com/FallingSky/FS_Rules_2018.pdf): §§4.5.1, 5.4, 8.2.3, 8.4.3 and 8.7.1.
- [GMT Falling Sky Playbook (2015)](https://gmtwebsiteassets.s3-us-west-2.amazonaws.com/FallingSky/FallingSky_Playbook_Final.pdf): Card67 text and tips, p44; no prediction rule found there.
- [GMT second-edition Rules of Play erratum](https://gmtwebsiteassets.s3-us-west-2.amazonaws.com/FallingSky/FallingSky_2ndEdition_Rules_of_Play_Erratum.pdf): corrects the 54BC setup illustration; it does not address these questions.

## Owner adoption

After receiving these recommendations, the owner instructed: "Let's go with
your recommendations; they are subject to official overruling if we find
such a source". Both are now recorded as
[PR-10 and PR-11](../provisional-rulings.md#pr-10), adopted on 2 November 2026
(America/Chicago). The source questions remain externally unresolved, but
are no longer project policy blockers. Other uncertain own-piece saving
rolls cannot establish safety or inflate the conservative PR-11 prediction.

[QUESTIONS.md](../../QUESTIONS.md#current-open-source-questions) preserves the
questions and disposition. The [repair report](gallic-event-grants-2026-11-02.md)
records implementation, validation and audit completion separately from
this research/adoption record.
