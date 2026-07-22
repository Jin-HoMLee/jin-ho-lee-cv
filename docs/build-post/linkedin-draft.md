# LinkedIn post draft - "Ask my CV" (#140)

Not application material; nothing private here. Jin-Ho reviews, edits, and posts this personally - no agent posts to LinkedIn.
Pick ONE variant at publish time. VOICE.md is the floor; run it past yourself out loud before posting.

---

## Variant A - link inline

Don't read my CV. Ask it.

There's a chat box on my CV site that answers questions about my work - grounded in my actual history, not a model's guesses. Ask it "does he have production ML experience or only research?" and see what comes back.

Under the hood it's the same idea all the way down: my CV isn't a document, it's one YAML source of truth that five renderers read from - PDF, website, JSON Resume, a schema.org graph, plain text. The chat box is just the sixth consumer. It runs on a free Cloudflare Worker with a model cascade so it stays up without an inference bill, and PII guards on three surfaces keep the private data private.

I also didn't hand-write most of it. I directed an AI agent through 15 phases of brainstorm → spec → plan → execute, tests first. The whole history is public, specs and all.

Ask the twin something: [LINK]
Read how it's built: [WRITEUP LINK]

---

## Variant B - link in first comment

Don't read my CV. Ask it.

There's a chat box on my CV site that answers questions about my work - grounded in my actual history, not a model's guesses. Ask it "does he have production ML experience or only research?" and see what comes back.

Under the hood it's one idea all the way down: my CV isn't a document, it's a single YAML source of truth that five renderers read from - PDF, website, JSON Resume, a schema.org graph, plain text. The chat box is just the sixth consumer. Free Cloudflare Worker, a model cascade so it stays up without an inference bill, PII guards on three surfaces.

And I didn't hand-write most of it - I directed an AI agent through 15 phases of brainstorm → spec → plan → execute, tests first. The whole build history is public.

Links in the comments 👇

(first comment: the twin + the write-up)

---

## Notes for Jin-Ho
- Both variants use "→" in the phase arrow; swap for "->" if you want the plain-dash-everywhere rule to hold on LinkedIn too.
- The example question is a stress-test question (research-vs-production) on purpose - it invites the reader to check honesty, which is the point.
- Consider a screen recording of one twin exchange as the post's media; LinkedIn favours native video/image over link posts (Variant B exists for that reason).
