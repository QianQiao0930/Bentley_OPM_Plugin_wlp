"""顶部输入条：Schema 目录、备份文件夹、修改内容、检查。窄窗口时换成两行。"""
import fluentqt as fq
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QGridLayout, QHBoxLayout, QWidget

from ui.theme import tokens


class _PathInput(QWidget):
    changed = Signal(str)

    def __init__(self, title, dialog_title, parent=None):
        super().__init__(parent)
        self._dialog_title = dialog_title
        self.edit = fq.LineEdit()
        self.edit.setClearButtonEnabled(True)
        self.edit.setAccessibleName(title)
        self.edit.editingFinished.connect(lambda: self.changed.emit(self.edit.text()))
        field = fq.Field(labelText=title)
        field.setEditor(self.edit)
        self.browse = fq.Button()
        self.browse.setIconGlyph(fq.Icons.Folder)
        self.browse.setFluentLayout(fq.Button.ButtonLayout.IconOnly)
        self.browse.setToolTip("浏览…")
        self.browse.setAccessibleName("浏览" + title)
        self.browse.setFixedWidth(36)
        self.browse.clicked.connect(self._pick)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(tokens.RELATED_GAP)
        row.addWidget(field, 1)
        row.addWidget(self.browse, 0, Qt.AlignBottom)

    def set_text(self, text):
        if self.edit.text() != text and not self.edit.hasFocus():
            self.edit.setText(text)
            self.edit.setCursorPosition(0)
            self.edit.setToolTip(text)

    def _pick(self):
        folder = QFileDialog.getExistingDirectory(self, self._dialog_title, self.edit.text())
        if folder:
            folder = folder.replace("/", "\\")
            self.edit.setText(folder)
            self.edit.setToolTip(folder)
            self.changed.emit(folder)


class InputStrip(QWidget):
    schemaDirChanged = Signal(str)
    backupDirChanged = Signal(str)
    featureChanged = Signal(str)
    checkRequested = Signal()

    def __init__(self, features, parent=None):
        super().__init__(parent)
        self._keys = [f.key for f in features]
        self.schema = _PathInput("Schema 目录", "选择工作集 Schema 目录（…\\Standards\\OpenPlant\\Schemas）")
        self.backup = _PathInput("备份文件夹", "选择备份文件夹")
        self.combo = fq.ComboBox()
        self.combo.addItems([f.label for f in features])
        for i, f in enumerate(features):
            self.combo.setItemData(i, f.description, Qt.ToolTipRole)
        self.combo.setAccessibleName("修改内容")
        self.feature_field = fq.Field(labelText="修改内容")
        self.feature_field.setEditor(self.combo)
        self.check = fq.Button("检查")
        self.check.setIconGlyph(fq.Icons.Search)
        self.check.setFluentLayout(fq.Button.ButtonLayout.IconBefore)
        self.check.setToolTip("只读检查，不会改动文件")
        self.schema.changed.connect(self.schemaDirChanged)
        self.backup.changed.connect(self.backupDirChanged)
        self.combo.currentIndexChanged.connect(lambda i: self.featureChanged.emit(self._keys[i]) if i >= 0 else None)
        self.check.clicked.connect(self.checkRequested)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(tokens.RELATED_GAP)
        self._narrow = None
        self.set_narrow(False)

    def set_narrow(self, narrow):
        if narrow == self._narrow:
            return
        self._narrow = narrow
        for widget in (self.schema, self.backup, self.feature_field, self.check):
            self._grid.removeWidget(widget)
        for column in range(4):
            self._grid.setColumnStretch(column, 0)
        if narrow:
            self._grid.addWidget(self.schema, 0, 0, 1, 3)
            self._grid.addWidget(self.backup, 1, 0)
            self._grid.addWidget(self.feature_field, 1, 1)
            self._grid.addWidget(self.check, 1, 2, Qt.AlignBottom)
            self._grid.setColumnStretch(0, 1)
            self._grid.setColumnStretch(1, 1)
        else:
            self._grid.addWidget(self.schema, 0, 0)
            self._grid.addWidget(self.backup, 0, 1)
            self._grid.addWidget(self.feature_field, 0, 2)
            self._grid.addWidget(self.check, 0, 3, Qt.AlignBottom)
            self._grid.setColumnStretch(0, 5)
            self._grid.setColumnStretch(1, 3)
            self._grid.setColumnStretch(2, 2)

    def render(self, state):
        self.schema.set_text(state.schema_dir)
        self.backup.set_text(state.backup_dir)
        index = self._keys.index(state.feature_key) if state.feature_key in self._keys else 0
        if self.combo.currentIndex() != index:
            self.combo.blockSignals(True)
            self.combo.setCurrentIndex(index)
            self.combo.blockSignals(False)
        for widget in (self.schema, self.backup, self.combo):
            widget.setEnabled(not state.busy)
        self.check.setEnabled(state.can_check)
