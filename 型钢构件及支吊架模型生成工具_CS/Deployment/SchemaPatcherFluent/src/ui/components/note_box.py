"""详情区的注意提示：高度随文字换行自适应（fluentqt.InfoBar 高度固定，放在窄栏里会留大块空白）。"""
import fluentqt as fq
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout

from ui.theme import tokens


class NoteBox(QFrame):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setObjectName("noteBox")
        self.setStyleSheet("#noteBox { background: %s; border: 1px solid %s; border-radius: 4px; }"
                           % (tokens.color("caution_bg").name(), tokens.color("caution_border").name()))
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(10)
        glyph = fq.FontIcon(fq.Icons.Warning, iconSize=16)
        glyph.setColor(tokens.color("caution_icon"))
        glyph.setFixedSize(20, 20)
        row.addWidget(glyph, 0, Qt.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(2)
        head = fq.Label(title, fluentTypography=fq.FontRole.BodyStrong)
        body = fq.Label(message, fluentTypography=fq.FontRole.Body)
        body.setWordWrap(True)
        text.addWidget(head)
        text.addWidget(body)
        row.addLayout(text, 1)
        self.setAccessibleName("%s：%s" % (title, message))
