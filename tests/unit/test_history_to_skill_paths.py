from pathlib import Path

import pytest

from app.core.history_to_skill import SkillMaterial, generate_skill, search_history


def test_history_search_rejects_extra_root_outside_allowed_dirs(tmp_path):
    with pytest.raises(ValueError):
        search_history("qwen", extra_roots=[str(tmp_path)])


def test_generate_skill_rejects_output_dir_outside_skill_root(tmp_path):
    with pytest.raises(ValueError):
        generate_skill(
            "qwen",
            material=SkillMaterial(model_name="qwen"),
            output_dir=str(tmp_path),
        )


def test_generate_skill_allows_default_output_dir(monkeypatch, tmp_path):
    import app.core.history_to_skill as hts

    safe_root = tmp_path / ".codex" / "skills"
    monkeypatch.setattr(hts, "SKILL_OUTPUT_ROOT", safe_root)

    result = hts.generate_skill("Qwen Test", hts.SkillMaterial(model_name="Qwen Test"))

    assert result.success is True
    assert Path(result.skill_md_path).exists()
