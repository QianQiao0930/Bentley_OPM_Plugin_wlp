"""台账列表模型：文件分组行 + 改动行。分组行不可选，键盘导航会跳过。"""
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

ENTRY_ROLE = Qt.UserRole + 1
HEADER_ROLE = Qt.UserRole + 2


class LedgerModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []

    def set_snapshot(self, snapshot):
        self.beginResetModel()
        self._rows = []
        if snapshot is not None:
            groups = {}
            for entry in snapshot.entries:
                groups.setdefault(entry.file_name, []).append(entry)
            for file_name, entries in groups.items():
                self._rows.append(("header", (file_name, entries[0].file_lines, len(entries))))
                for entry in sorted(entries, key=lambda e: e.original_line or 0):
                    self._rows.append(("entry", entry))
        self.endResetModel()

    def entry(self, row):
        if 0 <= row < len(self._rows) and self._rows[row][0] == "entry":
            return self._rows[row][1]
        return None

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def flags(self, index):
        if self.entry(index.row()) is None:
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        kind, value = self._rows[index.row()]
        if kind == "header":
            if role == HEADER_ROLE:
                return value
            if role in (Qt.DisplayRole, Qt.AccessibleTextRole):
                return "%s，%d处" % (value[0], value[2])
            return None
        if role == ENTRY_ROLE:
            return value
        if role in (Qt.DisplayRole, Qt.AccessibleTextRole, Qt.ToolTipRole):
            line = "原第 %d 行，" % value.original_line if value.original_line else ""
            return "%s，%s%s：%s" % (value.status, line, value.location, value.message)
        return None
