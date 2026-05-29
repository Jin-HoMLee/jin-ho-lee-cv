// Types matching the shape produced by scripts/render_web_data.py.
// If the Python dump shape changes, update here in lockstep.

export type Lang = "en" | "de";

export interface Name { given: string; family: string }
export interface Location { city: string; country: string }
export interface Links {
  linkedin: string | null;
  github: string | null;
  researchgate: string | null;
  website: string | null;
  orcid: string | null;
}
export interface Personal {
  name: Name;
  headline: string;
  email: string;
  location: Location;
  links: Links;
  photo: string;
}

export interface Profile {
  tagline: string;
  paragraphs: string[];
}

export interface SkillGroup { label: string; items: string[] }
export interface SkillCategory { name: string; groups: SkillGroup[] }
export interface Skills { categories: SkillCategory[] }

export interface Period { start: string; end: string | null }

// Education in this CV uses a flat shape (single graduation year, no start/end period).
export interface Education {
  degree: string;
  field?: string;
  institution: string;
  location: string;
  year: number;
}

// Experience bullets carry both languages inline (mixed dict — the langstring
// resolver intentionally does not flatten dicts that have non-2-letter keys
// like `refs`). Components pick the right text via `bullet[lang]`.
export interface ExperienceBullet {
  en: string;
  de: string;
  refs?: string[];
}
export interface Org { name: string; url: string | null }
export interface Experience {
  id: string;
  org: Org;
  role: string;
  period: Period;
  bullets: ExperienceBullet[];
}

export interface Project {
  id: string;
  category: "life-science" | "data-science" | "consulting";
  title: string;
  summary: string;
  role: string;
  period: Period;
  technologies: string[];
  contributions: string[];
  outcome: string;
}

export interface Language { name: string; proficiency: string }

export interface VolunteerCategory { name: string; entries: string[] }
export interface Volunteer { categories: VolunteerCategory[] }

export interface Award {
  title: string;
  issuer: string;
  year: number;
  note?: string;
}

export type PublicationType = "article" | "book-chapter" | "conference" | "book";
export type AuthorshipType = "first" | "shared" | "middle" | "last" | "corresponding";
export interface Publication {
  key: string;
  title: string;
  year: number;
  type: PublicationType;
  category: "research" | "applied";
  authorship: AuthorshipType;
  authors: string[];
  venue: string | null;
  doi: string | null;
}

export interface Labels {
  sections: {
    profile: string;
    experience: string;
    education: string;
    awards: string;
    skills: string;
    languages: string;
    volunteer: string;
  };
  months_abbr: string[]; // resolved to the page's language
  proficiency: {
    native: string;
    fluent: string;
    basic: string;
    passive: string;
  };
  misc: {
    present: string;
  };
}

export interface ContentData {
  personal: Personal;
  profile: Profile;
  skills: Skills;
  education: Education[];
  experience: Experience[];
  projects: Record<string, Project>;
  languages: Language[];
  volunteer: Volunteer;
  awards: Award[];
  publications: Publication[];
  labels: Labels;
}
