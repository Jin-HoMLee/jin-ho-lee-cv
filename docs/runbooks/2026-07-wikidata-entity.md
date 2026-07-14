# Runbook: Wikidata entity for Jin-Ho Lee

Phase 14 (issue #113).
A Wikidata item is the strongest entity anchor for a common-ish name: it feeds Google's Knowledge Graph and is read directly by LLMs.
The item is created by Jin-Ho's own account, off-repo.
This runbook makes that repeatable.

## Privacy boundary (do not cross)

INCLUDE only the professional core:

- instance of (P31) -> human (Q5)
- occupation (P106) -> bioinformatician / data scientist
- field of work (P101) -> bioinformatics, data science
- ORCID iD (P496) -> 0009-0001-8784-1771
- GitHub account (P2037) -> Jin-HoMLee
- official website (P856) -> https://jinholee.is-a.dev/
- country of citizenship (P27)

EXCLUDE, deliberately:

- date of birth
- employer (P108)
- educated at (P69)
- residence, any address, phone number

This is a considered privacy decision, not an oversight.
A future session must not "helpfully" enrich the item with these.

## Notability

Wikidata items for people need to be verifiable against published sources.
The anchor here is the peer-reviewed publication record (DOI-bearing, in `content/publications.bib`) plus the ORCID record.
Every statement added should carry a reference to a published source (the ORCID record, a paper's DOI, or the official website for P856).
If the item is challenged for notability, the publication record is the defence - do not pad it.

## Steps

1. Log in to https://www.wikidata.org with Jin-Ho's own account (create one if needed).
2. Search first: confirm no item already exists for this Jin-Ho Lee.
   Several other people share the name - check ORCID / affiliation before concluding.
3. Create the item: label "Jin-Ho Lee", description "bioinformatician and data scientist" (English), plus a German label/description.
4. Add each statement from the INCLUDE list above, attaching a reference to each.
5. Note the Q-ID (e.g. `Q12345678`).
6. Wire it into the CV (see next section).

## Wiring the Q-ID into the CV

In `content/personal.yaml`, inside `links:`:

    wikidata: "https://www.wikidata.org/wiki/Q<ID>"

`scripts/render_jsonld._same_as` picks up every link key except `website`, so the Wikidata URL flows into the Person's `sameAs` automatically.
`scripts/render_jsonresume._network_for` already maps `wikidata` -> "Wikidata".

Then:

    just validate && just test
    just snapshots-update   # the new URL appears in resume.json / person.jsonld / cv-*.txt
    git diff tests/__snapshots__/   # eyeball, then commit

## Google Scholar

Already wired (Task 1): `https://scholar.google.com/citations?user=QPyM-WoAAAAJ`.
Reference it from the Wikidata item too, if Wikidata's Google Scholar author ID property (P1960) applies.
