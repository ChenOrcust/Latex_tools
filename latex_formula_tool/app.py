from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import QMimeData, QSettings, QTimer, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QImageReader, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStatusBar,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .backends import (
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    FormulaRequest,
    FormulaResult,
    ServiceConfig,
    UniversalLLMBackend,
)
from .capture import capture_screen_region
from .env_profile_store import EnvProfileStore
from .image_utils import save_qimage_to_temp, save_qpixmap_to_temp
from .markdown_renderer import build_markdown_html, wrap_formula_as_markdown
from .pdf_pipeline import (
    convert_docx_to_markdown,
    convert_docx_to_tex,
    convert_markdown_file_to_docx,
    convert_markdown_file_to_html,
    convert_markdown_file_to_pdf,
    convert_markdown_to_html,
    extract_pdf_pages_to_markdown,
    export_markdown_to_docx,
)
from .runtime_paths import docs_dir, env_path, outputs_dir


DEFAULT_SERVICE_PROFILES = [
    ServiceConfig(
        profile_name="DashScope Qwen VL",
        base_url=DEFAULT_LLM_BASE_URL,
        model=DEFAULT_LLM_MODEL,
        extra_notes="阿里云百炼 OpenAI 兼容接口。",
    ),
    ServiceConfig(
        profile_name="OpenAI-compatible Custom",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        extra_notes="适用于 OpenAI 兼容网关或代理。",
    ),
]

ENV_PATH = env_path()


class GenerateWorker(QThread):
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, backend: UniversalLLMBackend, request: FormulaRequest) -> None:
        super().__init__()
        self._backend = backend
        self._request = request

    def run(self) -> None:
        try:
            self.finished_ok.emit(self._backend.generate(self._request))
        except Exception as exc:
            self.failed.emit(str(exc))


class DropImageLabel(QLabel):
    image_dropped = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__("粘贴截图、拖入图片/PDF，或点击按钮选择文件")
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            """
            QLabel {
                border: 1px dashed #8a96a3;
                border-radius: 10px;
                background: #f6f8fa;
                color: #4b5563;
                padding: 16px;
            }
            """
        )

    def dragEnterEvent(self, event) -> None:  # noqa: ANN001
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: ANN001
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if path:
            self.image_dropped.emit(path)


class ServiceConfigDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        profiles: list[ServiceConfig],
        current_profile_name: str,
    ) -> None:
        super().__init__(parent)
        self._profiles = [ServiceConfig(**profile.__dict__) for profile in profiles]
        self._current_profile_name = current_profile_name
        self.setWindowTitle("模型服务配置")
        self.resize(720, 500)
        self._build_ui()
        self._load_profile_names()
        self._select_initial_profile()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        selector = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.new_button = QPushButton("新建")
        self.delete_button = QPushButton("删除")
        selector.addWidget(QLabel("已保存服务"))
        selector.addWidget(self.profile_combo, stretch=1)
        selector.addWidget(self.new_button)
        selector.addWidget(self.delete_button)
        layout.addLayout(selector)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.api_key_edit = QLineEdit()
        self.base_url_edit = QLineEdit()
        self.model_edit = QLineEdit()
        self.notes_edit = QTextEdit()
        self.notes_edit.setMinimumHeight(120)
        form.addRow("档案名称", self.name_edit)
        form.addRow("API Key", self.api_key_edit)
        form.addRow("Base URL", self.base_url_edit)
        form.addRow("模型名称", self.model_edit)
        form.addRow("备注", self.notes_edit)
        layout.addLayout(form)

        hint = QLabel("这里只保存 OpenAI 兼容接口所需参数：Base URL、API Key、模型名。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #56606b;")
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        self.save_button = QPushButton("保存")
        self.close_button = QPushButton("关闭")
        buttons.addStretch(1)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self.profile_combo.currentTextChanged.connect(self._load_profile)
        self.new_button.clicked.connect(self._create_profile)
        self.delete_button.clicked.connect(self._delete_profile)
        self.save_button.clicked.connect(self._save_current_profile)
        self.close_button.clicked.connect(self.accept)

    def get_profiles(self) -> list[ServiceConfig]:
        return [ServiceConfig(**profile.__dict__) for profile in self._profiles]

    def get_current_profile_name(self) -> str:
        return self._current_profile_name

    def _load_profile_names(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems([profile.profile_name for profile in self._profiles])
        self.profile_combo.blockSignals(False)

    def _select_initial_profile(self) -> None:
        if not self._profiles:
            self._profiles = [ServiceConfig(**profile.__dict__) for profile in DEFAULT_SERVICE_PROFILES]
            self._load_profile_names()
        target = self._current_profile_name or self._profiles[0].profile_name
        index = self.profile_combo.findText(target)
        self.profile_combo.setCurrentIndex(index if index >= 0 else 0)
        self._load_profile(self.profile_combo.currentText())

    def _find_profile(self, profile_name: str) -> ServiceConfig | None:
        for profile in self._profiles:
            if profile.profile_name == profile_name:
                return profile
        return None

    def _load_profile(self, profile_name: str) -> None:
        profile = self._find_profile(profile_name)
        if profile is None:
            return
        self._current_profile_name = profile.profile_name
        self.name_edit.setText(profile.profile_name)
        self.api_key_edit.setText(profile.api_key)
        self.base_url_edit.setText(profile.base_url)
        self.model_edit.setText(profile.model)
        self.notes_edit.setPlainText(profile.extra_notes)

    def _create_profile(self) -> None:
        profile_name, ok = QInputDialog.getText(self, "新建服务", "输入服务档案名称")
        profile_name = profile_name.strip()
        if not ok or not profile_name:
            return
        if self._find_profile(profile_name):
            QMessageBox.warning(self, "名称重复", "已经有同名服务，请换一个名称。")
            return
        self._profiles.append(ServiceConfig(profile_name=profile_name))
        self._load_profile_names()
        self.profile_combo.setCurrentText(profile_name)
        self._load_profile(profile_name)

    def _delete_profile(self) -> None:
        if len(self._profiles) <= 1:
            QMessageBox.warning(self, "无法删除", "至少保留一个服务档案。")
            return
        profile_name = self.profile_combo.currentText()
        confirm = QMessageBox.question(self, "删除服务", f"确定删除“{profile_name}”吗？")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._profiles = [profile for profile in self._profiles if profile.profile_name != profile_name]
        self._load_profile_names()
        self.profile_combo.setCurrentIndex(0)
        self._load_profile(self.profile_combo.currentText())

    def _save_current_profile(self) -> None:
        current_name = self.profile_combo.currentText()
        new_name = self.name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "名称为空", "请填写服务档案名称。")
            return
        duplicate = self._find_profile(new_name)
        if duplicate is not None and duplicate.profile_name != current_name:
            QMessageBox.warning(self, "名称重复", "已经有同名服务，请换一个名称。")
            return
        profile = self._find_profile(current_name)
        if profile is None:
            return
        profile.profile_name = new_name
        profile.api_key = self.api_key_edit.text().strip()
        profile.base_url = self.base_url_edit.text().strip()
        profile.model = self.model_edit.text().strip()
        profile.extra_notes = self.notes_edit.toPlainText().strip()
        self._current_profile_name = new_name
        self._load_profile_names()
        self.profile_combo.setCurrentText(new_name)
        QMessageBox.information(self, "已保存", f"{new_name} 配置已保存。")


class FormulaToolWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LaTeX Formula Tool")
        self.resize(1320, 860)

        self._settings = QSettings()
        self._backend = UniversalLLMBackend()
        self._env_store = EnvProfileStore(ENV_PATH)
        self._service_profiles, active_profile_name = self._load_service_profiles()
        self._active_profile_name = active_profile_name
        self._suppress_profile_persistence = False
        self._current_image_path: Path | None = None
        self._current_pdf_path: Path | None = None
        self._current_pixmap: QPixmap | None = None
        self._worker: GenerateWorker | None = None
        self._awaiting_native_snip = False
        self._last_result_mode = "formula"
        self._last_markdown_path: Path | None = None
        self._max_raw_preview_chars = 1800

        self._build_ui()
        self._restore_settings()
        self._wire_events()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.addTab(self._build_recognition_tab(), "识别")
        self.tabs.addTab(self._build_conversion_tab(), "文件转换")
        layout.addWidget(self.tabs)
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("准备就绪")
        self._apply_app_styles()

    def _build_recognition_tab(self) -> QWidget:
        page = QWidget()
        root = QHBoxLayout(page)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(10)
        self.preview_label = DropImageLabel()
        self.preview_label.setMinimumHeight(220)
        left_layout.addWidget(self.preview_label, stretch=3)

        button_grid = QGridLayout()
        self.paste_button = QPushButton("粘贴截图/图片")
        self.capture_button = QPushButton("截取屏幕区域")
        self.open_button = QPushButton("打开图片")
        self.clear_image_button = QPushButton("清空内容")
        button_grid.addWidget(self.paste_button, 0, 0)
        button_grid.addWidget(self.capture_button, 0, 1)
        button_grid.addWidget(self.open_button, 1, 0)
        button_grid.addWidget(self.clear_image_button, 1, 1)
        left_layout.addLayout(button_grid)

        desc_group = QGroupBox("文字描述 / 补充说明")
        desc_layout = QVBoxLayout(desc_group)
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("例如：把图片里的分段函数转成 LaTeX；或直接输入数学描述。")
        self.description_edit.setMinimumHeight(120)
        self.description_edit.setMaximumHeight(180)
        desc_layout.addWidget(self.description_edit)
        left_layout.addWidget(desc_group)

        settings_group = QGroupBox("识别设置")
        settings_layout = QFormLayout(settings_group)
        self.service_profile_combo = QComboBox()
        self.recognition_mode_combo = QComboBox()
        self.recognition_mode_combo.addItem("单个公式模式", "formula")
        self.recognition_mode_combo.addItem("段落识别模式", "paragraph")
        self.recognition_mode_combo.addItem("PDF 提取模式", "pdf")
        self.profile_summary_label = QLabel("")
        self.profile_summary_label.setWordWrap(True)
        settings_layout.addRow("服务档案", self.service_profile_combo)
        settings_layout.addRow("识别模式", self.recognition_mode_combo)
        settings_layout.addRow("当前配置", self.profile_summary_label)
        left_layout.addWidget(settings_group)

        self.pdf_embed_group = QGroupBox("PDF 输入 / 输出")
        self.pdf_embed_group.setMinimumHeight(190)
        pdf_embed_layout = QGridLayout(self.pdf_embed_group)
        self.pdf_input_edit = QLineEdit()
        self.pdf_output_dir_edit = QLineEdit(str(outputs_dir()))
        self.pdf_notes_edit = QTextEdit()
        self.pdf_notes_edit.setPlaceholderText("可补充版式要求，例如：保留分页、不要合并公式块。")
        self.pdf_notes_edit.setMinimumHeight(90)
        self.pdf_notes_edit.setMaximumHeight(130)
        self.pdf_open_button = QPushButton("选择 PDF")
        self.pdf_output_browse_button = QPushButton("选择输出目录")
        pdf_embed_layout.addWidget(QLabel("PDF 文件"), 0, 0)
        pdf_embed_layout.addWidget(self.pdf_input_edit, 0, 1)
        pdf_embed_layout.addWidget(self.pdf_open_button, 0, 2)
        pdf_embed_layout.addWidget(QLabel("输出目录"), 1, 0)
        pdf_embed_layout.addWidget(self.pdf_output_dir_edit, 1, 1)
        pdf_embed_layout.addWidget(self.pdf_output_browse_button, 1, 2)
        pdf_embed_layout.addWidget(QLabel("补充说明"), 2, 0, alignment=Qt.AlignmentFlag.AlignTop)
        pdf_embed_layout.addWidget(self.pdf_notes_edit, 2, 1, 1, 2)
        left_layout.addWidget(self.pdf_embed_group)

        self.generate_button = QPushButton("生成内容")
        self.generate_button.setObjectName("primaryButton")
        self.generate_button.setMinimumHeight(42)
        left_layout.addWidget(self.generate_button)

        service_buttons = QHBoxLayout()
        self.service_config_button = QPushButton("模型服务配置")
        self.help_button = QPushButton("LaTeX 快速帮助")
        service_buttons.addWidget(self.service_config_button)
        service_buttons.addWidget(self.help_button)
        left_layout.addLayout(service_buttons)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setSpacing(10)
        self.result_edit = QTextEdit()
        self.result_edit.setPlaceholderText("识别结果")
        self.result_edit.setMinimumHeight(180)
        self.raw_edit = QTextEdit()
        self.raw_edit.setPlaceholderText("模型原始响应 / 调试信息")
        self.raw_edit.setMinimumHeight(88)
        self.raw_edit.setMaximumHeight(120)
        self.raw_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.markdown_view = QWebEngineView()
        self.markdown_view.setMinimumHeight(360)

        right_layout.addWidget(self._with_copy_button("识别结果", self.result_edit), stretch=2)
        right_layout.addWidget(self._build_preview_panel(), stretch=3)

        action_bar = QHBoxLayout()
        self.export_md_button = QPushButton("导出 Markdown")
        self.export_docx_button = QPushButton("导出 Word")
        self.copy_word_button = QPushButton("复制到 Word")
        action_bar.addWidget(self.export_md_button)
        action_bar.addWidget(self.export_docx_button)
        action_bar.addWidget(self.copy_word_button)
        action_bar.addStretch(1)
        right_layout.addLayout(action_bar)
        right_layout.addWidget(self._with_copy_button("原始响应", self.raw_edit), stretch=1)

        root.addWidget(left, 5)
        root.addWidget(right, 7)
        return page

    def _build_conversion_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        io_group = QGroupBox("本地目录")
        io_layout = QGridLayout(io_group)
        self.conv_input_dir_edit = QLineEdit(str(outputs_dir()))
        self.conv_output_dir_edit = QLineEdit(str(outputs_dir()))
        self.conv_input_browse_button = QPushButton("选择输入目录")
        self.conv_output_browse_button = QPushButton("选择输出目录")
        io_layout.addWidget(QLabel("输入目录"), 0, 0)
        io_layout.addWidget(self.conv_input_dir_edit, 0, 1)
        io_layout.addWidget(self.conv_input_browse_button, 0, 2)
        io_layout.addWidget(QLabel("输出目录"), 1, 0)
        io_layout.addWidget(self.conv_output_dir_edit, 1, 1)
        io_layout.addWidget(self.conv_output_browse_button, 1, 2)
        layout.addWidget(io_group)

        tools_group = QGroupBox("转换工具")
        tools_layout = QGridLayout(tools_group)
        self.word_to_md_button = QPushButton("Word 转 Markdown")
        self.word_to_tex_button = QPushButton("Word 转 TeX")
        self.md_to_word_button = QPushButton("Markdown 转 Word")
        self.md_to_pdf_button = QPushButton("Markdown 转 PDF")
        self.md_to_html_button = QPushButton("Markdown 转 HTML")
        self.generate_test_files_button = QPushButton("生成测试样例")
        self.open_input_dir_button = QPushButton("打开输入目录")
        self.open_output_dir_button = QPushButton("打开输出目录")
        self.word_to_md_button.setMinimumHeight(44)
        self.word_to_tex_button.setMinimumHeight(44)
        self.md_to_word_button.setMinimumHeight(44)
        self.md_to_pdf_button.setMinimumHeight(44)
        self.md_to_html_button.setMinimumHeight(44)
        self.generate_test_files_button.setMinimumHeight(44)
        tools_layout.addWidget(self.word_to_md_button, 0, 0)
        tools_layout.addWidget(self.word_to_tex_button, 0, 1)
        tools_layout.addWidget(self.md_to_word_button, 1, 0)
        tools_layout.addWidget(self.md_to_pdf_button, 1, 1)
        tools_layout.addWidget(self.md_to_html_button, 2, 0)
        tools_layout.addWidget(self.generate_test_files_button, 2, 1)
        tools_layout.addWidget(self.open_input_dir_button, 3, 0)
        tools_layout.addWidget(self.open_output_dir_button, 3, 1)
        layout.addWidget(tools_group)

        self.conversion_log_edit = QTextEdit()
        self.conversion_log_edit.setPlaceholderText("转换日志会显示在这里。")
        self.conversion_log_edit.setMinimumHeight(120)
        self.conversion_log_edit.setMaximumHeight(180)
        layout.addWidget(self._with_copy_button("转换日志", self.conversion_log_edit), stretch=1)
        layout.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        return page

    def _build_preview_panel(self) -> QWidget:
        return self._build_web_preview_panel("Markdown 预览", self.markdown_view, self.render_markdown_preview)

    def _build_web_preview_panel(self, title: str, view: QWebEngineView, refresh_callback) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        bar = QHBoxLayout()
        bar.addWidget(QLabel(title))
        bar.addStretch(1)
        refresh_button = QPushButton("刷新预览")
        refresh_button.clicked.connect(refresh_callback)
        bar.addWidget(refresh_button)
        layout.addLayout(bar)
        layout.addWidget(view)
        return wrapper

    def _with_copy_button(self, title: str, editor: QTextEdit) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        bar.addWidget(QLabel(title))
        bar.addStretch(1)
        copy_button = QPushButton("复制")
        copy_button.clicked.connect(lambda: self._copy_text(editor, copy_button))
        bar.addWidget(copy_button)
        layout.addLayout(bar)
        layout.addWidget(editor)
        return wrapper

    def _wire_events(self) -> None:
        self.paste_button.clicked.connect(self.paste_image)
        self.capture_button.clicked.connect(self.capture_region)
        self.open_button.clicked.connect(self.open_image)
        self.clear_image_button.clicked.connect(self.clear_image)
        self.generate_button.clicked.connect(self.generate_formula)
        self.export_md_button.clicked.connect(self.export_markdown)
        self.export_docx_button.clicked.connect(self.export_docx)
        self.copy_word_button.clicked.connect(lambda: self.copy_for_word(self.copy_word_button))
        self.service_config_button.clicked.connect(self.show_service_config)
        self.help_button.clicked.connect(self.show_latex_help)
        self.preview_label.image_dropped.connect(self.load_dropped_file)
        self.service_profile_combo.currentTextChanged.connect(self._on_service_profile_changed)
        self.recognition_mode_combo.currentTextChanged.connect(self._on_mode_changed)
        QApplication.clipboard().dataChanged.connect(self._on_clipboard_changed)
        QShortcut(QKeySequence.StandardKey.Paste, self, activated=self.paste_image)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.generate_formula)

        self.pdf_open_button.clicked.connect(self.open_pdf_for_tab)
        self.pdf_output_browse_button.clicked.connect(self.choose_pdf_output_dir)
        self.conv_input_browse_button.clicked.connect(lambda: self._choose_directory(self.conv_input_dir_edit))
        self.conv_output_browse_button.clicked.connect(lambda: self._choose_directory(self.conv_output_dir_edit))
        self.word_to_md_button.clicked.connect(self.convert_word_to_markdown)
        self.word_to_tex_button.clicked.connect(self.convert_word_to_tex)
        self.md_to_word_button.clicked.connect(self.convert_markdown_to_word)
        self.md_to_pdf_button.clicked.connect(self.convert_markdown_to_pdf)
        self.md_to_html_button.clicked.connect(self.convert_markdown_to_html_file)
        self.generate_test_files_button.clicked.connect(self.generate_test_files)
        self.open_input_dir_button.clicked.connect(lambda: self._open_directory(self.conv_input_dir_edit.text().strip()))
        self.open_output_dir_button.clicked.connect(lambda: self._open_directory(self.conv_output_dir_edit.text().strip()))

    def _restore_settings(self) -> None:
        recognition_mode = self._settings.value("recognition_mode", "formula")
        current_service = self._active_profile_name or (
            self._service_profiles[0].profile_name if self._service_profiles else ""
        )
        self._refresh_service_profile_combo(str(current_service))
        index = self.recognition_mode_combo.findData(str(recognition_mode))
        self.recognition_mode_combo.setCurrentIndex(index if index >= 0 else 0)
        self.pdf_output_dir_edit.setText(str(self._settings.value("pdf_output_dir", str(outputs_dir()))))
        self.conv_input_dir_edit.setText(str(self._settings.value("conv_input_dir", str(outputs_dir()))))
        self.conv_output_dir_edit.setText(str(self._settings.value("conv_output_dir", str(outputs_dir()))))
        self._on_mode_changed(self.recognition_mode_combo.currentText())

    def closeEvent(self, event) -> None:  # noqa: ANN001
        self._settings.setValue("recognition_mode", self.recognition_mode_combo.currentData())
        self._settings.setValue("pdf_output_dir", self.pdf_output_dir_edit.text().strip())
        self._settings.setValue("conv_input_dir", self.conv_input_dir_edit.text().strip())
        self._settings.setValue("conv_output_dir", self.conv_output_dir_edit.text().strip())
        super().closeEvent(event)

    def paste_image(self) -> None:
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime.hasImage():
            image = clipboard.image()
            if image.isNull():
                self._show_warning("剪贴板图片为空。")
                return
            path = save_qimage_to_temp(image)
            self._set_image(path, QPixmap.fromImage(image))
            self.statusBar().showMessage("已从剪贴板载入图片")
            return
        if mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                if path:
                    self.load_dropped_file(path)
                    return
        text = clipboard.text().strip()
        if text:
            self.description_edit.setPlainText(text)
            self.statusBar().showMessage("剪贴板没有图片，已粘贴为文字描述")
            return
        self._show_warning("剪贴板中没有图片或文字。")

    def capture_region(self) -> None:
        if sys.platform.startswith("win"):
            self._start_native_windows_snip()
            return

        app = QApplication.instance()
        previous_quit_flag = app.quitOnLastWindowClosed() if app is not None else True
        pixmap = None
        try:
            if app is not None:
                app.setQuitOnLastWindowClosed(False)
            self.hide()
            QApplication.processEvents()
            pixmap = capture_screen_region()
        finally:
            self.showNormal()
            self.raise_()
            self.activateWindow()
            if app is not None:
                app.setQuitOnLastWindowClosed(previous_quit_flag)

        if pixmap is None or pixmap.isNull():
            self.statusBar().showMessage("已取消截图")
            return
        path = save_qpixmap_to_temp(pixmap)
        self._set_image(path, pixmap)
        self.statusBar().showMessage("已载入屏幕截图")

    def _start_native_windows_snip(self) -> None:
        self._awaiting_native_snip = True
        self.statusBar().showMessage("请框选需要识别的区域，完成后会自动载入")
        opened = QDesktopServices.openUrl(QUrl("ms-screenclip:"))
        if not opened:
            self._awaiting_native_snip = False
            self._show_warning("无法启动系统截图工具。")

    def _on_clipboard_changed(self) -> None:
        if not self._awaiting_native_snip:
            return
        clipboard = QApplication.clipboard()
        if not clipboard.mimeData().hasImage():
            return
        image = clipboard.image()
        if image.isNull():
            return
        self._awaiting_native_snip = False
        path = save_qimage_to_temp(image)
        self._set_image(path, QPixmap.fromImage(image))
        self.statusBar().showMessage("已从系统截图载入图片")

    def open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            self.conv_input_dir_edit.text().strip(),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)",
        )
        if path:
            self.load_image(path)

    def open_pdf_for_tab(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 PDF 文件",
            self.conv_input_dir_edit.text().strip(),
            "PDF Files (*.pdf)",
        )
        if not path:
            return
        self.pdf_input_edit.setText(path)
        self._current_pdf_path = Path(path)
        self.statusBar().showMessage(f"已选择 PDF: {Path(path).name}")

    def choose_pdf_output_dir(self) -> None:
        self._choose_directory(self.pdf_output_dir_edit)

    def open_pdf(self) -> None:
        self.open_pdf_for_tab()
        self.tabs.setCurrentIndex(1)

    def load_dropped_file(self, path_text: str) -> None:
        suffix = Path(path_text).suffix.lower()
        if suffix == ".pdf":
            self.pdf_input_edit.setText(path_text)
            self._current_pdf_path = Path(path_text)
            index = self.recognition_mode_combo.findData("pdf")
            self.recognition_mode_combo.setCurrentIndex(index if index >= 0 else 0)
            self.statusBar().showMessage(f"已选择 PDF: {self._current_pdf_path.name}")
            return
        self.load_image(path_text)

    def load_image(self, path_text: str) -> None:
        path = Path(path_text)
        if not path.exists():
            self._show_warning(f"图片不存在：{path}")
            return
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            self._show_warning(f"无法读取图片：{path}")
            return
        self._current_pdf_path = None
        self._set_image(path, QPixmap.fromImage(image))
        self.statusBar().showMessage(f"已载入图片：{path.name}")

    def clear_image(self) -> None:
        self._current_image_path = None
        self._current_pdf_path = None
        self._current_pixmap = None
        self._last_markdown_path = None
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("粘贴截图、拖入图片/PDF，或点击按钮选择文件")
        self.statusBar().showMessage("已清空内容")

    def generate_formula(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        selected_mode = str(self.recognition_mode_combo.currentData())
        if selected_mode == "pdf":
            self.run_pdf_extraction()
            return
        text_hint = self.description_edit.toPlainText().strip()
        if not self._current_image_path and not text_hint:
            self._show_warning("请先粘贴截图、打开图片，或输入文字描述。")
            return
        service_config = self._current_service_config()
        if service_config is None:
            self._show_warning("请先选择一个服务档案。")
            return

        request = FormulaRequest(
            image_path=self._current_image_path,
            text_hint=text_hint,
            recognition_mode=selected_mode,
            service_config=service_config,
        )
        self.generate_button.setEnabled(False)
        self.generate_button.setText("生成中...")
        self.statusBar().showMessage(f"正在调用：{service_config.profile_name}")
        self.raw_edit.setPlainText("")

        self._worker = GenerateWorker(self._backend, request)
        self._worker.finished_ok.connect(self._on_generated)
        self._worker.failed.connect(self._on_generate_failed)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def run_pdf_extraction(self) -> None:
        pdf_text = self.pdf_input_edit.text().strip()
        if not pdf_text:
            self._show_warning("请先选择一个 PDF 文件。")
            return
        pdf_path = Path(pdf_text)
        if not pdf_path.exists():
            self._show_warning(f"PDF 不存在：{pdf_path}")
            return
        service_config = self._current_service_config()
        if service_config is None:
            self._show_warning("请先选择一个服务档案。")
            return

        output_root = Path(self.pdf_output_dir_edit.text().strip() or outputs_dir())
        output_dir = output_root / pdf_path.stem
        self.pdf_run_button.setEnabled(False)
        self.pdf_run_button.setText("处理中...")
        self.statusBar().showMessage(f"正在提取 PDF: {pdf_path.name}")
        self.raw_edit.setPlainText("")
        try:
            result = extract_pdf_pages_to_markdown(pdf_path, service_config, output_dir=output_dir)
        except Exception as exc:
            self._show_warning(str(exc))
            self.pdf_run_button.setEnabled(True)
            self.pdf_run_button.setText("提取 PDF 为 Markdown")
            return

        self._last_result_mode = "paragraph"
        self._last_markdown_path = result.markdown_path
        self._current_pdf_path = pdf_path
        self.result_edit.setPlainText(result.markdown_text)
        joined_raw = "\n\n==========\n\n".join(item.raw_output for item in result.results)
        self.raw_edit.setPlainText(self._build_raw_preview(joined_raw))
        self.render_markdown_preview()
        self.pdf_run_button.setEnabled(True)
        self.pdf_run_button.setText("提取 PDF 为 Markdown")
        self.statusBar().showMessage(f"PDF 提取完成，共 {result.page_count} 页")

    def _on_generated(self, result: FormulaResult) -> None:
        self._last_result_mode = result.recognition_mode
        self._last_markdown_path = None
        self.result_edit.setPlainText(result.content)
        self.render_markdown_preview()
        raw = result.raw_output
        if result.warning:
            raw = f"{raw}\n\n[提示] {result.warning}"
        self.raw_edit.setPlainText(self._build_raw_preview(raw))
        self.statusBar().showMessage(f"生成完成：{result.backend_name}")

    def _on_generate_failed(self, message: str) -> None:
        self.statusBar().showMessage("生成失败")
        self._show_warning(message)

    def _on_worker_finished(self) -> None:
        self.generate_button.setEnabled(True)
        self.generate_button.setText("生成内容")
        self._worker = None

    def _set_image(self, path: Path, pixmap: QPixmap) -> None:
        self._current_image_path = path
        self._current_pixmap = pixmap
        self._current_pdf_path = None
        self._update_preview()

    def _update_preview(self) -> None:
        if self._current_pixmap is None or self._current_pixmap.isNull():
            return
        scaled = self._current_pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setText("")
        self.preview_label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._update_preview()

    def show_service_config(self) -> None:
        dialog = ServiceConfigDialog(self, self._service_profiles, self.service_profile_combo.currentText())
        dialog.exec()
        self._service_profiles = dialog.get_profiles()
        self._active_profile_name = dialog.get_current_profile_name()
        self._save_service_profiles()
        self._refresh_service_profile_combo(dialog.get_current_profile_name())

    def _copy_text(self, editor: QTextEdit, button: QPushButton | None = None) -> None:
        QApplication.clipboard().setText(editor.toPlainText())
        self.statusBar().showMessage("已复制到剪贴板")
        self._flash_button_feedback(button)

    def export_markdown(self) -> None:
        content = self._current_markdown_text()
        if not content:
            self._show_warning("当前没有可导出的 Markdown 内容。")
            return
        default_path = self._last_markdown_path or (outputs_dir() / "result.md")
        path_text, _ = QFileDialog.getSaveFileName(self, "导出 Markdown", str(default_path), "Markdown Files (*.md)")
        if not path_text:
            return
        target = Path(path_text)
        target.write_text(content, encoding="utf-8")
        self._last_markdown_path = target
        self.statusBar().showMessage(f"Markdown 已导出：{target.name}")

    def export_docx(self) -> None:
        content = self._current_markdown_text()
        if not content:
            self._show_warning("当前没有可导出的 Word 内容。")
            return
        default_docx = (
            self._last_markdown_path.with_suffix(".docx")
            if self._last_markdown_path is not None
            else outputs_dir() / "result.docx"
        )
        path_text, _ = QFileDialog.getSaveFileName(self, "导出 Word", str(default_docx), "Word Files (*.docx)")
        if not path_text:
            return
        try:
            with tempfile.TemporaryDirectory(prefix="latex_tool_docx_") as temp_dir:
                markdown_path = Path(temp_dir) / "current_result.md"
                markdown_path.write_text(content, encoding="utf-8")
                export_markdown_to_docx(markdown_path, Path(path_text))
        except Exception as exc:
            self._show_warning(str(exc))
            return
        self.statusBar().showMessage(f"Word 已导出：{Path(path_text).name}")

    def copy_for_word(self, button: QPushButton | None = None) -> None:
        content = self._current_markdown_text()
        if not content:
            self._show_warning("当前没有可复制的内容。")
            return
        try:
            html = convert_markdown_to_html(content)
        except Exception as exc:
            self._show_warning(str(exc))
            return
        if not html.strip():
            self._show_warning("生成的 HTML 为空，无法复制到 Word。")
            return
        mime = QMimeData()
        mime.setHtml(html)
        mime.setText(content)
        QApplication.clipboard().setMimeData(mime)
        self.statusBar().showMessage("已复制为 Word 可粘贴格式")
        self._flash_button_feedback(button, success_text="已复制")

    def convert_word_to_markdown(self) -> None:
        source_text, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Word 文件",
            self.conv_input_dir_edit.text().strip(),
            "Word Files (*.docx)",
        )
        if not source_text:
            return
        source = Path(source_text)
        output_dir = Path(self.conv_output_dir_edit.text().strip() or outputs_dir())
        target = output_dir / source.with_suffix(".md").name
        try:
            convert_docx_to_markdown(source, target)
        except Exception as exc:
            self._show_warning(str(exc))
            return
        self.conversion_log_edit.append(f"Word -> Markdown\n输入: {source}\n输出: {target}\n")
        self.statusBar().showMessage(f"Word 已转换为 Markdown：{target.name}")

    def convert_word_to_tex(self) -> None:
        source_text, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Word 文件",
            self.conv_input_dir_edit.text().strip(),
            "Word Files (*.docx)",
        )
        if not source_text:
            return
        source = Path(source_text)
        output_dir = Path(self.conv_output_dir_edit.text().strip() or outputs_dir())
        target = output_dir / source.with_suffix(".tex").name
        try:
            convert_docx_to_tex(source, target)
        except Exception as exc:
            self._show_warning(str(exc))
            return
        self.conversion_log_edit.append(f"Word -> TeX\n输入: {source}\n输出: {target}\n")
        self.statusBar().showMessage(f"Word 已转换为 TeX：{target.name}")

    def convert_markdown_to_word(self) -> None:
        source_text, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Markdown 文件",
            self.conv_input_dir_edit.text().strip(),
            "Markdown Files (*.md *.markdown);;All Files (*)",
        )
        if not source_text:
            return
        source = Path(source_text)
        output_dir = Path(self.conv_output_dir_edit.text().strip() or outputs_dir())
        target = output_dir / source.with_suffix(".docx").name
        try:
            convert_markdown_file_to_docx(source, target)
        except Exception as exc:
            self._show_warning(str(exc))
            return
        self.conversion_log_edit.append(f"Markdown -> Word\n输入: {source}\n输出: {target}\n")
        self.statusBar().showMessage(f"Markdown 已转换为 Word：{target.name}")

    def convert_markdown_to_pdf(self) -> None:
        source_text, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Markdown 文件",
            self.conv_input_dir_edit.text().strip(),
            "Markdown Files (*.md *.markdown);;All Files (*)",
        )
        if not source_text:
            return
        source = Path(source_text)
        output_dir = Path(self.conv_output_dir_edit.text().strip() or outputs_dir())
        target = output_dir / source.with_suffix(".pdf").name
        try:
            convert_markdown_file_to_pdf(source, target)
        except Exception as exc:
            self._show_warning(str(exc))
            return
        self.conversion_log_edit.append(f"Markdown -> PDF\n输入: {source}\n输出: {target}\n")
        self.statusBar().showMessage(f"Markdown 已转换为 PDF：{target.name}")

    def convert_markdown_to_html_file(self) -> None:
        source_text, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Markdown 文件",
            self.conv_input_dir_edit.text().strip(),
            "Markdown Files (*.md *.markdown);;All Files (*)",
        )
        if not source_text:
            return
        source = Path(source_text)
        output_dir = Path(self.conv_output_dir_edit.text().strip() or outputs_dir())
        target = output_dir / source.with_suffix(".html").name
        try:
            convert_markdown_file_to_html(source, target)
        except Exception as exc:
            self._show_warning(str(exc))
            return
        self.conversion_log_edit.append(f"Markdown -> HTML\n输入: {source}\n输出: {target}\n")
        self.statusBar().showMessage(f"Markdown 已转换为 HTML：{target.name}")

    def generate_test_files(self) -> None:
        output_dir = Path(self.conv_output_dir_edit.text().strip() or outputs_dir())
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_dir / "pandoc_formula_demo.md"
        markdown_content = """# Pandoc Formula Demo

作者：Latex Formula Tool

## 行内公式

这是一个行内公式示例：$E = mc^2$，以及二次方程求根公式
$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$。

## 块级公式

$$
\\int_0^1 x^2 \\, dx = \\frac{1}{3}
$$

$$
\\sum_{n=1}^{\\infty} \\frac{1}{n^2} = \\frac{\\pi^2}{6}
$$

## 矩阵与分段函数

$$
A = \\begin{bmatrix}
1 & 2 \\\\
3 & 4
\\end{bmatrix}
$$

$$
f(x) =
\\begin{cases}
x^2, & x \\ge 0 \\\\
-x, & x < 0
\\end{cases}
$$

## 列表

- 公式保真测试
- Markdown 转 Word / PDF / HTML
- Word 转 Markdown / TeX
"""
        markdown_path.write_text(markdown_content, encoding="utf-8")
        self.conversion_log_edit.append(f"已生成测试 Markdown:\n{markdown_path}\n")
        self.statusBar().showMessage(f"测试样例已生成：{markdown_path.name}")

    def _open_directory(self, path_text: str) -> None:
        path = Path(path_text or outputs_dir())
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def render_markdown_preview(self) -> None:
        content = self._current_markdown_text()
        if not content:
            self.markdown_view.setHtml("<html><body><p>生成结果后会在这里显示 Markdown 预览。</p></body></html>")
            return
        try:
            html = build_markdown_html(content)
        except Exception as exc:
            self.markdown_view.setHtml(f"<html><body><p>预览渲染失败：{str(exc)}</p></body></html>")
            self.statusBar().showMessage("Markdown 预览渲染失败")
            return
        self.markdown_view.setHtml(html)
        self.statusBar().showMessage("Markdown 预览已刷新")

    def _current_markdown_text(self) -> str:
        content = self.result_edit.toPlainText().strip()
        if not content:
            return ""
        if self._last_result_mode == "paragraph":
            return content
        return wrap_formula_as_markdown(content)

    def _flash_button_feedback(
        self,
        button: QPushButton | None,
        *,
        success_text: str = "已复制",
        duration_ms: int = 1400,
    ) -> None:
        if button is None:
            return
        original_text = button.text()
        button.setText(success_text)
        button.setEnabled(False)

        def restore() -> None:
            button.setText(original_text)
            button.setEnabled(True)

        QTimer.singleShot(duration_ms, restore)

    def _build_raw_preview(self, raw_text: str) -> str:
        text = raw_text.strip()
        if not text:
            return ""
        if len(text) <= self._max_raw_preview_chars:
            return text
        return (
            text[: self._max_raw_preview_chars].rstrip()
            + "\n\n[已截断，仅显示前部分原始输出，避免界面被完整响应刷满]"
        )

    def _on_mode_changed(self, _text: str) -> None:
        is_pdf_mode = str(self.recognition_mode_combo.currentData()) == "pdf"
        self.preview_label.setHidden(is_pdf_mode)
        self.paste_button.setHidden(is_pdf_mode)
        self.capture_button.setHidden(is_pdf_mode)
        self.open_button.setHidden(is_pdf_mode)
        self.clear_image_button.setHidden(is_pdf_mode)
        self.description_edit.parentWidget().setHidden(is_pdf_mode)
        self.pdf_embed_group.setHidden(not is_pdf_mode)
        self.copy_word_button.setEnabled(True)

    def _choose_directory(self, editor: QLineEdit) -> None:
        current = editor.text().strip() or str(outputs_dir())
        path = QFileDialog.getExistingDirectory(self, "选择目录", current)
        if path:
            editor.setText(path)

    def show_latex_help(self) -> None:
        help_path = docs_dir() / "latex_formula_quick_reference.md"
        markdown = help_path.read_text(encoding="utf-8") if help_path.exists() else "# LaTeX 快速参考\n\n帮助文件不存在。"
        dialog = QDialog(self)
        dialog.setWindowTitle("LaTeX 快速参考")
        dialog.resize(820, 680)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setMarkdown(markdown)
        layout.addWidget(browser)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def _show_warning(self, message: str) -> None:
        QMessageBox.warning(self, "提示", message)

    def _load_service_profiles(self) -> tuple[list[ServiceConfig], str]:
        loaded = self._env_store.load_profiles()
        if loaded.has_managed_profiles:
            return loaded.profiles, loaded.active_profile_name
        migrated_profiles, migrated_active = self._migrate_profiles_from_qsettings()
        if migrated_profiles:
            self._env_store.save_profiles(migrated_profiles, migrated_active)
            return migrated_profiles, migrated_active
        legacy_defaults = self._env_store.load_legacy_defaults(
            fallback_base_url=DEFAULT_LLM_BASE_URL,
            fallback_model=DEFAULT_LLM_MODEL,
        )
        if legacy_defaults:
            active_name = legacy_defaults[0].profile_name
            self._env_store.save_profiles(legacy_defaults, active_name)
            return legacy_defaults, active_name
        defaults = [ServiceConfig(**profile.__dict__) for profile in DEFAULT_SERVICE_PROFILES]
        return defaults, defaults[0].profile_name

    def _save_service_profiles(self) -> None:
        active_name = self.service_profile_combo.currentText().strip() or self._active_profile_name
        if not active_name and self._service_profiles:
            active_name = self._service_profiles[0].profile_name
        self._env_store.save_profiles(self._service_profiles, active_name)
        self._active_profile_name = active_name

    def _migrate_profiles_from_qsettings(self) -> tuple[list[ServiceConfig], str]:
        raw = self._settings.value("service_profiles/json", "")
        if not raw:
            return [], ""
        try:
            items = json.loads(str(raw))
        except json.JSONDecodeError:
            return [], ""

        profiles: list[ServiceConfig] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            profile_name = str(item.get("profile_name", "")).strip()
            if not profile_name:
                continue
            profiles.append(
                ServiceConfig(
                    profile_name=profile_name,
                    api_key=str(item.get("api_key", "")),
                    base_url=str(item.get("base_url", "")),
                    model=str(item.get("model", "")),
                    extra_notes=str(item.get("extra_notes", "")),
                )
            )

        if not profiles:
            return [], ""
        active_name = str(self._settings.value("service_profiles/current_name", profiles[0].profile_name)).strip()
        self._settings.remove("service_profiles/json")
        self._settings.remove("service_profiles/current_name")
        return profiles, active_name or profiles[0].profile_name

    def _refresh_service_profile_combo(self, target_name: str = "") -> None:
        self._suppress_profile_persistence = True
        self.service_profile_combo.blockSignals(True)
        self.service_profile_combo.clear()
        self.service_profile_combo.addItems([profile.profile_name for profile in self._service_profiles])
        self.service_profile_combo.blockSignals(False)
        if not self._service_profiles:
            self._suppress_profile_persistence = False
            return
        target = target_name or self._service_profiles[0].profile_name
        index = self.service_profile_combo.findText(target)
        self.service_profile_combo.setCurrentIndex(index if index >= 0 else 0)
        self._on_service_profile_changed(self.service_profile_combo.currentText())
        self._suppress_profile_persistence = False

    def _current_service_config(self) -> ServiceConfig | None:
        name = self.service_profile_combo.currentText().strip()
        for profile in self._service_profiles:
            if profile.profile_name == name:
                return ServiceConfig(**profile.__dict__)
        return None

    def _on_service_profile_changed(self, profile_name: str) -> None:
        if profile_name:
            self._active_profile_name = profile_name
        config = self._current_service_config()
        if config is None:
            self.profile_summary_label.setText("未选择服务档案")
            return
        summary = f"Base URL: {config.base_url or '(未填写)'}\nModel: {config.model or '(未填写)'}"
        self.profile_summary_label.setText(summary)
        if not self._suppress_profile_persistence:
            self._save_service_profiles()

    def _apply_app_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                font-size: 14px;
                background: #eef2f5;
                color: #1d2b34;
            }
            QTabWidget::pane {
                border: 1px solid #c8d2da;
                border-radius: 14px;
                background: #f8fbfd;
                top: -1px;
            }
            QTabBar::tab {
                background: #dde6ec;
                color: #50616d;
                border: 1px solid #c8d2da;
                padding: 11px 20px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                margin-right: 6px;
                min-width: 96px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #f8fbfd;
                color: #173847;
                border-bottom-color: #f8fbfd;
            }
            QGroupBox {
                font-weight: 700;
                margin-top: 12px;
                border: 1px solid #d5dee5;
                border-radius: 12px;
                background: #fcfeff;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                color: #173847;
            }
            QLabel {
                background: transparent;
            }
            QTextEdit, QLineEdit, QComboBox {
                border: 1px solid #c7d1d9;
                border-radius: 8px;
                padding: 7px 8px;
                background: #ffffff;
                selection-background-color: #285d7a;
                selection-color: #ffffff;
            }
            QPushButton {
                border: 1px solid #bcc8d0;
                border-radius: 8px;
                padding: 8px 14px;
                background: #f6f9fb;
                color: #233742;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #e9f0f5;
                border-color: #8ea7b8;
            }
            QPushButton:disabled {
                color: #8b949e;
                background: #eef3f6;
                border-color: #d6dde3;
            }
            QPushButton#primaryButton {
                background: #1f4f67;
                color: #ffffff;
                border-color: #1f4f67;
                font-weight: 700;
            }
            QPushButton#primaryButton:hover {
                background: #275f7c;
                border-color: #275f7c;
            }
            QStatusBar {
                background: #e4ebf0;
                color: #42535d;
                border-top: 1px solid #c8d2da;
            }
            """
        )
