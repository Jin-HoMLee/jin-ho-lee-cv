#import "../styles.typ": *

#let awards(entries, labels) = {
  section-heading(labels.sections.awards)

  for entry in entries {
    grid(
      columns: (1fr, auto),
      align: (left, right),
      {
        text(weight: 600)[#entry.title]
        linebreak()
        text(size: size-small, fill: muted)[#entry.issuer]
        if "note" in entry {
          linebreak()
          text(size: size-small, fill: muted)[#entry.note]
        }
      },
      text(size: size-small, fill: muted)[#entry.year],
    )
    v(space-paragraph)
  }
}
