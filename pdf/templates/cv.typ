#import "../styles.typ": *
#import "header.typ": header
#import "navigation.typ": navigation
#import "profile.typ": profile
#import "experience.typ": experience
#import "selected_projects.typ": selected_projects
#import "publications.typ": publications
#import "awards.typ": awards
#import "sidebar.typ": skills, education, languages-and-volunteer

#let data = json("../.cache/data.json")
#let lang = sys.inputs.at("lang", default: "en")

#set page(
  paper: "a4",
  margin: page-margin,
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
#set text(font: font-family, size: size-body, fill: body-color)
#set par(leading: 0.56em)
#set heading(numbering: none)

// Preserve semantic heading nodes for outlines and links while fully controlling
// their compact visual treatment in section-heading().
#show heading.where(level: 1): item => item.body

// A restrained single reading stream is intentional: both visual readers and
// ATS extractors encounter sections in exactly the same order.
#header(data.personal, site-label: data.labels.misc.interactive_cv)
#navigation(data.labels)

#profile(data.profile, data.labels)
#skills(data.skills, data.labels)
#experience(data.experience, data.labels, lang, data.project_links)
#selected_projects(data.selected_projects, data.labels)
#education(data.education, data.labels)
#publications(data)
#awards(data.awards, data.labels)
#languages-and-volunteer(data.languages, data.volunteer, data.labels)
