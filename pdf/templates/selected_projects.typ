#import "../styles.typ": *

#let _format-ym(ym, months) = {
  let parts = ym.split("-")
  months.at(int(parts.at(1)) - 1) + " " + parts.at(0)
}

#let _period(p, months, present_label) = {
  let s = _format-ym(p.start, months)
  let e = if "end" in p and p.end != none { _format-ym(p.end, months) } else { present_label }
  s + " – " + e
}

#let selected_projects(entries, labels) = {
  if entries.len() == 0 { return }
  section-heading(labels.sections.selected_projects)
  let months = labels.months_abbr

  for (i, entry) in entries.enumerate() {
    // Use just the lead portion of the title (before the em-dash subtitle) to
    // keep the project header on one line. "(Open Source)" is parsed out of the
    // project role so the dedicated role line can be dropped without losing the
    // open-source signal.
    let title-lead = entry.title.split(" – ").at(0)
    let is-oss = entry.role.contains("Open Source")
    let title-suffix = if is-oss { text(size: size-small, fill: muted)[ (Open Source)] } else { none }
    grid(
      columns: (1fr, auto),
      align: (left, right),
      {
        text(weight: 600)[#title-lead]
        title-suffix
      },
      text(size: size-small, fill: muted)[#_period(entry.period, months, labels.misc.present)],
    )
    v(space-paragraph)
    text(size: size-small)[#entry.outcome]
    if i + 1 < entries.len() { v(space-section / 2) }
  }
}
