"""增补台账的领域值：一次检查得到的改动快照。不依赖 Qt 与具体的 Schema 读写实现。"""
from dataclasses import dataclass, field, replace
from typing import List, Optional, Tuple

ADDED = "新增"
MODIFIED = "修改"
CONFLICT = "冲突"
INSTALLED = "已具备"
WRITTEN = "已写入"
ERROR = "错误"
PENDING_STATUSES = (ADDED, MODIFIED)
BLOCKING_STATUSES = (CONFLICT, ERROR)
NO_CHANGE_TEXT = "当前选择的 Schema 文件已经具备这些字段，无需修改。"


@dataclass(frozen=True)
class FeatureOption:
    key: str
    label: str
    description: str


@dataclass(frozen=True)
class FieldChange:
    name: str
    before: str
    after: str


@dataclass(frozen=True)
class LedgerEntry:
    status: str
    file_name: str
    file_lines: int
    original_line: Optional[int]
    feature: str
    target: str
    message: str
    details: Tuple[str, ...] = ()

    @property
    def class_name(self) -> str:
        return _quoted_values(self.target)[0] if _quoted_values(self.target) else self.target

    @property
    def location(self) -> str:
        """台账里的简短位置：类名 / 字段名或自定义属性名。"""
        values = _quoted_values(self.target)
        if not values:
            return self.target
        last = self.target.rsplit("/", 1)[-1]
        if len(values) > 1:
            return "%s / %s" % (values[0], values[-1])
        if "[" not in last and last != self.target:
            return "%s / %s" % (values[0], last)
        return values[0]

    @property
    def short_message(self) -> str:
        """台账说明列：去掉与“位置”列重复的类名与字段名前缀。"""
        message = self.message
        name = self.class_name
        if name and message.startswith(name + " "):
            message = message[len(name) + 1:]
        tail = self.location.rsplit(" / ", 1)[-1] if " / " in self.location else ""
        for prefix in ("", "新增 "):
            if tail and message.startswith(prefix + tail):
                return (prefix.strip() + message[len(prefix + tail):]).strip()
        return message

    @property
    def field_changes(self) -> List[FieldChange]:
        return [c for c in (split_field_change(d) for d in self.details) if c is not None]

    @property
    def inserted_text(self) -> str:
        if self.status != ADDED:
            return ""
        return "\n".join(d for d in self.details if split_field_change(d) is None)


@dataclass(frozen=True)
class LedgerSnapshot:
    feature_label: str
    schema_dir: str
    entries: Tuple[LedgerEntry, ...] = ()

    def count(self, status: str) -> int:
        return sum(1 for e in self.entries if e.status == status)

    @property
    def pending(self) -> List[LedgerEntry]:
        return [e for e in self.entries if e.status in PENDING_STATUSES]

    @property
    def blocked(self) -> bool:
        return any(e.status in BLOCKING_STATUSES for e in self.entries)

    @property
    def nothing_to_do(self) -> bool:
        return bool(self.entries) and not self.blocked and not self.pending

    @property
    def summary(self) -> str:
        if self.blocked:
            problems = self.count(CONFLICT) + self.count(ERROR)
            return "%d处冲突或错误，执行修改已锁定" % problems
        if self.nothing_to_do:
            return NO_CHANGE_TEXT
        parts = ["%d%s" % (self.count(s), s) for s in (ADDED, MODIFIED) if self.count(s)]
        return "检查完成：%d处待修改（%s）" % (len(self.pending), "、".join(parts))

    @property
    def files(self) -> List[str]:
        """待修改涉及的文件，按台账中出现的顺序。"""
        seen = []
        for e in self.pending:
            if e.file_name not in seen:
                seen.append(e.file_name)
        return seen


@dataclass(frozen=True)
class ApplyOutcome:
    run_dir: str
    log_path: str
    files: Tuple[Tuple[str, str], ...] = field(default=())


def mark_written(after: LedgerSnapshot, before: LedgerSnapshot) -> LedgerSnapshot:
    """写入后复查的快照：本次写入的条目标为“已写入”并保留写入时的改动说明，行号取写入后的位置。"""
    written = dict(((e.file_name, e.target), e) for e in before.pending)
    entries = []
    for e in after.entries:
        source = written.get((e.file_name, e.target))
        if e.status == INSTALLED and source is not None:
            e = replace(e, status=WRITTEN, message=source.message, details=source.details)
        entries.append(e)
    return replace(after, entries=tuple(entries))


def _quoted_values(target: str) -> List[str]:
    values = []
    for part in target.split("'")[1::2]:
        values.append(part)
    return values


def split_field_change(detail: str) -> Optional[FieldChange]:
    """把“字段：旧值 → 新值”拆成三段；其他文本返回 None。"""
    name, sep, rest = detail.partition("：")
    if not sep or " → " not in rest or "\n" in detail or not name.isupper():
        return None
    before, _, after = rest.partition(" → ")
    return FieldChange(name, before, after)
