# LaTeX Formula Tool

一个桌面工具，用于从图片或 PDF 中提取包含公式的内容，并整理为 Markdown，再可选导出为 Word。

## 功能

- 图片公式识别
- 段落识别并输出 Markdown
- 独立的 `PDF 文档模式`
- `PDF -> Markdown -> Word(.docx)` 流程
- MathJax 预览公式
- 多服务档案管理，兼容 OpenAI 风格接口

## 安装

```powershell
cd E:\Projects\Latex_tools
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

项目运行环境统一使用项目内的 `.venv`。

## 项目内 Pandoc

Word 导出优先使用项目内的 Pandoc，不依赖系统 PATH。

运行 `run_app.bat` 时，会自动下载 Pandoc 到：

```text
E:\Projects\Latex_tools\.venv\tools\pandoc\pandoc.exe
```

如果该位置不存在，程序才会回退到系统里的 `pandoc`。

## 模型配置

服务档案保存在项目根目录 `.env` 中。示例：

```env
LLM_PROFILE_COUNT=1
LLM_ACTIVE_PROFILE=1
LLM_PROFILE_1_NAME="DashScope Qwen VL"
LLM_PROFILE_1_API_KEY="sk-..."
LLM_PROFILE_1_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_PROFILE_1_MODEL="qwen3-vl-plus"
LLM_PROFILE_1_NOTES=""
```

也可以在桌面端界面中直接新增、切换、保存多个服务档案。

## 启动

```powershell
python -m latex_formula_tool
```

或：

```powershell
pip install -e .
latex-formula-tool
```

也可以直接双击：

```text
run_app.bat
```

## 模式

- `单个公式模式`：输出单条 LaTeX
- `段落识别模式`：输出 Markdown
- `PDF 文档模式`：选择 PDF，逐页提取为 Markdown，可再导出为 Word

PDF 模式默认输出到 `outputs/<pdf文件名>/`。

## 说明

- PDF 提取当前采用“逐页渲染图片 + 视觉模型识别 + 页面文本辅助提示”的方式，目标是尽量保持公式和符号准确。
- Markdown 中的公式按 `$...$` 和 `$$...$$` 组织，便于 MathJax 和 Pandoc 处理。
- 如果项目内 `.venv\tools\pandoc\pandoc.exe` 已存在，Word 导出会优先使用它。
