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

#let _site-handle(url) = {
  // Strip scheme and any trailing slash → bare domain, e.g. "jinholee.is-a.dev".
  let s = url
  for prefix in ("https://", "http://") {
    if s.starts-with(prefix) {
      s = s.slice(prefix.len())
      break
    }
  }
  if s.ends-with("/") { s = s.slice(0, s.len() - 1) }
  s
}

#let _photo() = {
  // Photo is included when build.py passes --input has-photo=1 (set iff
  // assets/photo.jpg exists). Path is resolved against typst --root (repo root).
  if sys.inputs.at("has-photo", default: "0") == "1" {
    box(clip: true, radius: 50%, width: 78pt, height: 78pt)[
      #image("/assets/photo.jpg", width: 78pt, height: 78pt, fit: "cover")
    ]
  }
}

#let header(personal) = {
  grid(
    columns: (1fr, auto),
    column-gutter: 12pt,
    align: (left + top, right + top),
    {
      text(size: size-name, weight: 700, fill: accent)[
        #personal.name.given #personal.name.family
      ]
      linebreak()

      // Headline (already resolved to a string)
      text(size: size-headline, fill: muted)[#personal.headline]
      v(6pt)

      // Contact line — middot-separated
      let parts = ()
      parts.push(link("mailto:" + personal.email)[#personal.email])
      if "phone" in personal { parts.push(personal.phone) }

      // Address: full street/postal/city/country if private overlay supplied an address,
      // otherwise just city/country from the public location block.
      if "address" in personal {
        let addr = personal.address
        let addr-parts = ()
        if "street" in addr { addr-parts.push(addr.street) }
        // German convention: "postal_code city" as one chunk
        let pc-city = ()
        if "postal_code" in addr { pc-city.push(addr.postal_code) }
        if "city" in addr { pc-city.push(addr.city) }
        if pc-city.len() > 0 { addr-parts.push(pc-city.join(" ")) }
        if "country" in addr { addr-parts.push(addr.country) }
        if addr-parts.len() > 0 { parts.push(addr-parts.join(", ")) }
      } else {
        let loc = ()
        if "city" in personal.location { loc.push(personal.location.city) }
        if "country" in personal.location { loc.push(personal.location.country) }
        if loc.len() > 0 { parts.push(loc.join(", ")) }
      }

      if "linkedin" in personal.links and personal.links.linkedin != none {
        parts.push(link(personal.links.linkedin)[in/#_link-handle(personal.links.linkedin)])
      }
      if "github" in personal.links and personal.links.github != none {
        parts.push(link(personal.links.github)[gh/#_link-handle(personal.links.github)])
      }
      if "website" in personal.links and personal.links.website != none {
        // Accent-styled so the live/interactive site stands out in the muted line.
        parts.push(link(personal.links.website)[
          #text(fill: accent, weight: 500)[#_site-handle(personal.links.website)]
        ])
      }

      text(size: size-small, fill: muted)[#parts.join("  ·  ")]
    },
    _photo(),
  )

  v(4pt)
  line(length: 100%, stroke: 0.5pt + accent.lighten(60%))
}
