"""Regression coverage for L3's evidence-bounded multi-project representation."""

from scripts.content_loader import load_content


def test_l3_is_an_umbrella_portfolio_without_inventing_an_exact_count(content_dir):
    en = load_content(content_dir, lang="en", target="comp-bio")
    de = load_content(content_dir, lang="de", target="comp-bio")
    l3_en = en["projects"]["L3"]
    l3_de = de["projects"]["L3"]

    # Keep the Master's-period record distinct from later doctoral research.
    assert l3_en["role"] == "Graduate Researcher / Master's Candidate"
    assert l3_en["period"] == {"start": "2017-02", "end": "2018-08"}

    assert "Portfolio" in l3_en["title"]
    assert "multiple concurrent research streams" in l3_en["summary"]
    assert "Forschungsportfolio zur experimentellen Biophysik" in l3_de["title"]
    assert "mehrerer paralleler Forschungsstränge" in l3_de["summary"]

    en_detail = " ".join([l3_en["summary"], *l3_en["contributions"], l3_en["outcome"]])
    de_detail = " ".join([l3_de["summary"], *l3_de["contributions"], l3_de["outcome"]])
    for marker in (
        "COMBO-FISH",
        "single-molecule localization microscopy",
        "DNA-damage repair",
        "spatial point-pattern analysis",
        "DBSCAN",
        "international collaborations",
        "Bachelor’s and Master’s students",
        "third-party funding",
    ):
        assert marker in en_detail
    for marker in (
        "COMBO-FISH",
        "Einzelmolekül-Lokalisationsmikroskopie",
        "DNA-Schadensreparatur",
        "räumliche Punktmusteranalyse",
        "DBSCAN",
        "internationaler Kooperationen",
        "Bachelor- und Masterstudierenden",
        "Drittmittel",
    ):
        assert marker in de_detail

    # The recollected 4–5 count is not repository-verifiable, so the CV stays unnumbered.
    assert "4–5" not in en_detail
    assert "4-5" not in en_detail
    assert "vier bis fünf" not in de_detail.lower()


def test_l3_portfolio_leadership_surfaces_in_experience_and_comp_bio_profile(content_dir):
    en = load_content(content_dir, lang="en", target="comp-bio")
    de = load_content(content_dir, lang="de", target="comp-bio")

    en_research = next(entry for entry in en["experience"] if entry["id"] == "research")
    de_research = next(entry for entry in de["experience"] if entry["id"] == "research")
    en_l3 = next(bullet["en"] for bullet in en_research["bullets"] if bullet["refs"] == ["L3"])
    de_l3 = next(bullet["de"] for bullet in de_research["bullets"] if bullet["refs"] == ["L3"])

    assert "Coordinated concurrent" in en_l3
    assert "Parallele" in de_l3 and "koordiniert" in de_l3
    assert "multi-project" in en["profile"]["tagline"]
    assert "Forschungsportfolio paralleler Projekte" in de["profile"]["tagline"]
    assert "coordinated experimental-biophysics portfolio" in en["profile"]["paragraphs"][0]
    assert "koordiniertes Forschungsportfolio" in de["profile"]["paragraphs"][0]
