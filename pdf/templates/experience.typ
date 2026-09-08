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

#let _bullet(b, lang) = {
  let txt = b.at(lang)
  let refs = b.at("refs", default: ())

  // Keep each bullet together; long bullets may move as a unit rather than
  // leaving a dangling continuation line at the top of the next page.
  block(breakable: false, {
    grid(
      columns: (8pt, 1fr),
      gutter: 4pt,
      text(fill: accent)[•],
      {
        txt
        if refs.len() > 0 {
          h(4pt)
          for (i, r) in refs.enumerate() {
            if i > 0 { h(2pt) }
            ref-chip(r)
          }
        }
      },
    )
    v(2pt)
  })
}

#let experience(entries, labels, lang) = {
  section-heading(labels.sections.experience)
  let months = labels.months_abbr

  for entry in entries {
    // The heading and first bullet travel together. Remaining bullets can flow
    // independently, while _bullet() keeps each bullet itself unbreakable.
    block(breakable: false, {
      // Org + period on one line; role on next
      grid(
        columns: (1fr, auto),
        align: (left, right),
        text(weight: 600)[#entry.org.name],
        text(size: size-small, fill: muted)[#_period(entry.period, months, labels.misc.present)],
      )
      text(style: "italic", fill: muted)[#entry.role]
      v(space-paragraph)
      if entry.bullets.len() > 0 {
        _bullet(entry.bullets.at(0), lang)
      }
    })

    for (i, bullet) in entry.bullets.enumerate() {
      if i > 0 { _bullet(bullet, lang) }
    }
    v(space-section / 2)
  }
}
