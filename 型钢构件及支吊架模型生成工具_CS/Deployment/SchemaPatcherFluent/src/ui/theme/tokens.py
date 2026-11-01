"""台账的语义色、等宽字体与间距。视图只取这里的值，不各自写颜色。"""
import fluentqt as fq
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPixmap, QRegion
from PySide6.QtWidgets import QWidget

from domain.ledger import ADDED, CONFLICT, ERROR, INSTALLED, MODIFIED, WRITTEN

EDGE = 24
SECTION_GAP = 16
RELATED_GAP = 8
ROW_HEIGHT = 32
DETAIL_WIDTH = 380
NARROW_WIDTH = 1100

_LIGHT = {ADDED: "#005FB8", MODIFIED: "#9D5D00", CONFLICT: "#C42B1C", ERROR: "#C42B1C", INSTALLED: "#0F7B0F",
          WRITTEN: "#0F7B0F",
          "line": "#707070", "selected": QColor(0, 95, 184, 34), "hover": QColor(0, 0, 0, 10),
          "removed": "#C42B1C", "added": "#0F7B0F", "text": "#1A1A1A", "secondary": "#5D5D5D",
          "caution_bg": "#FFF4CE", "caution_border": "#F2E2A8", "caution_icon": "#9D5D00"}
_DARK = {ADDED: "#60CDFF", MODIFIED: "#FCE100", CONFLICT: "#FF99A4", ERROR: "#FF99A4", INSTALLED: "#6CCB5F",
         WRITTEN: "#6CCB5F",
         "line": "#9E9E9E", "selected": QColor(96, 205, 255, 40), "hover": QColor(255, 255, 255, 12),
         "removed": "#FF99A4", "added": "#6CCB5F", "text": "#FFFFFF", "secondary": "#C5C5C5",
         "caution_bg": "#433519", "caution_border": "#5C4A1F", "caution_icon": "#FCE100"}
_GLYPHS = {ADDED: fq.Icons.Add, MODIFIED: fq.Icons.Edit, CONFLICT: fq.Icons.ErrorIcon, ERROR: fq.Icons.ErrorIcon,
           INSTALLED: fq.Icons.CheckMark, WRITTEN: fq.Icons.Save}


def is_dark():
    return fq.theme_uses_dark_appearance(fq.current_theme())


def color(role):
    value = (_DARK if is_dark() else _LIGHT)[role]
    return value if isinstance(value, QColor) else QColor(value)


def status_glyph(status):
    return _GLYPHS.get(status, fq.Icons.Info)


def mono_font(point_size=9.0):
    for family in ("Cascadia Mono", "Consolas"):
        if family in QFontDatabase.families():
            font = QFont(family)
            font.setPointSizeF(point_size)
            return font
    font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
    font.setPointSizeF(point_size)
    return font


def breakable(text, marks=("\\", ".", "/", "[", "=")):
    """路径、点分命名空间、XPath 没有空格，允许在给定字符后换行；不在下划线处断开标识符。"""
    for mark in marks:
        text = text.replace(mark, mark + "\u200b")
    return text


def body_font(role=fq.FontRole.Body):
    return fq.font_for_role(role)


_icon_cache = {}


def icon_pixmap(glyph, size, color_value, device_ratio=1.0):
    """自绘场景用的图标位图；图标字体靠 FontIcon 内部映射，普通 QPainter 画不出连字。"""
    key = (glyph, size, color_value.name(), device_ratio)
    if key not in _icon_cache:
        widget = fq.FontIcon(glyph, iconSize=size)
        widget.setColor(color_value)
        widget.setFixedSize(size, size)
        widget.setAttribute(Qt.WA_TranslucentBackground)
        pixmap = QPixmap(QSize(int(size * device_ratio), int(size * device_ratio)))
        pixmap.setDevicePixelRatio(device_ratio)
        pixmap.fill(Qt.transparent)
        widget.render(pixmap, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
        widget.deleteLater()
        _icon_cache[key] = pixmap
    return _icon_cache[key]
