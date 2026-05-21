#import "../styles.typ": *

#let _link-handle(url) = {
  // Strip "https://linkedin.com/in/" etc. to just the handle.
  let s = url
  for prefix in (
    "https://linkedin.com/in/",
    "https://www.linkedin.com/in/",
    "https://github.com/",
    "https://www.github.com/",
    "https://researchgate.net/profile/",
    "https://www.researchgate.net/profile/",
  ) {
    if s.starts-with(prefix) {
      s = s.slice(prefix.len())
      break
    }
  }
  s
}

#let header(personal) = {
  text(size: size-name, weight: 700, fill: accent)[
    #personal.name.given #personal.name.family
  ]
  linebreak()

  // Headline (already resolved to a string)
  text(size: size-headline, fill: muted)[#personal.headline]
  v(6pt)

  // Contact line — middot-separated
  let parts = ()
  parts.push(personal.email)
  if "phone" in personal { parts.push(personal.phone) }

  let loc = ()
  if "city" in personal.location { loc.push(personal.location.city) }
  if "country" in personal.location { loc.push(personal.location.country) }
  if loc.len() > 0 { parts.push(loc.join(", ")) }

  if "linkedin" in personal.links and personal.links.linkedin != none {
    parts.push("in/" + _link-handle(personal.links.linkedin))
  }
  if "github" in personal.links and personal.links.github != none {
    parts.push("gh/" + _link-handle(personal.links.github))
  }

  text(size: size-small, fill: muted)[#parts.join("  ·  ")]

  v(4pt)
  line(length: 100%, stroke: 0.5pt + accent.lighten(60%))
}
