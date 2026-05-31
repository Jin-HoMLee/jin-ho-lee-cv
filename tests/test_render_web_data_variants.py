import json
from pathlib import Path

VARIANTS_EN = Path(__file__).parent.parent / "web" / "src" / "data" / "content.en.variants.json"
VARIANTS_DE = Path(__file__).parent.parent / "web" / "src" / "data" / "content.de.variants.json"
BRIDGE_EN = Path(__file__).parent.parent / "web" / "src" / "data" / "content.en.json"
BRIDGE_DE = Path(__file__).parent.parent / "web" / "src" / "data" / "content.de.json"

def test_variants_json_valid():
    """Verify both variants JSON files exist and parse."""
    assert VARIANTS_EN.exists(), f"Missing {VARIANTS_EN}"
    assert VARIANTS_DE.exists(), f"Missing {VARIANTS_DE}"
    en = json.loads(VARIANTS_EN.read_text())
    de = json.loads(VARIANTS_DE.read_text())
    assert isinstance(en, dict)
    assert isinstance(de, dict)

def test_variants_en_de_parity():
    """EN and DE must have identical target keys."""
    en = json.loads(VARIANTS_EN.read_text())
    de = json.loads(VARIANTS_DE.read_text())
    assert en.keys() == de.keys(), f"Key mismatch: EN={en.keys()}, DE={de.keys()}"
    for target in en:
        en_override_keys = set(en[target].keys())
        de_override_keys = set(de[target].keys())
        assert en_override_keys == de_override_keys, \
            f"{target}: EN keys={en_override_keys}, DE keys={de_override_keys}"

def test_variants_no_bridge_leaks():
    """Variant values must actually differ from bridge."""
    bridge = json.loads(BRIDGE_EN.read_text())
    variants = json.loads(VARIANTS_EN.read_text())
    for target, overrides in variants.items():
        for key, value in overrides.items():
            bridge_val = bridge.get(key)
            assert value != bridge_val, \
                f"{target}.{key} == bridge.{key} (should differ); override invalid"

def test_variants_projects_exist():
    """All project IDs in selected_projects must be resolvable."""
    projects_dir = Path(__file__).parent.parent / "content" / "projects"
    for lang, variants_file in [("en", VARIANTS_EN), ("de", VARIANTS_DE)]:
        variants = json.loads(variants_file.read_text())
        for target, overrides in variants.items():
            if "selected_projects" in overrides:
                for proj_obj in overrides["selected_projects"]:
                    # selected_projects is array of full project objects; extract id
                    proj_id = proj_obj.get("id")
                    assert proj_id, f"{target}: project object missing 'id' field"
                    proj_path = projects_dir / f"{proj_id}.{lang}.yaml"
                    assert proj_path.exists(), \
                        f"Project {proj_id}.{lang}.yaml not found (referenced in {target})"
