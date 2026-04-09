from __future__ import annotations

import json
import sys
from pathlib import Path

from PyQt6.QtCore import QSettings, Qt, QThread, QUrl, pyqtSignal
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
    QSplitter,
    QStatusBar,
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

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


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
        super().__init__("粘贴截图、拖入图片，或点击按钮选择图片")
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            """
            QLabel {
                border: 1px dashed #8a96a3;
                border-radius: 8px;
                background: #f6f8fa;
                color: #4b5563;
                padding: 16px;
            }
            """
        )

    def dragEnterEvent(self, event) -> None:  # noqa: ANN001 - Qt override.
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: ANN001 - Qt override.
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

        hint = QLabel(
            "这里只保存 OpenAI 兼容接口需要的三项核心参数：Base URL、API Key、模型名。"
        )
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
        self.setWindowTitle("LaTeX 公式生成器")
        self.resize(1180, 760)

        self._settings = QSettings()
        self._backend = UniversalLLMBackend()
        self._env_store = EnvProfileStore(ENV_PATH)
        self._service_profiles, active_profile_name = self._load_service_profiles()
        self._active_profile_name = active_profile_name
        self._suppress_profile_persistence = False
        self._current_image_path: Path | None = None
        self._current_pixmap: QPixmap | None = None
        self._worker: GenerateWorker | None = None
        self._awaiting_native_snip = False
        self._last_result_mode = "formula"

        self._build_ui()
        self._restore_settings()
        self._wire_events()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_input_panel())
        splitter.addWidget(self._build_output_panel())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        root_layout.addWidget(splitter)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("准备就绪")

        self._apply_app_styles()

    def _build_input_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.preview_label = DropImageLabel()
        layout.addWidget(self.preview_label, stretch=2)

        image_buttons = QGridLayout()
        self.paste_button = QPushButton("粘贴截图/图片")
        self.capture_button = QPushButton("截取屏幕区域")
        self.open_button = QPushButton("打开图片")
        self.clear_image_button = QPushButton("清空图片")
        image_buttons.addWidget(self.paste_button, 0, 0)
        image_buttons.addWidget(self.capture_button, 0, 1)
        image_buttons.addWidget(self.open_button, 1, 0)
        image_buttons.addWidget(self.clear_image_button, 1, 1)
        layout.addLayout(image_buttons)

        desc_group = QGroupBox("文字描述 / 补充说明")
        desc_layout = QVBoxLayout(desc_group)
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText(
            "例如：把图片里的分段函数转成 LaTeX；或直接输入“x 从 0 到无穷的 e 的负 x 平方积分”。"
        )
        self.description_edit.setMinimumHeight(110)
        desc_layout.addWidget(self.description_edit)
        layout.addWidget(desc_group)

        settings_group = QGroupBox("模型服务")
        settings_layout = QFormLayout(settings_group)
        self.service_profile_combo = QComboBox()
        self.recognition_mode_combo = QComboBox()
        self.recognition_mode_combo.addItem("单个公式模式", "formula")
        self.recognition_mode_combo.addItem("段落识别模式", "paragraph")
        self.profile_summary_label = QLabel("")
        self.profile_summary_label.setWordWrap(True)
        self.profile_summary_label.setStyleSheet("color: #56606b;")
        settings_layout.addRow("服务档案", self.service_profile_combo)
        settings_layout.addRow("识别模式", self.recognition_mode_combo)
        settings_layout.addRow("当前配置", self.profile_summary_label)
        layout.addWidget(settings_group)

        self.generate_button = QPushButton("生成公式代码")
        self.generate_button.setObjectName("primaryButton")
        self.generate_button.setMinimumHeight(42)
        layout.addWidget(self.generate_button)

        self.service_config_button = QPushButton("模型服务配置")
        layout.addWidget(self.service_config_button)

        self.help_button = QPushButton("LaTeX 速查帮助")
        layout.addWidget(self.help_button)

        hint = QLabel(
            "提示：单个公式模式输出公式主体；段落识别模式输出 Markdown 文本，公式统一用单个 $...$ 包裹。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #56606b;")
        layout.addWidget(hint)
        return panel

    def _build_output_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.result_edit = QTextEdit()
        self.markdown_view = QWebEngineView()
        self.raw_edit = QTextEdit()

        self.result_edit.setPlaceholderText("识别结果（单个公式模式下为 LaTeX；段落识别模式下为 Markdown）")
        self.markdown_view.setMinimumHeight(240)
        self.raw_edit.setPlaceholderText("模型原始响应 / 调试信息")
        self.raw_edit.setMinimumHeight(90)

        layout.addWidget(self._with_copy_button("识别结果", self.result_edit), stretch=2)
        layout.addWidget(self._build_render_panel(), stretch=3)
        layout.addWidget(self._with_copy_button("原始响应", self.raw_edit), stretch=1)
        return panel

    def _build_render_panel(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)

        bar = QHBoxLayout()
        label = QLabel("Markdown 渲染预览")
        refresh_button = QPushButton("刷新预览")
        refresh_button.clicked.connect(self.render_markdown_preview)
        bar.addWidget(label)
        bar.addStretch(1)
        bar.addWidget(refresh_button)

        layout.addLayout(bar)
        layout.addWidget(self.markdown_view)
        return wrapper

    def _with_copy_button(self, title: str, editor: QTextEdit) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)

        bar = QHBoxLayout()
        label = QLabel(title)
        copy_button = QPushButton("复制")
        copy_button.clicked.connect(lambda: self._copy_text(editor))
        bar.addWidget(label)
        bar.addStretch(1)
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
        self.service_config_button.clicked.connect(self.show_service_config)
        self.help_button.clicked.connect(self.show_latex_help)
        self.preview_label.image_dropped.connect(self.load_image)
        self.service_profile_combo.currentTextChanged.connect(self._on_service_profile_changed)
        QApplication.clipboard().dataChanged.connect(self._on_clipboard_changed)

        QShortcut(QKeySequence.StandardKey.Paste, self, activated=self.paste_image)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.generate_formula)

    def _restore_settings(self) -> None:
        recognition_mode = self._settings.value("recognition_mode", "formula")
        current_service = self._active_profile_name or (
            self._service_profiles[0].profile_name if self._service_profiles else ""
        )
        self._refresh_service_profile_combo(str(current_service))
        index = self.recognition_mode_combo.findData(str(recognition_mode))
        self.recognition_mode_combo.setCurrentIndex(index if index >= 0 else 0)

    def closeEvent(self, event) -> None:  # noqa: ANN001 - Qt override.
        self._settings.setValue("recognition_mode", self.recognition_mode_combo.currentData())
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
                    self.load_image(path)
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
        self.statusBar().showMessage("请框选需要识别的公式区域，截图完成后会自动载入")
        opened = QDesktopServices.openUrl(QUrl("ms-screenclip:"))
        if not opened:
            self._awaiting_native_snip = False
            self._show_warning("无法启动系统截图工具。")

    def _on_clipboard_changed(self) -> None:
        if not self._awaiting_native_snip:
            return
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if not mime.hasImage():
            return
        image = clipboard.image()
        if image.isNull():
            return
        self._awaiting_native_snip = False
        path = save_qimage_to_temp(image)
        self._set_image(path, QPixmap.fromImage(image))
        self.statusBar().showMessage("已从系统截图载入图片")

    def open_image(self) -> None:
        filters = "Images (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "选择公式图片", "", filters)
        if path:
            self.load_image(path)

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
        self._set_image(path, QPixmap.fromImage(image))
        self.statusBar().showMessage(f"已载入图片：{path.name}")

    def clear_image(self) -> None:
        self._current_image_path = None
        self._current_pixmap = None
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("粘贴截图、拖入图片，或点击按钮选择图片")
        self.statusBar().showMessage("已清空图片")

    def generate_formula(self) -> None:
        if self._worker is not None and self._worker.isRunning():
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
            recognition_mode=str(self.recognition_mode_combo.currentData()),
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

    def _on_generated(self, result: FormulaResult) -> None:
        self._last_result_mode = result.recognition_mode
        self.result_edit.setPlainText(result.content)
        self.render_markdown_preview()
        raw = result.raw_output
        if result.warning:
            raw = f"{raw}\n\n[提示] {result.warning}"
        self.raw_edit.setPlainText(raw)
        self.statusBar().showMessage(f"生成完成：{result.backend_name}")

    def _on_generate_failed(self, message: str) -> None:
        self.statusBar().showMessage("生成失败")
        self._show_warning(message)

    def _on_worker_finished(self) -> None:
        self.generate_button.setEnabled(True)
        self.generate_button.setText("生成公式代码")
        self._worker = None

    def _set_image(self, path: Path, pixmap: QPixmap) -> None:
        self._current_image_path = path
        self._current_pixmap = pixmap
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

    def resizeEvent(self, event) -> None:  # noqa: ANN001 - Qt override.
        super().resizeEvent(event)
        self._update_preview()

    def show_service_config(self) -> None:
        dialog = ServiceConfigDialog(self, self._service_profiles, self.service_profile_combo.currentText())
        dialog.exec()
        self._service_profiles = dialog.get_profiles()
        self._active_profile_name = dialog.get_current_profile_name()
        self._save_service_profiles()
        self._refresh_service_profile_combo(dialog.get_current_profile_name())

    def _copy_text(self, editor: QTextEdit) -> None:
        text = editor.toPlainText()
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage("已复制到剪贴板")

    def render_markdown_preview(self) -> None:
        content = self.result_edit.toPlainText().strip()
        if not content:
            self.markdown_view.setHtml("<html><body><p>生成结果后会在这里显示 Markdown 预览。</p></body></html>")
            return

        if self._last_result_mode == "paragraph":
            markdown_text = content
        else:
            markdown_text = wrap_formula_as_markdown(content)

        try:
            html = build_markdown_html(markdown_text)
        except Exception as exc:
            self.markdown_view.setHtml(
                f"<html><body><p>预览渲染失败：{str(exc)}</p></body></html>"
            )
            self.statusBar().showMessage("Markdown 预览渲染失败")
            return

        self.markdown_view.setHtml(html)
        self.statusBar().showMessage("Markdown 预览已刷新")

    def show_latex_help(self) -> None:
        help_path = Path(__file__).resolve().parent.parent / "docs" / "latex_formula_quick_reference.md"
        if help_path.exists():
            markdown = help_path.read_text(encoding="utf-8")
        else:
            markdown = "# LaTeX 公式代码速查\n\n帮助文件不存在。"

        dialog = QDialog(self)
        dialog.setWindowTitle("LaTeX 公式代码速查")
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

        active_name = str(
            self._settings.value("service_profiles/current_name", profiles[0].profile_name)
        ).strip() or profiles[0].profile_name
        self._settings.remove("service_profiles/json")
        self._settings.remove("service_profiles/current_name")
        return profiles, active_name

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
        summary = (
            f"Base URL: {config.base_url or '(未填写)'}\n"
            f"Model: {config.model or '(未填写)'}"
        )
        self.profile_summary_label.setText(summary)
        if not self._suppress_profile_persistence:
            self._save_service_profiles()

    def _apply_app_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                font-size: 14px;
            }
            QGroupBox {
                font-weight: 600;
                margin-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
            QTextEdit, QLineEdit, QComboBox {
                border: 1px solid #c7cdd4;
                border-radius: 6px;
                padding: 6px;
                background: #ffffff;
            }
            QPushButton {
                border: 1px solid #9aa4af;
                border-radius: 6px;
                padding: 7px 12px;
                background: #ffffff;
            }
            QPushButton:hover {
                background: #eef4ff;
            }
            QPushButton:disabled {
                color: #8b949e;
                background: #f2f4f7;
            }
            QPushButton#primaryButton {
                background: #0f766e;
                color: #ffffff;
                border-color: #0f766e;
                font-weight: 700;
            }
            QPushButton#primaryButton:hover {
                background: #115e59;
            }
            """
        )
