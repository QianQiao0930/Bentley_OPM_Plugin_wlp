"""改动详情：选中行的位置、说明，以及改前改后或插入内容。"""
import fluentqt as fq
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QVBoxLayout, QWidget

from domain.ledger import ADDED, CONFLICT, ERROR, PENDING_STATUSES
from ui.components.note_box import NoteBox
from ui.theme import tokens

_PREVIEW_LINES = 6


def _label(text, role=fq.FontRole.Body, color=None, mono=False, wrap=True, marks=None):
    shown = tokens.breakable(text, marks) if wrap and marks else (tokens.breakable(text) if wrap else text)
    widget = fq.Label(shown, fluentTypography=role)
    if mono:
        widget.setFont(tokens.mono_font(9))
    if color is not None:
        widget.setStyleSheet("color: %s;" % color.name())
    widget.setWordWrap(wrap)
    widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return widget


def _fold(line, columns):
    """等宽 XML 预折行：优先在空格或 = 后断开，避免交给自动换行时冲出卡片或拆开标签名。"""
    parts = []
    while len(line) > columns:
        cut = max(line.rfind(" ", 0, columns), line.rfind("=", 0, columns) + 1)
        if cut <= 0:
            cut = columns
        parts.append(line[:cut].rstrip())
        line = line[cut:].lstrip()
    parts.append(line)
    return "\n".join(parts)


class DetailPane(QWidget):
    def __init__(self, parent=None, show_caption=True):
        super().__init__(parent)
        self._show_caption = show_caption
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(18, 16, 18, 16)
        self._layout.setSpacing(tokens.RELATED_GAP)
        self.show_entry(None)

    def show_entry(self, entry):
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        add = self._layout.addWidget
        if self._show_caption:
            caption = _label("改动详情", fq.FontRole.Caption)
            caption.setTextColorRole(fq.Label.TextColorRole.Secondary)
            add(caption)
        if entry is None:
            hint = _label("在台账中选择一行，查看它落在哪个文件、哪一行、改成什么。")
            hint.setTextColorRole(fq.Label.TextColorRole.Secondary)
            add(hint)
            self._layout.addStretch(1)
            return
        add(_label(entry.class_name, fq.FontRole.Subtitle))
        where = entry.file_name.replace(".01.08.ecschema.xml", "")
        prefix = "原第" if entry.status in PENDING_STATUSES else "第"
        line = " · %s %d 行" % (prefix, entry.original_line) if entry.original_line else ""
        meta = _label("%s · %s%s" % (where, entry.status, line), fq.FontRole.Caption)
        meta.setTextColorRole(fq.Label.TextColorRole.Secondary)
        add(meta)
        add(_label(entry.target, mono=True, color=tokens.color("line")))
        status_color = tokens.color(entry.status)
        add(_label(entry.short_message, fq.FontRole.BodyStrong,
                   status_color if entry.status in (CONFLICT, ERROR) else None))
        if "耳轴" in entry.feature and entry.status in PENDING_STATUSES:
            add(NoteBox("注意", "改的是 OPM 自带耳轴类，改后该工作集所有耳轴都需要本插件。"))

        changes = entry.field_changes
        if changes:
            add(fq.Divider(Qt.Horizontal))
            for change in changes:
                add(_label(change.name, mono=True, color=tokens.color("line")))
                add(_label("− " + change.before, mono=True, color=tokens.color("removed")))
                add(_label("+ " + change.after, mono=True, color=tokens.color("added")))
        elif entry.status == ADDED and entry.inserted_text:
            add(fq.Divider(Qt.Horizontal))
            readable = entry.inserted_text.replace("><", ">\n<")
            lines = [l.strip() for l in readable.splitlines() if l.strip()]
            more = len(lines) - _PREVIEW_LINES
            add(_label("插入内容", fq.FontRole.Caption))
            font = tokens.mono_font(9)
            columns = max(20, (tokens.DETAIL_WIDTH - 48) // max(1, QFontMetrics(font).horizontalAdvance("M")))
            preview = "\n".join(_fold(line, columns) for line in lines[:_PREVIEW_LINES])
            add(_label(preview, mono=True, color=tokens.color("added"), wrap=False))
            if more > 0:
                rest = _label("另有%d行，完整内容见日志" % more, fq.FontRole.Caption)
                rest.setTextColorRole(fq.Label.TextColorRole.Secondary)
                add(rest)
        self._layout.addStretch(1)
