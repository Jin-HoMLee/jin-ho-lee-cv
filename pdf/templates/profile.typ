#import "../styles.typ": *

#let profile(p, labels) = {
  section-heading(labels.sections.profile)

  if "tagline" in p {
    text(weight: 600)[#p.tagline]
    v(space-paragraph)
  }

  for para in p.paragraphs {
    par(justify: true)[#para]
    v(space-paragraph)
  }
}
