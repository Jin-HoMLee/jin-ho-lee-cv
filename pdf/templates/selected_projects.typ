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
  // The whole short list travels together: no orphaned section label at the
  // bottom of page one, and no project outcomes detached from their titles.
  block(breakable: false, {
    section-heading(labels.sections.selected_projects, "section-projects")
    let months = labels.months_abbr

    for (i, entry) in entries.enumerate() {
      // Use just the lead portion of the title (before the em-dash subtitle) to
      // keep the project header on one line.
      let title-lead = entry.title.split(" – ").at(0)
      let is-oss = entry.at("open_source", default: false)
      let title-suffix = if is-oss { text(size: size-small, fill: muted)[ (Open Source)] } else { none }
      grid(
        columns: (1fr, auto),
        align: (left, right),
        {
          ref-chip(entry.id, url: entry.web_url)
          h(4pt)
          link(entry.web_url)[#text(weight: 600, fill: body-color)[#title-lead]]
          title-suffix
        },
        text(size: size-small, fill: muted)[#_period(entry.period, months, labels.misc.present)],
      )
      v(space-paragraph)
      text(size: size-small)[#entry.outcome]
      if i + 1 < entries.len() { v(space-section / 2) }
    }
  })
}
