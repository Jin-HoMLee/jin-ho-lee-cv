#import "../styles.typ": *
#import "header.typ": header
#import "profile.typ": profile
#import "experience.typ": experience
#import "selected_projects.typ": selected_projects
#import "publications.typ": publications
#import "awards.typ": awards
#import "sidebar.typ": sidebar

#let data = json("../.cache/data.json")
#let lang = sys.inputs.at("lang", default: "en")

#set page(
  paper: "a4",
  margin: page-margin,
  // Footer with name + page number, shown only on multi-page output so a
  // single-page build stays clean.
  footer: context {
    let total = counter(page).final().first()
    if total > 1 {
      set text(size: size-small, fill: muted)
      grid(
        columns: (1fr, auto),
        align: (left, right),
        [#data.personal.name.given #data.personal.name.family],
        [#counter(page).display() / #total],
      )
    }
  },
)
#set text(
  font: font-family,
  size: size-body,
  fill: body-color,
)
#set par(leading: 0.56em)

// Two-column layout in normal document flow so content paginates across pages
// when it exceeds one page: the breakable main column continues onto page 2,
// while the sidebar sizes to its content.
#header(data.personal, site-label: data.labels.misc.interactive_cv)
#v(6pt)

#grid(
  columns: sidebar-ratio,
  gutter: column-gutter,
  // Sidebar (column 1) gets the colored fill + left accent rule + padding as a
  // grid cell so the panel spans the page break and bottom-aligns with the main
  // column. The main column (0) is flush with no inset.
  fill: (x, _) => if x == 1 { sidebar-bg },
  stroke: (x, _) => if x == 1 { (left: 3pt + accent) },
  inset: (x, _) => if x == 1 { 10pt } else { 0pt },
  block(width: 100%, {
    profile(data.profile, data.labels)
    experience(data.experience, data.labels, lang)
    selected_projects(data.selected_projects, data.labels)
    publications(data)
    awards(data.awards, data.labels)
  }),
  sidebar(data, data.labels),
)
