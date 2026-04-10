from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from .converters import normalize_latex, strip_code_fence
from .data_urls import image_file_to_data_url


load_dotenv()


DEFAULT_LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_LLM_MODEL = "qwen3-vl-plus"


@dataclass
class ServiceConfig:
    profile_name: str
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    extra_notes: str = ""


@dataclass(frozen=True)
class FormulaRequest:
    image_path: Path | None
    text_hint: str
    recognition_mode: Literal["formula", "paragraph"] = "formula"
    service_config: ServiceConfig | None = None


@dataclass
class FormulaResult:
    content: str
    raw_output: str
    backend_name: str
    recognition_mode: Literal["formula", "paragraph"] = "formula"
    warning: str | None = None


class FormulaBackend:
    display_name = "Backend"

    def generate(self, request: FormulaRequest) -> FormulaResult:
        raise NotImplementedError


class UniversalLLMBackend(FormulaBackend):
    display_name = "通用大模型接口（OpenAI 兼容）"

    def generate(self, request: FormulaRequest) -> FormulaResult:
        config = request.service_config or ServiceConfig(profile_name="Default")
        api_key = config.api_key or os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        base_url = config.base_url or os.getenv("LLM_BASE_URL") or os.getenv("QWEN_BASE_URL")
        model = config.model or os.getenv("LLM_MODEL") or os.getenv("QWEN_VL_MODEL")

        if not api_key:
            raise RuntimeError("未找到 API Key。请在服务配置中填写，或设置 LLM_API_KEY。")
        if not base_url:
            raise RuntimeError("未找到 Base URL。请在服务配置中填写，或设置 LLM_BASE_URL。")
        if not model:
            raise RuntimeError("未找到模型名。请在服务配置中填写，或设置 LLM_MODEL。")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("未安装 openai 包。请运行：pip install openai") from exc

        client = OpenAI(api_key=api_key, base_url=base_url)
        content: list[dict[str, object]] = [
            {
                "type": "text",
                "text": self._build_prompt(
                    request.text_hint,
                    bool(request.image_path),
                    request.recognition_mode,
                ),
            }
        ]
        if request.image_path:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": image_file_to_data_url(request.image_path)},
                }
            )

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You convert formula screenshots and Chinese/English descriptions "
                        "into exact LaTeX. Return only JSON."
                    ),
                },
                {"role": "user", "content": content},
            ],
            temperature=0,
        )

        raw = completion.choices[0].message.content or ""
        parsed = self._parse_jsonish(raw)
        content = parsed.get("content", "")
        if not content:
            content = parsed.get("latex", raw)
        if request.recognition_mode == "formula":
            content = normalize_latex(content)
        else:
            content = self._normalize_paragraph_content(content)
        notes = strip_code_fence(parsed.get("notes", "")).strip()

        return FormulaResult(
            content=content,
            raw_output=raw,
            backend_name=f"{self.display_name} / {config.profile_name}",
            recognition_mode=request.recognition_mode,
            warning=notes or None,
        )

    @staticmethod
    def _build_prompt(
        text_hint: str,
        has_image: bool,
        recognition_mode: Literal["formula", "paragraph"],
    ) -> str:
        source = "截图中的公式" if has_image else "用户的文字描述"
        hint = text_hint.strip() or "无额外说明"
        if recognition_mode == "paragraph":
            mode_instructions = """
识别模式：段落识别。
请输出 markdown 正文内容。
行内公式使用单个 $...$ 包裹。
单独成行的行间公式使用双 $$...$$ 包裹，并独占一行。
不要输出裸公式，不要使用 \\[...\\] 或 \\(...\\)，不要输出代码块。
JSON 字段必须包含 content、notes。
""".strip()
        else:
            mode_instructions = """
识别模式：单个公式。
请只输出单个公式的 LaTeX 主体，不要包裹 $、$$、\\[\\]。
JSON 字段必须包含 content、notes。
""".strip()
        return f"""
请把{source}转换为可复制的公式代码。

要求：
1. 输出严格 JSON，不要 Markdown，不要额外解释。
2. {mode_instructions}
3. 对模糊字符做最合理判断，并在 notes 中简短说明不确定处。

用户补充说明：
{hint}
""".strip()

    @staticmethod
    def _parse_jsonish(raw: str) -> dict[str, str]:
        text = strip_code_fence(raw)
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.S)
            if not match:
                return {}
            try:
                value = json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}

        if not isinstance(value, dict):
            return {}
        return {str(key): str(val) for key, val in value.items() if val is not None}

    @classmethod
    def _normalize_paragraph_content(cls, text: str) -> str:
        content = strip_code_fence(text).replace("\r\n", "\n").strip()
        if not content:
            return content

        # Normalize paragraph-mode math wrappers:
        # inline math -> $...$
        # display math / stand-alone formula lines -> $$...$$
        content = re.sub(
            r"\$\$(.*?)\$\$",
            lambda match: f"$${match.group(1).strip()}$$",
            content,
            flags=re.S,
        )
        content = re.sub(
            r"\\\[(.*?)\\\]",
            lambda match: f"$${match.group(1).strip()}$$",
            content,
            flags=re.S,
        )
        content = re.sub(
            r"\\\((.*?)\\\)",
            lambda match: f"${match.group(1).strip()}$",
            content,
            flags=re.S,
        )

        lines: list[str] = []
        for line in content.splitlines():
            stripped = line.strip()
            if re.fullmatch(r"\$[^$].*[^$]\$", stripped, re.S):
                lines.append(f"$${stripped[1:-1].strip()}$$")
            elif cls._looks_like_bare_math_line(stripped):
                lines.append(f"$${normalize_latex(stripped)}$$")
            else:
                lines.append(line)
        return "\n".join(lines).strip()

    @staticmethod
    def _looks_like_bare_math_line(line: str) -> bool:
        if not line or "$" in line:
            return False
        if re.match(r"^(#{1,6}\s|[-*+]\s|>\s|\d+\.\s)", line):
            return False

        has_math_signal = bool(
            re.search(r"(\\[A-Za-z]+|[_^=<>+\-*/]|≤|≥|≠|≈|∑|∫|∞|√)", line)
        )
        if not has_math_signal:
            return False

        # Avoid wrapping normal prose lines that simply mention a symbol.
        cjk_count = len(re.findall(r"[\u4e00-\u9fff]", line))
        if cjk_count > 4:
            return False

        cleaned = re.sub(r"\s+", "", line)
        cleaned = re.sub(r"[.,;:，。；：!?！？]", "", cleaned)
        return bool(re.fullmatch(r"[\w\\{}()\[\]^_=<>+\-*/|,&%~`'\"∞≤≥≠≈∑∫√]+", cleaned))
