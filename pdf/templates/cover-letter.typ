#import "attachment.typ": *

#let data = json("../.cache/letter.json")
#let lang = sys.inputs.at("lang", default: "en")
#let has-signature = sys.inputs.at("has-signature", default: "0") == "1"
#let letter = data.letter
#let author = data.personal.name.given + " " + data.personal.name.family
#let document-label = if lang == "de" { "Anschreiben" } else { "Cover Letter" }

#attachment-document(
  letter.subject,
  author,
  data.personal,
  document-label,
)[
  // The formal letterhead intentionally omits the sender street address. The
  // phone remains an explicit per-letter opt-in from application.yaml.
  #attachment-masthead(
    data.personal,
    document-label,
    date: letter.date_display,
    show-phone: letter.include_phone,
  )
  #v(8pt)

  #if letter.recipient != none {
    attachment-recipient(letter.recipient)
    v(10pt)
  }

  #attachment-subject(letter.subject)
  #v(8pt)

  // Body blocks: paragraphs (with **bold** spans) and accent-bullet lists.
  // Parsing lives in scripts/cover_letter_core.py so PDF + text never diverge.
  #let render-spans(spans) = {
    for s in spans {
      if s.bold { text(weight: 700)[#s.text] } else { [#s.text] }
    }
  }
  #for blk in letter.body_blocks {
    if blk.at("type") == "bullet_list" {
      for (i, item) in blk.items.enumerate() {
        if i > 0 { v(2pt) }
        grid(
          columns: (8pt, 1fr),
          gutter: 4pt,
          text(fill: attachment-gold)[•],
          render-spans(item),
        )
      }
      parbreak()
    } else {
      render-spans(blk.spans)
      parbreak()
    }
  }

  #v(4pt)
  #letter.closing
  #v(4pt)
  #if has-signature {
    image("/assets/signature.png", height: 36pt)
    v(2pt)
  }
  #letter.signer_name
]
