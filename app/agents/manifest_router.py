"""Manifest-based routing utility for Nature Skills agents.

Loads manifest.yaml, resolves axis values, and provides
the routing protocol defined in each skill's SKILL.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ManifestRouter:
    """Load and resolve a Nature Skills manifest.yaml."""

    def __init__(self, agent_dir: str | Path):
        self.agent_dir = Path(agent_dir)
        manifest_path = self.agent_dir / "manifest.yaml"
        if manifest_path.exists():
            with open(manifest_path, encoding="utf-8") as f:
                self._data: dict[str, Any] = yaml.safe_load(f) or {}
        else:
            self._data = {}

    # ── Properties ──

    @property
    def name(self) -> str:
        return self._data.get("name", "")

    @property
    def version(self) -> str:
        return self._data.get("version", "0.0.0")

    @property
    def always_load(self) -> list[str]:
        """Files that must be loaded on every invocation."""
        return self._data.get("always_load", [])

    @property
    def axes(self) -> dict[str, dict]:
        """Declared axes: {axis_name: {values: {...}, multi: bool}}."""
        return self._data.get("axes", {})

    @property
    def on_demand_references(self) -> list[dict]:
        """On-demand reference entries: [{condition: ..., path: ...}]."""
        return self._data.get("references", {}).get("on_demand", [])

    # ── Core loading ──

    def load_core_fragments(self) -> dict[str, str]:
        """Read all always_load files and return {relative_path: content}."""
        result: dict[str, str] = {}
        for rel_path in self.always_load:
            full = self.agent_dir / rel_path
            if full.exists():
                result[rel_path] = full.read_text(encoding="utf-8")
        return result

    # ── Axis resolution ──

    def resolve_axis(self, axis_name: str, value: str) -> str | None:
        """Return the fragment path for a given axis value, or None."""
        axis = self.axes.get(axis_name, {})
        return axis.get("values", {}).get(value)

    def load_axis_fragment(self, axis_name: str, value: str) -> str | None:
        """Load the fragment file for a specific axis value."""
        rel_path = self.resolve_axis(axis_name, value)
        if rel_path is None:
            return None
        full = self.agent_dir / rel_path
        if full.exists():
            return full.read_text(encoding="utf-8")
        return None

    def load_axis_fragments(self, axis_name: str, values: list[str]) -> dict[str, str]:
        """Load fragments for multiple axis values (multi=True axes)."""
        result: dict[str, str] = {}
        for v in values:
            content = self.load_axis_fragment(axis_name, v)
            if content is not None:
                result[v] = content
        return result

    # ── On-demand references ──

    def load_reference(self, ref_path: str) -> str | None:
        """Load an on-demand reference by its relative path."""
        full = self.agent_dir / ref_path
        if full.exists():
            return full.read_text(encoding="utf-8")
        return None

    # ── Routing summary ──

    def routing_summary(self) -> dict[str, Any]:
        """Return a summary of the manifest for debugging/logging."""
        return {
            "name": self.name,
            "version": self.version,
            "always_load_count": len(self.always_load),
            "axes": {k: list(v.get("values", {}).keys()) for k, v in self.axes.items()},
            "on_demand_count": len(self.on_demand_references),
        }
