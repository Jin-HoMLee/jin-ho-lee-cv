#import "../styles.typ": *

#let education(entries) = {
  section-heading("Education")

  for entry in entries {
    grid(
      columns: (1fr, auto),
      align: (left, right),
      {
        text(weight: 600)[#entry.degree]
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
