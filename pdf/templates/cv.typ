#import "../styles.typ": *

#let data = json("../.cache/data.json")

#set page(
  paper: "a4",
  margin: page-margin,
)
#set text(
  font: font-family,
  size: size-body,
  fill: body-color,
)

= #data.personal.name.given #data.personal.name.family
