"""台账行绘制。分组行：文件名 + 总行数；改动行：状态色条、等宽行号、状态、等宽位置、功能、说明。"""
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

import fluentqt as fq

from domain.ledger import CONFLICT, ERROR
from ui.models.ledger_model import ENTRY_ROLE, HEADER_ROLE
from ui.theme import tokens

LINE_W, STATUS_W, TARGET_W, FEATURE_W, GAP = 64, 44, 340, 84, 12
HEADER_HEIGHT = 36
ROW_INSET = 4
TEXT_START = ROW_INSET + 9 + GAP


def column_spans(width, show_feature):
    """各列 (标题, 起点, 宽度)，台账行与列头共用，保证对齐。"""
    spans, x = [], TEXT_START
    for title, w in (("行号", LINE_W), ("状态", STATUS_W), ("位置", TARGET_W), ("功能", FEATURE_W)):
        if title == "功能" and not show_feature:
            continue
        spans.append((title, x, w))
        x += w + GAP
    spans.append(("说明", x, max(0, width - ROW_INSET - 8 - x)))
    return spans


class LedgerDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_feature = True
        self.dimmed = False  # 参数已变更时弱化旧结果
        self.dimmed = False  # 参数已变更时弱化旧结果

    def sizeHint(self, option, index):
        height = HEADER_HEIGHT if index.data(HEADER_ROLE) is not None else tokens.ROW_HEIGHT
        return QSize(option.rect.width(), height)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        if self.dimmed:
            painter.setOpacity(0.5)
        header = index.data(HEADER_ROLE)
        if header is not None:
            self._paint_header(painter, option.rect, header)
        else:
            entry = index.data(ENTRY_ROLE)
            if entry is not None:
                self._paint_entry(painter, option, entry)
        painter.restore()

    def _paint_header(self, painter, rect, header):
        file_name, lines, count = header
        band = rect.adjusted(0, 6, 0, 0)
        ratio = painter.device().devicePixelRatioF() if painter.device() is not None else 1.0
        icon = tokens.icon_pixmap(fq.Icons.File, 14, tokens.color("secondary"), ratio)
        painter.drawPixmap(rect.left() + 14, band.center().y() - 7, icon)
        strong = tokens.body_font(fq.FontRole.BodyStrong)
        width = QFontMetrics(strong).horizontalAdvance(file_name)
        x = self._text(painter, rect.left() + 36, band, width, file_name, strong, tokens.color("text"))
        caption = "共 %d 行 · %d处" % (lines, count) if lines else "%d处" % count
        self._text(painter, x - 4, band, 200, caption, tokens.body_font(fq.FontRole.Caption), tokens.color("secondary"))

    def _paint_entry(self, painter, option, entry):
        rect = option.rect.adjusted(ROW_INSET, 1, -ROW_INSET, -1)
        if option.state & QStyle.State_Selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(tokens.color("selected"))
            painter.drawRoundedRect(rect, 4, 4)
        elif option.state & QStyle.State_MouseOver:
            painter.setPen(Qt.NoPen)
            painter.setBrush(tokens.color("hover"))
            painter.drawRoundedRect(rect, 4, 4)
        if option.state & QStyle.State_HasFocus:
            pen = QPen(fq.accent_color(), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)
        status_color = tokens.color(entry.status)
        painter.setPen(Qt.NoPen)
        painter.setBrush(status_color)
        painter.drawRoundedRect(QRect(rect.left() + 6, rect.center().y() - 10, 3, 20), 1.5, 1.5)

        base = option.rect.left()
        mono = tokens.mono_font(8.5)
        bad = entry.status in (CONFLICT, ERROR)
        cells = {
            "行号": ("L%05d" % entry.original_line if entry.original_line else "—", mono, tokens.color("line"), Qt.ElideRight),
            "状态": (entry.status, tokens.body_font(fq.FontRole.BodyStrong), status_color, Qt.ElideRight),
            "位置": (entry.location, mono, tokens.color("text"), Qt.ElideMiddle),
            "功能": (entry.feature.split("（")[0].replace("增加", "").replace("修改", ""),
                   tokens.body_font(fq.FontRole.Caption), tokens.color("secondary"), Qt.ElideRight),
            "说明": (entry.short_message, tokens.body_font(), status_color if bad else tokens.color("text"), Qt.ElideRight),
        }
        for title, x, width in column_spans(option.rect.width(), self.show_feature):
            text, font, color, elide = cells[title]
            self._text(painter, base + x, rect, width, text, font, color, elide)

    @staticmethod
    def _text(painter, x, rect, width, text, font, color, elide=Qt.ElideRight):
        if width <= 0:
            return x
        painter.setFont(font)
        painter.setPen(color)
        shown = QFontMetrics(font).elidedText(text, elide, width)
        painter.drawText(QRect(x, rect.top(), width, rect.height()), Qt.AlignVCenter | Qt.AlignLeft, shown)
        return x + width + GAP
