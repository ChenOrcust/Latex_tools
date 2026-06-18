from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import fitz  # PyMuPDF

from .backends import FormulaRequest, FormulaResult, ServiceConfig, UniversalLLMBackend
from .runtime_paths import bundled_pandoc_dir


ProgressCallback = Callable[[int, int, str], None]
PANDOC_MARKDOWN_READER = "markdown+tex_math_dollars+tex_math_single_backslash+raw_tex"
PANDOC_MARKDOWN_WRITER = "markdown+tex_math_dollars+pipe_tables"


@dataclass
class PdfConversionResult:
    markdown_text: str
    markdown_path: Path | None
    docx_path: Path | None
    page_count: int
    results: list[FormulaResult]


def render_pdf_page_to_image(pdf_path: Path, page_index: int, zoom: float = 1.8) -> Path:
    document = fitz.open(pdf_path)
    try:
        page = document[page_index]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        temp_dir = Path(tempfile.mkdtemp(prefix="latex_tool_pdf_"))
        image_path = temp_dir / f"page_{page_index + 1:04d}.png"
        pixmap.save(image_path)
        return image_path
    finally:
        document.close()


def extract_pdf_pages_to_markdown(
    pdf_path: Path,
    service_config: ServiceConfig,
    output_dir: Path | None = None,
    backend: UniversalLLMBackend | None = None,
    progress: ProgressCallback | None = None,
) -> PdfConversionResult:
    backend = backend or UniversalLLMBackend()
    document = fitz.open(pdf_path)
    results: list[FormulaResult] = []
    chunks: list[str] = []

    try:
        for page_index in range(document.page_count):
            if progress:
                progress(page_index + 1, document.page_count, f"rendering page {page_index + 1}")
            page = document[page_index]
            image_path = render_pdf_page_to_image(pdf_path, page_index)
            page_text = page.get_text("text").strip()
            request = FormulaRequest(
                image_path=image_path,
                text_hint=(
                    f"PDF page {page_index + 1}/{document.page_count}.\nExtracted text:\n{page_text}"
                    if page_text
                    else f"PDF page {page_index + 1}/{document.page_count}."
                ),
                recognition_mode="paragraph",
                service_config=service_config,
            )
            if progress:
                progress(page_index + 1, document.page_count, f"recognizing page {page_index + 1}")
            result = backend.generate(request)
            results.append(result)
            chunks.append(f"<!-- Page {page_index + 1} -->\n{result.content.strip()}")
    finally:
        document.close()

    markdown_text = "\n\n---\n\n".join(chunk for chunk in chunks if chunk.strip()).strip()
    markdown_path = None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_dir / f"{pdf_path.stem}.md"
        markdown_path.write_text(markdown_text, encoding="utf-8")

    return PdfConversionResult(
        markdown_text=markdown_text,
        markdown_path=markdown_path,
        docx_path=None,
        page_count=len(results),
        results=results,
    )


def export_markdown_to_docx(markdown_path: Path, docx_path: Path) -> None:
    _run_pandoc(
        [
            "--from",
            PANDOC_MARKDOWN_READER,
            str(markdown_path),
            "-o",
            str(docx_path),
        ],
        "Pandoc 转 Word 失败。",
    )


def convert_docx_to_markdown(docx_path: Path, markdown_path: Path) -> None:
    media_dir = markdown_path.with_name(f"{markdown_path.stem}_media")
    _run_pandoc(
        [
            "--from",
            "docx",
            "--to",
            PANDOC_MARKDOWN_WRITER,
            "--wrap=none",
            "--extract-media",
            str(media_dir),
            str(docx_path),
            "-o",
            str(markdown_path),
        ],
        "Pandoc Word 转 Markdown 失败。",
    )


def convert_docx_to_tex(docx_path: Path, tex_path: Path) -> None:
    _run_pandoc(
        [
            "--from",
            "docx",
            "--to",
            "latex",
            "--standalone",
            str(docx_path),
            "-o",
            str(tex_path),
        ],
        "Pandoc Word 转 TeX 失败。",
    )


def convert_markdown_file_to_docx(markdown_path: Path, docx_path: Path) -> None:
    export_markdown_to_docx(markdown_path, docx_path)


def convert_markdown_file_to_pdf(markdown_path: Path, pdf_path: Path) -> None:
    _run_pandoc(
        [
            "--from",
            PANDOC_MARKDOWN_READER,
            str(markdown_path),
            "-o",
            str(pdf_path),
        ],
        "Pandoc Markdown 转 PDF 失败。",
    )


def convert_markdown_file_to_html(markdown_path: Path, html_path: Path) -> None:
    _run_pandoc(
        [
            "--from",
            PANDOC_MARKDOWN_READER,
            "--to",
            "html5",
            "--standalone",
            "--mathml",
            str(markdown_path),
            "-o",
            str(html_path),
        ],
        "Pandoc Markdown 转 HTML 失败。",
    )


def convert_markdown_to_html(markdown_text: str) -> str:
    pandoc_executable = find_pandoc_executable()
    if pandoc_executable is None:
        raise RuntimeError(
            "未找到 Pandoc。\n"
            f"请先运行启动脚本自动安装，或确认 {bundled_pandoc_dir()}\\pandoc.exe 存在。"
        )

    command = [
        str(pandoc_executable),
        "--from",
        PANDOC_MARKDOWN_READER,
        "--to",
        "html5",
        "--standalone",
        "--mathml",
    ]
    completed = subprocess.run(
        command,
        input=markdown_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Pandoc 转 HTML 失败。"
            + (f"\n{completed.stderr.strip()}" if completed.stderr.strip() else "")
        )
    return completed.stdout


def _run_pandoc(arguments: list[str], error_message: str) -> None:
    pandoc_executable = find_pandoc_executable()
    if pandoc_executable is None:
        raise RuntimeError(
            "未找到 Pandoc。\n"
            f"请先运行启动脚本自动安装，或确认 {bundled_pandoc_dir()}\\pandoc.exe 存在。"
        )

    completed = subprocess.run(
        [str(pandoc_executable), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            error_message + (f"\n{completed.stderr.strip()}" if completed.stderr.strip() else "")
        )


def find_pandoc_executable() -> Path | None:
    candidates = [
        bundled_pandoc_dir() / "pandoc.exe",
        bundled_pandoc_dir() / "pandoc",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    system_pandoc = shutil.which("pandoc")
    if system_pandoc:
        return Path(system_pandoc)
    return None
