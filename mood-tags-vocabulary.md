# Mood/Theme Tag Vocabulary (draft)

A controlled vocabulary for the AI tagging stage (spec §4.2). Claude picks candidate
tags for each title from this fixed list only — no free-form tags — so the
similarity engine has a consistent, closed set to compare against.

Drawn from themes visible across the two scraped samples (`scraper/output/sample.json`,
`scraper/output/1995_sample.json`): family sagas, crime/action, historical drama,
comedy, romance, horror/mystery.

Status: **draft, not yet approved** — review and edit before the AI tagging script
locks it in. Add/remove/rename freely; this is meant to be edited.

## Family & relationships
- family drama
- family saga
- coming-of-age
- forbidden love
- marriage & betrayal
- friendship & loyalty
- generational conflict

## Struggle & society
- social commentary
- class conflict
- poverty & survival
- corruption
- political intrigue
- immigration & displacement
- women's struggle

## Crime & conflict
- crime & heist
- revenge
- moral dilemma
- prison & captivity
- war & conflict
- underdog

## Emotional tone
- redemption
- tragedy
- nostalgia
- hope & resilience
- despair & loss
- triumph over adversity

## Comedy & lightness
- slapstick comedy
- satire
- feel-good
- comedy of errors
- musical & celebration

## Suspense & the unknown
- mystery & suspense
- supernatural & horror
- psychological thriller

## Historical & epic
- historical epic
- religious & spiritual
- folklore & legend

## Open questions for review
- Is ~30 tags the right size, or should some be merged/split further once we
  see how the AI tagger actually uses them across a larger batch?
- Should genre-adjacent tags (e.g. "crime & heist") be dropped since `genres`
  already captures that, keeping this list purely mood/theme?
