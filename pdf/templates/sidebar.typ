#import "../styles.typ": *

#let _skills(skills, labels) = {
  section-heading(labels.sections.skills)
  for category in skills.categories {
    text(weight: 600, size: size-small)[#category.name]
    v(2pt)
    for group in category.groups {
      text(size: size-small, fill: muted)[#group.label:]
      h(3pt)
      text(size: size-small)[#group.items.join(", ")]
      linebreak()
    }
    v(space-paragraph)
  }
}

#let _languages(langs, labels) = {
  section-heading(labels.sections.languages)
  for l in langs {
    grid(
      columns: (1fr, auto),
      text(size: size-small)[#l.name],
      text(size: size-small, fill: muted)[#labels.proficiency.at(l.proficiency)],
    )
    v(2pt)
  }
}

#let _volunteer(v_data, labels) = {
  section-heading(labels.sections.volunteer)
  for category in v_data.categories {
    text(weight: 600, size: size-small)[#category.name]
    v(2pt)
    text(size: size-small, fill: muted)[#category.entries.join(", ")]
    v(space-paragraph)
  }
}

// Returns the sidebar content only. The colored background + left accent rule
// are applied as a grid cell fill/stroke in cv.typ so the panel spans across
// the page break (full-length rail), bottom-aligned with the main column.
#let sidebar(data, labels) = {
  _skills(data.skills, labels)
  _languages(data.languages, labels)
  _volunteer(data.volunteer, labels)
}
