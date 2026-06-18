# LaTeX Formula Tool

一个桌面工具，用于识别图片公式、提取 PDF 内容、做 Pandoc 文档转换，并支持导出为 Markdown / Word / PDF / HTML。

## 主要功能

- 图片公式识别
- 段落识别并输出 Markdown
- PDF 按页提取为 Markdown
- Markdown 导出 Word
- Markdown 导出 PDF
- Markdown 导出 HTML
- Word 转 Markdown
- Word 转 TeX
- Markdown 转 Word
- 顶部多选项卡页面切换
- 本地输入目录 / 输出目录选择
- 一键生成带公式的测试样例

## 运行环境

项目统一使用项目内 `.venv`：

```powershell
cd E:\Projects\Latex_tools
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Pandoc

运行 `run_app.bat` 时会自动安装项目内 Pandoc，默认位置：

```text
E:\Projects\Latex_tools\.venv\tools\pandoc\pandoc.exe
```

Word / PDF / HTML 导出和文档转换会优先使用这个项目内 Pandoc。

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

也可以直接在软件界面里新增、切换、保存多个服务档案。

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

## 页面结构

顶部有两个页面：

- `识别`
  通过下拉模式切换：
  - 单个公式模式
  - 段落识别模式
  - PDF 提取模式
- `文件转换`
  适合 Word / Markdown / TeX / PDF / HTML 的本地文件转换，并支持输入目录、输出目录选择。

## 文件转换页功能

- Word 转 Markdown
- Word 转 TeX
- Markdown 转 Word
- Markdown 转 PDF
- Markdown 转 HTML
- 打开输入目录
- 打开输出目录
- 一键生成 `pandoc_formula_demo.md` 测试样例

## 说明

- PDF 提取采用“逐页渲染图片 + 视觉模型识别 + 页面文本辅助提示”的方式，尽量保持公式和符号准确。
- 复制到 Word 会同时写入 HTML 和纯文本格式，兼容性比单纯复制 Markdown 更好。
- PDF 输出默认会放到 `outputs/<pdf文件名>/`，也可以在界面中改成本地任意目录。
- 文件转换页支持一键生成测试 Markdown，方便验证公式在 Word / PDF / HTML 中的互转效果。
