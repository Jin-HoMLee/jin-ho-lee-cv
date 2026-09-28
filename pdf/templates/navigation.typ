#import "../styles.typ": *

// Compact in-document contents line. The links are optional annotations over
// complete visible labels; all section content remains ordinary page text.
#let navigation(labels) = {
  let items = (
    ("section-profile", labels.sections.profile),
    ("section-skills", labels.sections.skills),
    ("section-experience", labels.sections.experience),
    ("section-projects", labels.sections.selected_projects),
    ("section-education", labels.sections.education),
    ("section-publications", labels.sections.publications),
  )
  block(width: 100%, inset: (y: 3pt), stroke: (bottom: 0.4pt + accent.lighten(70%)), [
    #align(center)[
      #text(size: size-small, fill: muted)[
        #for (i, item) in items.enumerate() {
          if i > 0 { [ · ] }
          link(label(item.at(0)))[#text(fill: accent)[#item.at(1)]]
        }
      ]
    ]
  ])
}
