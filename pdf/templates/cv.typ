#import "../styles.typ": *
#import "header.typ": header
#import "profile.typ": profile
#import "experience.typ": experience
#import "selected_projects.typ": selected_projects
#import "education.typ": education
#import "awards.typ": awards
#import "sidebar.typ": sidebar

#let data = json("../.cache/data.json")
#let lang = sys.inputs.at("lang", default: "en")

#set page(
  paper: "a4",
  margin: page-margin,
)
#set text(
  font: font-family,
  size: size-body,
  fill: body-color,
)
#set par(leading: 0.56em)

// Use layout() so the columns grid fills the remaining page height after the
// header. This bottom-aligns the main column and the sidebar — without this
// the grid auto-sizes each cell to its content and the shorter column leaves
// whitespace below it.
#layout(size => {
  grid(
    columns: 1,
    rows: (auto, 1fr),
    {
      header(data.personal)
      v(6pt)
    },
    grid(
      columns: sidebar-ratio,
      gutter: column-gutter,
      // Main column — block fills the grid cell so its height matches the sidebar.
      block(width: 100%, height: 100%, {
        profile(data.profile, data.labels)
        experience(data.experience, data.labels, lang)
        selected_projects(data.selected_projects, data.labels)
        education(data.education, data.labels)
        awards(data.awards, data.labels)
      }),
      sidebar(data, data.labels),
    ),
  )
})
