from pathlib import Path

from personal_agent.skills import SkillLoader, build_system_prompt
from personal_agent.tools.skills import create_skill_tools


def test_skill_loader_catalog_and_load(tmp_path: Path):
    skill_dir = tmp_path / "skills" / "testing"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: testing\ndescription: Test things carefully.\n---\n# Full instructions\n", encoding="utf-8")
    loader = SkillLoader(tmp_path / "skills")
    loader.scan()
    assert "testing: Test things carefully." in loader.catalog()
    assert "Full instructions" in loader.load("testing")
    assert "unknown skill" in loader.load("missing")


def test_load_skill_is_a_registered_tool(tmp_path: Path):
    loader = SkillLoader(tmp_path / "skills")
    loader.scan()
    (tmp_path / "skills").mkdir()
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\ndemo content", encoding="utf-8")
    loader.scan()
    tool = create_skill_tools(loader)[0]
    assert tool.name == "load_skill"
    assert tool.handler({"name": "demo"}) == "---\nname: demo\ndescription: demo\n---\ndemo content"


def test_system_prompt_contains_catalog(tmp_path: Path):
    loader = SkillLoader(tmp_path / "skills")
    loader.skills["demo"] = type("SkillValue", (), {"name": "demo", "description": "demo skill", "content": "full"})()
    prompt = build_system_prompt(tmp_path, loader)
    assert "demo: demo skill" in prompt
    assert "load_skill" in prompt
