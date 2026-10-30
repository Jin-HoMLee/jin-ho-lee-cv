# One-page CV redesign implementation plan

**Design:** `docs/superpowers/specs/2026-10-30-one-page-cv-redesign-design.md`

1. **Lock the renderer projection contract**
   - Add failing tests for the three focus treatments, grouped experience, proof selection, comp-bio research evidence, and DE localization.
   - Implement a resolved `pdf_layout` derived from canonical records.
   - Preserve appended tailoring bullets.

2. **Build the approved visual family**
   - Add the three original SVG line-art assets.
   - Replace the stock CV template with the warm masthead, focus panel, 62/38 body, timeline, proof cards, and footer.
   - Keep stock output photo-free and retain optional private-photo compatibility.

3. **Make all projections fit honestly**
   - Build all six stock PDFs.
   - Tighten selected evidence or lower-priority details where German expands.
   - Keep main evidence at or above the readable type floor; do not solve overflow with micro-type.

4. **Upgrade PDF regression gates**
   - Require one A4 page for all stock outputs.
   - Verify Poppler and pypdf extraction, target evidence, headings, bookmarks, links, typography, photo-free stock resources, and safe PDF features.
   - Verify EN/DE tailored comp-bio exports remain one page and retain appended evidence.

5. **Document and validate**
   - Update the repository conventions for the one-page PDF contract.
   - Run `just validate`, `just test`, and `just lint`.
   - Rebuild and inspect all six PDFs at full-page and 100% scale.
   - Commit, push, open a direct PR, and wait for required CI before marking the inbox request handled.
