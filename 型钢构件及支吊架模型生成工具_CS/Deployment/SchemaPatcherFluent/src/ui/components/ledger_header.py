"""台账列头：与行绘制共用列宽，窄窗口时随行一起隐藏“功能”列。"""
import fluentqt as fq
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from ui.delegates.ledger_delegate import column_spans
from ui.theme import tokens


class LedgerHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_feature = True
        self.setFixedHeight(24)
        self.setAccessibleName("台账列：行号、状态、位置、功能、说明")

    def set_show_feature(self, show):
        self.show_feature = show
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(tokens.body_font(fq.FontRole.Caption))
        painter.setPen(tokens.color("secondary"))
        for title, x, width in column_spans(self.width(), self.show_feature):
            painter.drawText(QRect(x, 0, width, self.height()), Qt.AlignVCenter | Qt.AlignLeft, title)
        painter.end()
