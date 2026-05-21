#import "../styles.typ": *

#let _maybe-photo() = {
  // Photo lives at repo_root/assets/photo.jpg. From this file (pdf/templates/sidebar.typ),
  // the relative path is ../../assets/photo.jpg. typst gracefully errors if missing;
  // we wrap in a context that warns instead via build-time presence check below.
  // For now, conditionally include based on a sidecar marker.
  // (Implementation note: presence is checked in build.py; if missing, it removes
  //  pdf/.cache/has-photo. We check existence of that marker here.)
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
      text(size: size-small, fill: muted)[#group.label: ]
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
