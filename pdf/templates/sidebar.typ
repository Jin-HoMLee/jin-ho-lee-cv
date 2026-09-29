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

#let _skill-column(categories, gap) = block(breakable: false, {
  for (i, category) in categories.enumerate() {
    if i > 0 { v(gap) }
    _skill-category(category)
  }
})

#let skills(skills-data, labels) = {
  section-heading(labels.sections.skills, "section-skills")
  // Two independent text columns, not row-aligned cells. Categories flow in
  // category_order: left column takes the first half, right the rest, so a
  // column-then-column text extract matches the target order (web stays
  // aligned via the same category_order source).
  let categories = skills-data.categories
  let split = calc.ceil(categories.len() / 2)
  let left = categories.slice(0, split)
  let right = categories.slice(split)
  grid(
    columns: (1fr, 1fr),
    gutter: column-gutter,
    _skill-column(left, space-paragraph),
    _skill-column(right, space-section + 3pt),
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
