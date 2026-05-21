#import "../styles.typ": *
#import "header.typ": header
#import "profile.typ": profile
#import "experience.typ": experience

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
#v(6pt)

#grid(
  columns: sidebar-ratio,
  gutter: column-gutter,
  // Main column
  {
    profile(data.profile)
    experience(data.experience)
  },
  // Sidebar (placeholder until Task 7)
  rect(fill: sidebar-bg, width: 100%, height: 100%)[],
)
