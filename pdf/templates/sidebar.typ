#import "../styles.typ": *

#let skills(skills-data, labels) = {
  section-heading(labels.sections.skills, "section-skills")
  for category in skills-data.categories {
    text(weight: 600, size: size-small, fill: accent)[#category.name]
    linebreak()
    for group in category.groups {
      text(size: size-small, weight: 500)[#group.label:]
      h(3pt)
      text(size: size-small)[#group.items.join(", ")]
      linebreak()
    }
    v(space-paragraph)
  }
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
    text(size: size-small, weight: 600)[#category.name:]
    h(3pt)
    text(size: size-small, fill: muted)[#category.entries.join(", ")]
  }
}

// Kept as a compatibility wrapper for templates that want the compact
// supplementary sections as one stream.
#let sidebar(data, labels) = {
  skills(data.skills, labels)
  education(data.education, labels)
  languages(data.languages, labels)
  volunteer(data.volunteer, labels)
}
