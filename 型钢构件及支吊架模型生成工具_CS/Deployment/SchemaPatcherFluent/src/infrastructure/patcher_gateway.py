"""把 Deployment/SchemaPatcher 的检查/写入引擎适配成领域快照。业务规则只在那边维护，这里不复制。"""
import os
import re
import sys

from domain.ledger import ApplyOutcome, FeatureOption, LedgerEntry, LedgerSnapshot


def _engine_root():
    if getattr(sys, "frozen", False):
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "..", "SchemaPatcher"))


_root = _engine_root()
if _root and _root not in sys.path:
    sys.path.insert(0, _root)

from schema_patcher import engine as _engine  # noqa: E402
from schema_patcher.features import FEATURES as _FEATURES  # noqa: E402


class PatchFailed(Exception):
    pass


_STEP = re.compile(r"^(\w+)(?:\[@(\w+)='([^']*)'\])?$")


def _target_line(doc, target):
    """冲突与已具备项没有插入点，按目标路径定位现有节点的行号；找不到返回 None。"""
    if doc is None or not target or target == "-":
        return None
    node = doc.root
    for step in target.split("/"):
        match = _STEP.match(step)
        if match is None:
            return None
        name, attr, value = match.groups()
        node = next((c for c in node.children if c.local == name and (attr is None or c.get(attr) == value)), None)
        if node is None:
            return None
    return node.line


class PatcherGateway(object):
    """一次检查返回 (快照, 不透明计划)；写入只接受同一次检查的计划。"""

    def features(self):
        return [FeatureOption(f.key, f.label, f.description) for f in _FEATURES.values()]

    def check(self, schema_dir, feature_key):
        plan = _engine.load_plan(schema_dir, feature_key)
        lines = dict((key, doc.data.count(b"\n") + 1) for key, doc in plan.docs.items())
        entries = tuple(
            LedgerEntry(status=_engine.STATUS_TEXT[item.status], file_name=_engine.file_name(item.file_key),
                        file_lines=lines.get(item.file_key, 0),
                        original_line=_target_line(plan.docs.get(item.file_key), item.target) or item.original_line,
                        feature=item.feature, target=item.target, message=item.message,
                        details=tuple(item.details))
            for item in plan.items)
        return LedgerSnapshot(plan.feature.label, plan.schema_dir, entries), plan

    def detailed_log(self, plan):
        return _engine.format_log(plan)

    def running_opm(self):
        return _engine.running_opm()

    def apply(self, plan, backup_dir):
        try:
            result = _engine.apply_plan(plan, backup_dir)
        except _engine.PatchError as error:
            raise PatchFailed(str(error))
        files = tuple((r["schema"], r["backup"]) for r in result.files)
        return ApplyOutcome(result.run_dir, result.log_path, files), result.log_text

    def save_text(self, path, text):
        with open(path, "w", encoding="utf-8-sig") as stream:
            stream.write(text)
