#import "../styles.typ": *
#import "header.typ": header

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

#header(data.personal)
