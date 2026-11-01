"""顶层窗口：组装台账页，把页面意图接到控制器，处理关闭与提示对话框。"""
import fluentqt as fq
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QWidget

from application.controller import APPLIED, CHECKED
from domain.ledger import NO_CHANGE_TEXT
from ui.pages.ledger_page import LedgerPage


class MainWindow(fq.Window):
    def __init__(self, controller, parent=None):
        self.page = LedgerPage(controller.features())
        super().__init__(parent, contentWidget=self.page)
        self._controller = controller
        self._last_phase = controller.state.phase
        self.setWindowTitle("Schema 增补")
        self.setMinimumSize(860, 560)
        self.resize(1440, 900)
        self.setCaptionButtonToolTips("最小化", "最大化", "关闭", "还原")
        self.setCaptionButtonAccessibleNames("最小化", "最大化", "关闭", "还原")
        self.titleBar().setContentWidget(self._title())

        page = self.page
        page.schemaDirChanged.connect(controller.set_schema_dir)
        page.backupDirChanged.connect(controller.set_backup_dir)
        page.featureChanged.connect(controller.set_feature)
        page.checkRequested.connect(controller.check)
        page.applyRequested.connect(self._apply)
        page.saveLogRequested.connect(self._save_log)
        page.openBackupRequested.connect(self._open_backup)
        controller.stateChanged.connect(self._render)
        self._render(controller.state)

    @staticmethod
    def _title():
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(12, 0, 0, 0)
        row.setSpacing(10)
        glyph = fq.FontIcon(fq.Icons.Document, iconSize=16)
        glyph.setFixedSize(20, 20)
        row.addWidget(glyph)
        row.addWidget(fq.Label("Schema 增补", fluentTypography=fq.FontRole.BodyStrong))
        caption = fq.Label("OpenPlant 工作集 · 增补台账", fluentTypography=fq.FontRole.Caption)
        caption.setTextColorRole(fq.Label.TextColorRole.Secondary)
        row.addWidget(caption)
        row.addStretch(1)
        return host

    def _render(self, state):
        self.page.render(state)
        entered = state.phase != self._last_phase
        self._last_phase = state.phase
        if not entered:
            return
        if state.phase == CHECKED and state.snapshot is not None and state.snapshot.nothing_to_do:
            self.page.show_message("无需修改", NO_CHANGE_TEXT)
        elif state.phase == APPLIED:
            self.page.show_message("修改完成", "原文件已备份，重启 OPM 后生效。\n\n备份与记录：\n%s" % state.last_run_dir)

    def _apply(self):
        if not self._controller.state.can_apply:
            return
        confirmed = self.page.ask_confirmation(self._controller.confirmation_text())
        self.page.restore_focus()
        if confirmed:
            self._controller.apply()

    def _save_log(self):
        path = self.page.ask_log_path(self._controller.state.backup_dir)
        if not path:
            return
        try:
            self._controller.save_log(path)
        except OSError as error:
            self.page.show_message("保存失败", str(error), "error")

    def _open_backup(self):
        folder = self._controller.state.last_run_dir
        if folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def closeEvent(self, event):
        if not self._controller.can_close():
            event.ignore()
            self.page.show_message("正在处理", "正在备份并写入，请等待完成后再关闭。")
            return
        super().closeEvent(event)
