"""增补台账页：输入条、提示条、台账 + 改动详情、底部操作。只渲染状态并发出意图。"""
import datetime

import fluentqt as fq
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QScrollArea, QSizePolicy, QVBoxLayout

from application.controller import APPLIED, CHECKING
from domain.ledger import CONFLICT, ERROR, PENDING_STATUSES
from ui.components.detail_pane import DetailPane
from ui.components.input_strip import InputStrip
from ui.components.ledger_header import LedgerHeader
from ui.components.summary_footer import SummaryFooter
from ui.delegates.ledger_delegate import LedgerDelegate
from ui.models.ledger_model import LedgerModel
from ui.theme import tokens

_SEVERITY = {"info": fq.InfoBar.InfoBarSeverity.Informational, "success": fq.InfoBar.InfoBarSeverity.Success,
             "warning": fq.InfoBar.InfoBarSeverity.Warning, "error": fq.InfoBar.InfoBarSeverity.Error}
_EMPTY = "还没有检查结果。选择 Schema 目录和修改内容，然后检查。"


def _transparent_scroll(widget):
    """fluentqt.ScrollView 自绘背景且运行中切换主题不更新，这里用透明 QScrollArea + Fluent 滚动条。"""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBar(fq.ScrollBar(Qt.Vertical))
    scroll.setObjectName("transparentScroll")
    scroll.setStyleSheet("#transparentScroll, #transparentScroll > QWidget > QWidget { background: transparent; }")
    scroll.setWidget(widget)
    return scroll


class LedgerPage(fq.FluentWidget):
    schemaDirChanged = Signal(str)
    backupDirChanged = Signal(str)
    featureChanged = Signal(str)
    checkRequested = Signal()
    applyRequested = Signal()
    saveLogRequested = Signal()
    openBackupRequested = Signal()

    def __init__(self, features, parent=None):
        super().__init__(parent)
        self._snapshot = None
        self._narrow = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(tokens.EDGE, 4, tokens.EDGE, tokens.SECTION_GAP)
        outer.setSpacing(12)

        self.strip = InputStrip(features)
        outer.addWidget(self.strip)
        self.banner = fq.InfoBar(isOpen=False, isClosable=False)
        self.banner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        outer.addWidget(self.banner)

        body = QHBoxLayout()
        body.setSpacing(tokens.SECTION_GAP)
        ledger_card = fq.Card()
        ledger_card.setAppearance(fq.Card.Appearance.Layer)
        lc = QVBoxLayout(ledger_card)
        lc.setContentsMargins(4, 8, 4, 8)
        lc.setSpacing(2)
        self.header = LedgerHeader()
        lc.addWidget(self.header)
        self.model = LedgerModel(self)
        self.delegate = LedgerDelegate(self)
        self.list = fq.ListView()
        self.list.setModel(self.model)
        self.list.setItemDelegate(self.delegate)
        self.list.setSelectionIndicatorVisible(False)
        self.list.setBorderVisible(False)
        self.list.setSpacing(0)
        self.list.setPlaceholderText(_EMPTY)
        self.list.setMouseTracking(True)
        self.list.setAccessibleName("增补台账")
        self.list.selectionModel().currentChanged.connect(self._on_current)
        self.list.activated.connect(self._on_activated)
        lc.addWidget(self.list)
        body.addWidget(ledger_card, 1)

        self.detail_card = fq.Card()
        self.detail_card.setAppearance(fq.Card.Appearance.LayerAlt)
        self.detail_card.setFixedWidth(tokens.DETAIL_WIDTH)
        dc = QVBoxLayout(self.detail_card)
        dc.setContentsMargins(0, 4, 0, 4)
        self.detail = DetailPane()
        dc.addWidget(_transparent_scroll(self.detail))
        body.addWidget(self.detail_card)
        outer.addLayout(body, 1)

        self.footer = SummaryFooter()
        outer.addWidget(self.footer)

        for source, target in ((self.strip.schemaDirChanged, self.schemaDirChanged),
                               (self.strip.backupDirChanged, self.backupDirChanged),
                               (self.strip.featureChanged, self.featureChanged),
                               (self.strip.checkRequested, self.checkRequested),
                               (self.footer.applyRequested, self.applyRequested),
                               (self.footer.saveLogRequested, self.saveLogRequested),
                               (self.footer.openBackupRequested, self.openBackupRequested)):
            source.connect(target)

    # ---------------------------------------------------------------- 渲染
    def render(self, state):
        self.strip.render(state)
        self.footer.render(state)
        self._render_banner(state)
        if state.snapshot is not self._snapshot:
            self._snapshot = state.snapshot
            self.model.set_snapshot(state.snapshot)
            self._select_first()
        self.list.setEnabled(not state.busy)
        if self.delegate.dimmed != state.stale:
            self.delegate.dimmed = state.stale
            self.list.viewport().update()
        self.list.setPlaceholderText("" if state.phase == CHECKING else _EMPTY)

    def _render_banner(self, state):
        banner = state.banner
        if state.stale and state.snapshot is not None and not state.busy:
            title, message, severity = "参数已变更", "下方是旧的检查结果，请重新检查后再执行修改。", "warning"
        elif banner is not None:
            title, message, severity = banner.title, banner.message, banner.severity
        else:
            self.banner.setIsOpen(False)
            return
        self.banner.setSeverity(_SEVERITY[severity])
        self.banner.setTitle(title)
        self.banner.setMessage(message)
        self.banner.setToolTip(state.last_run_dir if state.phase == APPLIED else message)
        self.banner.setIsOpen(True)

    def _select_first(self):
        rows = self.model.rowCount()
        if not rows:
            self.detail.show_entry(None)
            return
        entries = [r for r in range(rows) if self.model.entry(r) is not None]
        wanted = (CONFLICT, ERROR) if self._snapshot.blocked else PENDING_STATUSES
        row = next((r for r in entries if self.model.entry(r).status in wanted), entries[0] if entries else -1)
        if row < 0:
            self.detail.show_entry(None)
            return
        self.list.setCurrentIndex(self.model.index(row))

    def _on_current(self, current, _previous):
        self.detail.show_entry(self.model.entry(current.row()) if current.isValid() else None)

    def on_theme_updated(self):
        """主题切换后重建使用语义色的部分。"""
        super().on_theme_updated()
        if not hasattr(self, "list"):
            return
        current = self.list.currentIndex()
        self.detail.show_entry(self.model.entry(current.row()) if current.isValid() else None)
        self.list.viewport().update()

    def _on_activated(self, index):
        if self._narrow and index.isValid() and self.model.entry(index.row()) is not None:
            self.build_detail_dialog(self.model.entry(index.row())).exec()
            self.restore_focus()

    def restore_focus(self):
        """对话框关闭后焦点回到台账，避免落到第一个输入框并全选文字。"""
        self.list.setFocus(Qt.OtherFocusReason)
        self.strip.schema.edit.deselect()

    def build_detail_dialog(self, entry):
        """窄窗口下详情区收起，选中行按 Enter 或双击时用对话框查看。"""
        dialog = fq.ContentDialog(self.window(), title="改动详情", closeButtonText="关闭")
        pane = DetailPane(show_caption=False)
        pane.show_entry(entry)
        pane.setFixedWidth(440)
        height = pane.heightForWidth(440) if pane.hasHeightForWidth() else pane.sizeHint().height()
        limit = self.window().height() - 40
        scroll = _transparent_scroll(pane)
        scroll.setFixedSize(456, 160)
        dialog.setContent(scroll)
        dialog.adjustSize()
        chrome = dialog.height() - scroll.height()
        scroll.setFixedHeight(max(160, min(height, limit - chrome)))
        if height > scroll.height():
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
            scroll.verticalScrollBar().setOpacity(1.0)
        dialog.adjustSize()
        dialog.setMaximumHeight(max(320, limit))
        return dialog

    # ---------------------------------------------------------------- 响应式
    def resizeEvent(self, event):
        super().resizeEvent(event)
        narrow = self.width() < tokens.NARROW_WIDTH
        if narrow != self._narrow:
            self._narrow = narrow
            self.strip.set_narrow(narrow)
            self.detail_card.setVisible(not narrow)
            self.delegate.show_feature = not narrow
            self.header.set_show_feature(not narrow)
            self.list.viewport().update()

    # ---------------------------------------------------------------- 对话框
    def build_confirmation(self, text):
        dialog = fq.ContentDialog(self.window(), title="确认修改", primaryButtonText="备份并写入", closeButtonText="取消")
        dialog.setContent(self._dialog_body(text, 520))
        dialog.setDefaultButton(int(fq.ContentDialogButton.Primary))
        dialog.adjustSize()
        return dialog

    @staticmethod
    def _dialog_body(text, width):
        body = fq.Label(tokens.breakable(text, marks=("\\",)), fluentTypography=fq.FontRole.Body)
        body.setWordWrap(True)
        body.setFixedWidth(width)
        body.setMinimumHeight(body.heightForWidth(width))
        return body

    def ask_confirmation(self, text):
        return self.build_confirmation(text).exec() == int(fq.ContentDialogButton.Primary)

    def ask_log_path(self, folder):
        name = "SchemaPatch_%s.log" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path, _ = QFileDialog.getSaveFileName(self, "保存日志", (folder + "\\" if folder else "") + name,
                                              "日志 (*.log);;文本 (*.txt)")
        return path

    def show_message(self, title, text, severity="info"):
        dialog = fq.ContentDialog(self.window(), title=title, closeButtonText="确定")
        dialog.setContent(self._dialog_body(text, 420))
        dialog.adjustSize()
        dialog.exec()
