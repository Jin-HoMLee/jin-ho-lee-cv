#import "../styles.typ": *

#let _skill-category(category) = block(breakable: false, [
  #text(weight: 600, size: size-small, fill: accent)[#category.name]
  #linebreak()
  #for group in category.groups {
    text(size: size-small, weight: 500)[#group.label:]
    h(3pt)
    text(size: size-small)[#group.items.join(", ")]
    linebreak()
  }
])

#let skills(skills-data, labels) = {
  section-heading(labels.sections.skills, "section-skills")
  // Four restrained text groups use a compact 2x2 matrix. Cells remain in
  // source order, so both PDF extractors see one deterministic reading stream.
  grid(
    columns: (1fr, 1fr),
    gutter: (column-gutter, space-section),
    ..skills-data.categories.map(_skill-category),
  )
}

#let education(edu, labels) = {
  section-heading(labels.sections.education, "section-education")
  for entry in edu {
    grid(
      columns: (1fr, auto),
      align: (left, right),
      {
        text(weight: 600)[#entry.degree]
        if "field" in entry { [ · #entry.field] }
        linebreak()
        text(size: size-small, fill: muted)[#entry.institution]
      },
      text(size: size-small, fill: muted)[#entry.year],
    )
    v(space-paragraph)
  }
}

#let languages(langs, labels) = {
  section-heading(labels.sections.languages, "section-languages")
  for proficiency in ("native", "fluent", "basic") {
    let names = langs.filter(language => language.proficiency == proficiency).map(
      language => language.name
    )
    if names.len() > 0 {
      text(size: size-small)[#names.join(" / ")]
      [ — ]
      text(size: size-small, fill: muted)[#labels.proficiency.at(proficiency)]
      linebreak()
    }
  }
}

#let volunteer(volunteer-data, labels) = {
  section-heading(labels.sections.volunteer, "section-volunteer")
  for category in volunteer-data.categories {
    text(size: size-small, weight: 600)[#category.name]
    linebreak()
    for entry in category.entries {
      text(size: size-small, fill: muted)[– #entry]
      linebreak()
    }
    v(space-paragraph)
  }
}

#let languages-and-volunteer(langs, volunteer-data, labels) = {
  // These short secondary sections share a row without becoming a sidebar.
  // Languages precedes Volunteer in source and extraction order.
  grid(
    columns: (1fr, 1fr),
    gutter: column-gutter,
    block(breakable: false, { languages(langs, labels) }),
    block(breakable: false, { volunteer(volunteer-data, labels) }),
  )
}

// Kept as a compatibility wrapper for templates that want the compact
// supplementary sections as one stream.
#let sidebar(data, labels) = {
  skills(data.skills, labels)
  education(data.education, labels)
  languages-and-volunteer(data.languages, data.volunteer, labels)
}
