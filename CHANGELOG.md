# Changelog

Entries describe repository changes. Package metadata alone does not imply
that an artifact has been published or that every rules interaction has been
verified. Revision-specific results remain in the validation reports.

## Unreleased — provisional rulings adopted 24 October 2026

- Adopt [PR-01 through PR-06](docs/provisional-rulings.md) as explicit project
  policies, each subject to possible later correction if an authoritative
  source is found. Protected source documents remain unchanged.
- Permit A28 lending by both non-player Aedui and Belgae only where the
  executor contributes its own participating pieces; preserve human consent
  and the Roman refusal rule.
- Resolve Ariovistus Harassment in printed faction order with Arverni last.
  During Winter use the last actually played non-Winter card, recovered from
  saved history; document a deterministic fallback for missing history.
- Retain the existing A30 ordinary Belgic handling, Roman ownership of unused
  A53 funding, and post-Interlude dormancy of German-owned A63, now supported
  by the owner's provisional rulings.
- Preserve earlier validation measurements as evidence for their original
  revisions; they do not measure these later rulings.

## 0.1.0 — initial local distribution

- Implement Diviciacus cooperation for Commands, permitted Special Activities,
  and defense, preserving physical ownership through movement and losses.
  Human consent and exact physical-piece choices support pause, save and replay;
  non-player planning accounts for cooperation and replans after refusal.
- Preserve a March cohort’s physical-owner context when only native pieces
  continue after formation, drop-offs or borrowed-piece losses. Transit
  residents cannot be substituted into that cohort.
- Apply Event cooperation to the actual permitted forces. Camulogenus now
  moves its selected cohort to one destination within its printed range;
  stationary pieces are not revealed as if they had marched.
- Add the separate optional Diviciacus setup in original scenarios, including
  O38, saved configuration and the printed non-player restrictions.
- Correct Suborn's complete piece choices, cumulative validation, Vergobret's
  fourth piece and second Ally, and non-player Ally priorities. Track both
  Vergobret sides as capabilities, including compatibility with earlier saves.
- Offer active capabilities in Shifting Loyalties, including legacy
  modifier-only Vergobret saves, and use the same capability list in board
  and change displays.
- Make self-play experiments classify their human seat correctly, support
  German policies and Interlude handover, reject invalid outcomes and resume
  only compatible studies. Historical strategy results retain their caveats.
- Extend validation tools and CI to explicit card editions and held-out seeds.
  Mixed-seat determinism compares the complete state, RNG and returned results;
  unfinished games and replay-only failures can no longer report success.
- Reject prohibited Roman Quarters hosts before asking for consent. Preserve
  accepted Supply-Line agreements for their action and avoid asking again
  between Recruit's budget check and execution.
- Add an installable `falling-sky-bot` package and `fs-bot` launch command,
  while retaining `python -m fs_bot` and standard-library-only gameplay.
- Bundle unchanged reference inputs at build time so installed games retain
  full card text and the rules-citation utility retains its source chapters.
  Include the balance baseline used by the installed validation tool.
- Record the writing engine's version and source digest in new saves, keeping
  save format 1 and support for older valid files without this metadata.
- Preserve compatibility fixtures written by the `8ef88e2` engine, including
  pending human decisions and actual pre/post-Interlude game states. These
  establish the tested continuations, not universal replay compatibility.
- Fix circular imports that could prevent direct setup/Battle API use in a
  fresh Python process. Preserve public convenience imports through lazy
  exports.
- Make Trade's earnings breakdown deterministic across Python hash seeds.
- Preserve source and fixture identities across Windows checkouts: Python
  files use LF, while supplied references and archived compatibility JSON
  bypass automatic line-ending conversion. This repairs the remote fixture
  provenance check without changing its recorded expected hash.
- Add a build/install/play workflow for Linux, Windows, and macOS. It builds
  the wheel from the source archive and exercises it in an isolated environment.

See [release maintenance](RELEASES.md) for installation, build checks, and
the save metadata contract. See [current status](docs/current-status.md) for
gameplay changes and unresolved source questions.
