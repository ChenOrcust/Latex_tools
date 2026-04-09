# LaTeX Formula Tool

一个 PyQt 桌面工具，可以从截图、剪贴板图片、图片文件或文字描述中识别单个公式或段落文字，并在界面中统一使用 Markdown 渲染预览。

## 功能

- 粘贴剪贴板截图或图片，快捷键 `Ctrl+V`
- 框选屏幕区域截图
- 打开本地图片
- 输入文字描述生成公式或带公式的段落
- 统一使用 OpenAI 兼容大模型接口
- 支持新建、删除、保存多个模型服务档案
- 自动记住上次使用的模型服务配置
- 支持“单个公式模式”和“段落识别模式”
- 使用 `Markdown + MathJax` 渲染预览
- 内置 LaTeX 公式代码速查帮助
- 一键复制识别结果

## 安装

```powershell
cd E:\Projects\Latex_tools
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 配置通用模型接口

服务档案现在保存在项目根目录的 `.env` 文件中；`.gitignore` 已忽略它，因此默认不会提交到 Git。

推荐把默认参数放到 `.env`：

```env
LLM_PROFILE_COUNT=1
LLM_ACTIVE_PROFILE=1
LLM_PROFILE_1_NAME="DashScope Qwen VL"
LLM_PROFILE_1_API_KEY="sk-..."
LLM_PROFILE_1_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_PROFILE_1_MODEL="qwen3-vl-plus"
LLM_PROFILE_1_NOTES=""
```

也可以在界面的“模型服务配置”里保存多个不同服务档案；应用会直接回写 `.env`。

## 模型服务配置

界面中提供了“模型服务配置”按钮。每个服务档案会按编号变量写入 `.env`，例如：

- `LLM_PROFILE_1_NAME`
- `LLM_PROFILE_1_API_KEY`
- `LLM_PROFILE_1_BASE_URL`
- `LLM_PROFILE_1_MODEL`
- `LLM_PROFILE_1_NOTES`
- `LLM_ACTIVE_PROFILE`

你可以：

- 新建多个服务档案
- 删除不用的服务档案
- 保存每个服务的 `API Key`、`Base URL`、`模型名称`、备注
- 下次打开软件时继续使用上次保存和选中的服务
- 用同一个界面切换 DashScope、OpenRouter、硅基流动或其他 OpenAI 兼容服务
- 如果你之前的服务配置还保存在 Windows 注册表里，首次启动会自动迁移到 `.env`

## 识别模式

- `单个公式模式`：输出单个公式的 LaTeX 主体，不带 `$` 包裹。
- `段落识别模式`：输出 Markdown 正文内容；如果出现公式，不论是行内还是单独成行，都要求模型用单个 `$...$` 包裹。

预览区统一按 Markdown 渲染，因此可以同时显示段落文字与公式。

## 运行

```powershell
python -m latex_formula_tool
```

或安装成命令后运行：

```powershell
pip install -e .
latex-formula-tool
```

## 环境检查

```powershell
python scripts\check_environment.py
```

如果 PyQt6 在全局 Python 中出现 QtCore DLL 加载失败，建议使用上面的 `.venv` 重新安装依赖，避免 Anaconda、用户 site-packages 和系统 PATH 混用。

## 使用建议

- 截图尽量只包含公式区域，边缘留少量空白。
- 对复杂多行公式，可以在「文字描述/补充说明」中写明排版要求。
- 预览区使用 Markdown + MathJax 渲染。单个公式模式会自动包装成数学块，段落模式会原样按 Markdown 渲染。
- 截图按钮如果此前出现“一闪就退”，通常是因为主窗口隐藏时 Qt 把应用当成“最后一个窗口已关闭”而退出；当前版本已经修正这段流程。
- 当前调用方式基于 OpenAI 兼容 Chat Completions；如果某个服务不是 OpenAI 兼容接口，需要单独适配。
