# Issue #50 — Header PDF download menu (resolve PDF ↔ language collision)

**Date:** 2026-06-01
**Issue:** [#50](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/50) — `fix(web): PDF download buttons collide with the site language switch in the header`
**Size:** S · **Type:** bug (web/UX)

## Problem

The header right cluster is one flat `gap-2` row ([Header.astro:23-37](../../../web/src/components/Header.astro)):

```text
Download PDF: [EN▣] [DE▣]   [DE▢]   [☾]
              └ PDF links ┘   │ lang  │ theme
```

On the **English** site the language switcher renders **DE** (switch to German), so two buttons labelled **DE** sit adjacent meaning different things — *download the German PDF* vs *switch the site to German* — with no separation. Misclicks are easy (the reported bug). Symmetric collision on the **German** site (PDF **EN** vs language **EN**).

## Design

Collapse the two PDF buttons into a single disclosure menu, and visually separate the download control from the site controls (language + theme).

### New component — `web/src/components/PdfDownloadMenu.astro`

A self-contained island. Props: `{ lang: Lang }`.

- Computes the localized trigger label: `Download PDF` (en) / `PDF herunterladen` (de).
- `pdfUrlBase = "https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download"` (the GitHub-release base, as today — unchanged).
- Two items: `English → cv-en.pdf`, `Deutsch → cv-de.pdf`.

**Markup** — native `<details>/<summary>` disclosure (progressive enhancement: works with JS disabled):

```astro
<details class="relative" data-pdf-menu>
  <summary aria-label={label} class="<accent pill, list-style:none, cursor:pointer>">
    <DownloadIcon/> {label} <CaretIcon class="caret"/>
  </summary>
  <div class="<absolute panel, right-0, surface bg, border, rounded, shadow>">
    <a href={base}/cv-en.pdf hreflang="en"><span>English</span><span class="muted mono">EN · PDF</span></a>
    <a href={base}/cv-de.pdf hreflang="de"><span>Deutsch</span><span class="muted mono">DE · PDF</span></a>
  </div>
</details>
```

- Default `<summary>` marker hidden (`list-style:none` + `::-webkit-details-marker{display:none}`).
- Caret rotates when open via CSS: `details[open] .caret { transform: rotate(180deg) }`.
- Styling uses existing theme tokens only (`--accent`, `--accent-contrast`, `--surface`, `--surface-border`, `--muted`, `--text`) so it tracks dark/light automatically.
- Panel positioned `absolute right-0` below the trigger; trigger wrapper `relative`.

**Behaviour script** (small vanilla `<script>`, same island pattern as `ThemeToggle.astro`):

- **Escape** closes the open menu and returns focus to the `<summary>`.
- **Click outside** closes it.
- `aria-expanded` on the trigger is kept in sync via a `toggle` listener.
- Selecting a language navigates to the release asset (download) and collapses the menu.
- Clicking the trigger **only toggles the menu** — it never triggers a download, so the reported misclick is structurally impossible.

### Header changes — `web/src/components/Header.astro`

- Remove the inline `downloadLabel` / `pdfUrlBase` consts and the `<span>Download PDF:</span>` + two `<a>` buttons (they move into the component).
- Render order in the right cluster: `<PdfDownloadMenu lang={lang} />` → **divider** → `<LanguageSwitcher>` → `<ThemeToggle>`.
- **Divider**: a 1px-wide, ~20px-tall `aria-hidden` element (`bg-[var(--surface-border)]`) separating the download menu from the site controls, so the two language-ish controls read as distinct groups.
- `LanguageSwitcher` and `ThemeToggle` are **unchanged**.

### Accessibility

- `<summary>` is natively a button and keyboard-operable (Enter/Space toggles; Tab reaches the two links; Escape closes + restores focus to the trigger via the script).
- Renders **closed** server-side → no theme/no-flash interaction, no layout shift.
- `aria-expanded` is mirrored on the `<summary>` via a `toggle` listener — native `<details>` does not reliably expose expanded/collapsed state to Safari/VoiceOver. The accessible name comes from the visible label (icons are `aria-hidden`); no redundant `aria-label`.
- `hreflang` on each link declares the target language; each visible endonym (`English`/`Deutsch`) carries `lang=` so screen readers pronounce it in its own language.

## Testing

- **Build assertion (CI):** inspect [.github/workflows/pages.yml](../../../.github/workflows/pages.yml) for any assertion pinning the *old* PDF-button markup (e.g. `Download PDF:` text or the bare `EN`/`DE` anchors); update it. Add an assertion that the built `index.html` (and `de/index.html`) contains the menu (`data-pdf-menu`) with **both** `cv-en.pdf` and `cv-de.pdf` links and the localized trigger label, so the control can't silently regress. (Pages CI runs on `main` only — so also verify the production build locally before merge.)
- **Local build:** `just web-build`; grep `web/dist/index.html` + `web/dist/de/index.html` for `data-pdf-menu`, both PDF hrefs, and the localized label; confirm no leftover `Download PDF:` label markup.
- **Manual (`verify`/`run`):** open both locales, confirm the trigger opens the menu (does not download), Escape + outside-click close it, both PDFs download, the divider separates the groups, and dark/light theming is correct.

## Out of scope

- No change to `LanguageSwitcher` or `ThemeToggle` behaviour, or to the PDF release URLs.
- No ARIA *menu* pattern (roving tabindex / arrow keys) — the disclosure + link-list pattern is simpler and sufficient for two static links.
- Global `:focus-visible` styling is tracked separately ([#45](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/45)); this component relies on the existing focus styles.
