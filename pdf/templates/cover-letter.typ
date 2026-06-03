#import "../styles.typ": *
#import "header.typ": header

#let data = json("../.cache/letter.json")
#let lang = sys.inputs.at("lang", default: "en")
#let has-signature = sys.inputs.at("has-signature", default: "0") == "1"
#let letter = data.letter

#set page(paper: "a4", margin: page-margin)
#set text(font: font-family, size: size-body, fill: body-color)
#set par(leading: 0.6em, justify: true)

// Letterhead — reuses the CV header so the letter visually matches the CV.
#header(data.personal)
#v(10pt)

// Right-aligned date (DIN 5008).
#align(right)[#text(size: size-body)[#letter.date_display]]
#v(6pt)

// Recipient address block.
#if letter.recipient != none {
  let r = letter.recipient
  [
    #if "name" in r and r.name != none [#r.name \ ]
    #if "company" in r and r.company != none [#r.company \ ]
    #if "address" in r and r.address != none {
      let a = r.address
      if "street" in a [#a.street \ ]
      let pc-city = ()
      if "postal_code" in a { pc-city.push(a.postal_code) }
      if "city" in a { pc-city.push(a.city) }
      if pc-city.len() > 0 [#pc-city.join(" ")]
    }
  ]
  v(14pt)
}

// Bold subject (Betreff).
#text(weight: 700)[#letter.subject]
#v(10pt)

// Salutation.
#letter.salutation
#v(8pt)

// Body paragraphs.
#for para in letter.body_paragraphs {
  [#para]
  parbreak()
}

#v(6pt)
// Closing + optional signature image + typed name.
#letter.closing
#v(4pt)
#if has-signature {
  image("/assets/signature.png", height: 36pt)
  v(2pt)
}
#letter.signer_name
