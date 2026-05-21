#import "../styles.typ": *

#let _period(p) = {
  let s = if "start" in p { p.start } else { "" }
  let e = if "end" in p and p.end != none { p.end } else { "present" }
  s + " – " + e
}

#let _bullet(b) = {
  let txt = b.en
  let refs = b.at("refs", default: ())

  // Bullet line: dash + text + optional refs at end
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
}

#let experience(entries) = {
  section-heading("Experience")

  for entry in entries {
    // Org + period on one line; role on next
    grid(
      columns: (1fr, auto),
      align: (left, right),
      text(weight: 600)[#entry.org.name],
      text(size: size-small, fill: muted)[#_period(entry.period)],
    )
    text(style: "italic", fill: muted)[#entry.role]
    v(space-paragraph)

    for bullet in entry.bullets {
      _bullet(bullet)
    }
    v(space-section / 2)
  }
}
