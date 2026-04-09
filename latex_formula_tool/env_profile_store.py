from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from .backends import ServiceConfig


MANAGED_BLOCK_START = "# Managed model service profiles"
MANAGED_BLOCK_END = "# End model service profiles"
PROFILE_COUNT_KEY = "LLM_PROFILE_COUNT"
ACTIVE_PROFILE_KEY = "LLM_ACTIVE_PROFILE"
PROFILE_KEY_PATTERN = re.compile(r"^LLM_PROFILE_(\d+)_(NAME|API_KEY|BASE_URL|MODEL|NOTES)$")


@dataclass(frozen=True)
class LoadedProfiles:
    profiles: list[ServiceConfig]
    active_profile_name: str
    has_managed_profiles: bool


class EnvProfileStore:
    def __init__(self, env_path: Path) -> None:
        self.env_path = env_path

    def load_profiles(self) -> LoadedProfiles:
        values = self._read_values()
        indices = self._profile_indices(values)
        if not indices:
            return LoadedProfiles([], "", False)

        profiles: list[ServiceConfig] = []
        for index in indices:
            name = (values.get(f"LLM_PROFILE_{index}_NAME") or "").strip()
            if not name:
                continue
            profiles.append(
                ServiceConfig(
                    profile_name=name,
                    api_key=(values.get(f"LLM_PROFILE_{index}_API_KEY") or "").strip(),
                    base_url=(values.get(f"LLM_PROFILE_{index}_BASE_URL") or "").strip(),
                    model=(values.get(f"LLM_PROFILE_{index}_MODEL") or "").strip(),
                    extra_notes=(values.get(f"LLM_PROFILE_{index}_NOTES") or "").strip(),
                )
            )

        if not profiles:
            return LoadedProfiles([], "", False)

        active_name = self._resolve_active_profile_name(values, profiles)
        return LoadedProfiles(profiles, active_name, True)

    def load_legacy_defaults(self, fallback_base_url: str, fallback_model: str) -> list[ServiceConfig]:
        values = self._read_values()
        raw_api_key = (values.get("LLM_API_KEY") or values.get("DASHSCOPE_API_KEY") or "").strip()
        raw_base_url = (values.get("LLM_BASE_URL") or values.get("QWEN_BASE_URL") or "").strip()
        raw_model = (values.get("LLM_MODEL") or values.get("QWEN_VL_MODEL") or "").strip()
        if not any([raw_api_key, raw_base_url, raw_model]):
            return []

        api_key = raw_api_key
        base_url = raw_base_url or fallback_base_url
        model = raw_model or fallback_model
        return [
            ServiceConfig(
                profile_name="Default from .env",
                api_key=api_key,
                base_url=base_url,
                model=model,
                extra_notes="从项目根目录 .env 的旧式单变量配置生成。",
            )
        ]

    def save_profiles(self, profiles: list[ServiceConfig], active_profile_name: str) -> None:
        existing_lines = self._read_raw_lines()
        unmanaged_lines = self._strip_managed_block(existing_lines)
        managed_lines = self._build_managed_block(profiles, active_profile_name)

        new_lines = list(unmanaged_lines)
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.extend(managed_lines)
        self.env_path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")

    def _read_values(self) -> dict[str, str]:
        if not self.env_path.exists():
            return {}
        values = dotenv_values(self.env_path)
        return {str(key): str(value) for key, value in values.items() if value is not None}

    def _read_raw_lines(self) -> list[str]:
        if not self.env_path.exists():
            return []
        return self.env_path.read_text(encoding="utf-8").splitlines()

    def _profile_indices(self, values: dict[str, str]) -> list[int]:
        count = self._parse_int(values.get(PROFILE_COUNT_KEY, ""))
        indices = set()
        if count > 0:
            indices.update(range(1, count + 1))

        for key in values:
            match = PROFILE_KEY_PATTERN.match(key)
            if match:
                indices.add(int(match.group(1)))
        return sorted(indices)

    def _resolve_active_profile_name(
        self,
        values: dict[str, str],
        profiles: list[ServiceConfig],
    ) -> str:
        active_index = self._parse_int(values.get(ACTIVE_PROFILE_KEY, ""))
        if 1 <= active_index <= len(profiles):
            return profiles[active_index - 1].profile_name
        return profiles[0].profile_name

    @staticmethod
    def _parse_int(value: str) -> int:
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _format_env_value(value: str) -> str:
        escaped = (
            value.replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace('"', '\\"')
        )
        return f'"{escaped}"'

    def _strip_managed_block(self, lines: list[str]) -> list[str]:
        result: list[str] = []
        in_block = False
        for line in lines:
            stripped = line.strip()
            if stripped == MANAGED_BLOCK_START:
                in_block = True
                continue
            if stripped == MANAGED_BLOCK_END:
                in_block = False
                continue
            if in_block:
                continue

            key_match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
            if key_match:
                key = key_match.group(1)
                if key in {PROFILE_COUNT_KEY, ACTIVE_PROFILE_KEY} or PROFILE_KEY_PATTERN.match(key):
                    continue
            result.append(line)
        while result and not result[-1].strip():
            result.pop()
        return result

    def _build_managed_block(
        self,
        profiles: list[ServiceConfig],
        active_profile_name: str,
    ) -> list[str]:
        lines = [MANAGED_BLOCK_START]
        lines.append(f"{PROFILE_COUNT_KEY}={len(profiles)}")

        active_index = 1
        for index, profile in enumerate(profiles, start=1):
            if profile.profile_name == active_profile_name:
                active_index = index
                break
        lines.append(f"{ACTIVE_PROFILE_KEY}={active_index}")

        for index, profile in enumerate(profiles, start=1):
            lines.append(f"LLM_PROFILE_{index}_NAME={self._format_env_value(profile.profile_name)}")
            lines.append(f"LLM_PROFILE_{index}_API_KEY={self._format_env_value(profile.api_key)}")
            lines.append(f"LLM_PROFILE_{index}_BASE_URL={self._format_env_value(profile.base_url)}")
            lines.append(f"LLM_PROFILE_{index}_MODEL={self._format_env_value(profile.model)}")
            lines.append(f"LLM_PROFILE_{index}_NOTES={self._format_env_value(profile.extra_notes)}")
        lines.append(MANAGED_BLOCK_END)
        return lines
