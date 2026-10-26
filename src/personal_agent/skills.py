from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    content: str


class SkillLoader:
    """Scan local SKILL.md files and load full instructions on demand."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir.resolve()
        self.skills: dict[str, Skill] = {}

    def scan(self) -> None:
        self.skills.clear()
        if not self.skills_dir.is_dir():
            return
        for manifest in sorted(self.skills_dir.glob("*/SKILL.md")):
            resolved = manifest.resolve()
            if not manifest.is_file() or not resolved.is_relative_to(self.skills_dir):
                continue
            content = manifest.read_text(encoding="utf-8")
            metadata, body = self._parse_frontmatter(content)
            name = str(metadata.get("name", "")).strip() or manifest.parent.name
            description = str(metadata.get("description", "")).strip()
            if not description:
                description = next((line.lstrip("# ").strip() for line in body.splitlines() if line.strip()), "No description")
            self.skills[name] = Skill(name, " ".join(description.split()), content)

    def catalog(self) -> str:
        if not self.skills:
            return "(no skills available)"
        return "\n".join(f"- {skill.name}: {skill.description}" for skill in self.skills.values())

    def load(self, name: str) -> str:
        skill = self.skills.get(name.strip())
        if skill is None:
            available = ", ".join(self.skills) or "none"
            return f"skill error: unknown skill {name!r}; available: {available}"
        return skill.content

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
        if not content.startswith("---\n"):
            return {}, content
        parts = content.split("\n---\n", 1)
        if len(parts) != 2:
            return {}, content
        metadata: dict[str, str] = {}
        for line in parts[0][4:].splitlines():
            key, separator, value = line.partition(":")
            if separator:
                metadata[key.strip()] = value.strip().strip("\"'")
        return metadata, parts[1]


def build_system_prompt(workspace: Path, loader: SkillLoader) -> str:
    return (
        f"You are a coding agent working in {workspace.resolve()}. "
        "Use tools to inspect and modify the project. Act on the task, then report verified results.\n\n"
        f"Skills available:\n{loader.catalog()}\n\n"
        "When a skill applies, call load_skill with its exact name before following its instructions."
    )
