#import "../styles.typ": *

#let _maybe-photo() = {
  // Photo is included when build.py passes --input has-photo=1 (set iff
  // assets/photo.jpg exists). Path is resolved against typst --root (repo root).
  if sys.inputs.at("has-photo", default: "0") == "1" {
    align(center)[
      #box(clip: true, radius: 50%, width: 80pt, height: 80pt)[
        #image("/assets/photo.jpg", width: 80pt, height: 80pt, fit: "cover")
      ]
    ]
    v(8pt)
  }
}

#let _skills(skills) = {
  section-heading("Skills")
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

#let _languages(langs) = {
  section-heading("Languages")
  for l in langs {
    grid(
      columns: (1fr, auto),
      text(size: size-small)[#l.name],
      text(size: size-small, fill: muted)[#l.proficiency],
    )
    v(2pt)
  }
}

#let _volunteer(v_data) = {
  section-heading("Volunteer")
  for category in v_data.categories {
    text(weight: 600, size: size-small)[#category.name]
    v(2pt)
    text(size: size-small, fill: muted)[#category.entries.join(", ")]
    v(space-paragraph)
  }
}

#let sidebar(data) = {
  block(
    fill: sidebar-bg,
    inset: (x: 10pt, y: 10pt),
    stroke: (left: 3pt + accent),
    width: 100%,
  )[
    #_maybe-photo()
    #_skills(data.skills)
    #_languages(data.languages)
    #_volunteer(data.volunteer)
  ]
}
