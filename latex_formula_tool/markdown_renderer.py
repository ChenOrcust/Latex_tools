from __future__ import annotations

import html
import re


def build_markdown_html(markdown_text: str) -> str:
    try:
        import markdown
    except ImportError as exc:
        raise RuntimeError("未安装 markdown 包，无法渲染 Markdown 预览。") from exc

    normalized = _promote_formula_lines(markdown_text)

    body = markdown.markdown(
        normalized,
        extensions=["extra", "sane_lists", "nl2br"],
        output_format="html5",
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <script>
    window.MathJax = {{
      tex: {{
        inlineMath: [['$', '$']],
        displayMath: [['$$', '$$']],
        processEscapes: true
      }},
      options: {{
        skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
      }}
    }};
  </script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
  <style>
    body {{
      margin: 0;
      padding: 18px 20px;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      font-size: 15px;
      line-height: 1.65;
      color: #111827;
      background: #ffffff;
      word-break: break-word;
    }}
    p, li {{
      margin: 0 0 0.75em;
    }}
    pre, code {{
      font-family: Consolas, "Courier New", monospace;
    }}
    pre {{
      background: #f6f8fa;
      border: 1px solid #d0d7de;
      border-radius: 6px;
      padding: 12px;
      overflow-x: auto;
    }}
    blockquote {{
      margin: 0;
      padding-left: 12px;
      border-left: 3px solid #d0d7de;
      color: #4b5563;
    }}
    .formula-line {{
      margin: 0.9em 0;
      text-align: center;
      font-size: 1.08em;
    }}
  </style>
</head>
<body>
{body}
</body>
</html>"""


def wrap_formula_as_markdown(latex: str) -> str:
    clean = latex.strip()
    if not clean:
        return ""
    return f"${html.escape(clean, quote=False)}$"


def _promote_formula_lines(markdown_text: str) -> str:
    lines: list[str] = []
    for raw_line in markdown_text.splitlines():
        stripped = raw_line.strip()
        if re.fullmatch(r"\$[^$].*[^$]\$", stripped):
            lines.append(f'<div class="formula-line">{stripped}</div>')
        else:
            lines.append(raw_line)
    return "\n".join(lines)
