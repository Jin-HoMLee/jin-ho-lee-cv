#import "../styles.typ": *

#let education(entries, labels) = {
  section-heading(labels.sections.education)

  for entry in entries {
    grid(
      columns: (1fr, auto),
      align: (left, right),
      {
        text(weight: 600)[#entry.degree]
        if "field" in entry {
          linebreak()
          text(size: size-small, style: "italic", fill: muted)[#entry.field]
        }
        linebreak()
        text(size: size-small, fill: muted)[
          #entry.institution#if "location" in entry { " · " + entry.location }
        ]
      },
      text(size: size-small, fill: muted)[#entry.year],
    )
    v(space-paragraph)
  }
}
