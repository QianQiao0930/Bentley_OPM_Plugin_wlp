"""底部：状态计数、执行修改的条件说明、进度，以及保存日志 / 打开备份 / 执行修改。"""
import fluentqt as fq
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from application.controller import APPLIED
from domain.ledger import ADDED, CONFLICT, ERROR, INSTALLED, MODIFIED, WRITTEN
from ui.theme import tokens


class SummaryFooter(QWidget):
    applyRequested = Signal()
    saveLogRequested = Signal()
    openBackupRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(tokens.SECTION_GAP)
        self._counts = {}
        for status in (ADDED, MODIFIED, CONFLICT, WRITTEN, INSTALLED):
            pair = QHBoxLayout()
            pair.setSpacing(4)
            glyph = fq.FontIcon(tokens.status_glyph(status), iconSize=14)
            glyph.setFixedSize(18, 18)
            text = fq.Label("", fluentTypography=fq.FontRole.BodyStrong)
            pair.addWidget(glyph)
            pair.addWidget(text)
            row.addLayout(pair)
            self._counts[status] = (glyph, text)
        self.hint = fq.Label("", fluentTypography=fq.FontRole.Body)
        self.hint.setTextColorRole(fq.Label.TextColorRole.Secondary)
        row.addWidget(self.hint, 1)
        self.progress = fq.ProgressBar(isIndeterminate=True)
        self.progress.setFixedWidth(160)
        self.progress.hide()
        row.addWidget(self.progress)
        self.open_backup = self._button("打开备份文件夹", fq.Icons.Folder, self.openBackupRequested)
        self.open_backup.setFluentStyle(fq.Button.ButtonStyle.Subtle)
        self.save_log = self._button("保存日志", fq.Icons.SaveAs, self.saveLogRequested)
        self.apply = self._button("执行修改", fq.Icons.Save, self.applyRequested)
        self.apply.setFluentStyle(fq.Button.ButtonStyle.Accent)
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(tokens.RELATED_GAP)
        for button in (self.open_backup, self.save_log, self.apply):
            actions.addWidget(button)
        row.addLayout(actions)

    @staticmethod
    def _button(text, glyph, signal):
        button = fq.Button(text)
        button.setIconGlyph(glyph)
        button.setFluentLayout(fq.Button.ButtonLayout.IconBefore)
        button.setAccessibleName(text)
        button.clicked.connect(signal)
        return button

    def render(self, state):
        snap = state.snapshot
        for status, (glyph, text) in self._counts.items():
            count = snap.count(status) + (snap.count(ERROR) if status == CONFLICT else 0) if snap else 0
            visible = snap is not None and count > 0
            glyph.setVisible(visible)
            text.setVisible(visible)
            if visible:
                color = tokens.color(status)
                glyph.setColor(color)
                text.setText("%s%d" % (status, count))
                text.setStyleSheet("color: %s;" % color.name())
        self.hint.setText(state.apply_hint)
        self.hint.setToolTip(state.apply_hint)
        self.progress.setVisible(state.busy)
        self.apply.setEnabled(state.can_apply)
        self.apply.setToolTip(state.apply_hint)
        self.open_backup.setVisible(state.phase == APPLIED and bool(state.last_run_dir))
        self.save_log.setEnabled(not state.busy and state.has_log)
        self.save_log.setToolTip("" if state.has_log else "检查后才有可保存的记录")
