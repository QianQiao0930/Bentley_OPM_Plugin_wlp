"""检查、备份、写入、回滚与记录。所有写入先在内存中完成并自检，通过后才替换工作集文件。"""
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import uuid

from .features import ADD, CONFLICT, ERROR, FEATURES, INSTALLED, MODIFY, SCHEMA_FILES, Item, plan_feature
from .xmlspan import Document, XmlFormatError

STATUS_TEXT = {INSTALLED: "已具备", ADD: "新增", MODIFY: "修改", CONFLICT: "冲突", ERROR: "错误"}
OPM_PROCESSES = ("openplantmodeler.exe", "ustation.exe")


class PatchError(Exception):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest().upper()


class Plan(object):
    def __init__(self, feature, schema_dir):
        self.feature = feature
        self.schema_dir = schema_dir
        self.paths = {}
        self.originals = {}
        self.docs = {}
        self.items = []
        self.created = datetime.datetime.now()

    @property
    def blocked(self):
        return any(i.status in (CONFLICT, ERROR) for i in self.items)

    @property
    def pending(self):
        return [i for i in self.items if i.status in (ADD, MODIFY)]

    @property
    def nothing_to_do(self):
        return not self.blocked and not self.pending

    def patches_by_file(self):
        result = {}
        for item in self.pending:
            result.setdefault(item.file_key, []).extend(item.patches)
        return result


def file_name(key):
    return SCHEMA_FILES[key][1]


def load_plan(schema_dir, feature_key):
    feature = FEATURES[feature_key]
    plan = Plan(feature, os.path.abspath(schema_dir))
    if not os.path.isdir(plan.schema_dir):
        plan.items.append(Item(feature.label, feature.files[0], "-", ERROR, "Schema 目录不存在：%s" % plan.schema_dir))
        return plan
    for key in feature.files:
        schema_name, name = SCHEMA_FILES[key]
        full = os.path.join(plan.schema_dir, name)
        plan.paths[key] = full
        if not os.path.isfile(full):
            plan.items.append(Item(feature.label, key, "-", ERROR, "缺少 Schema 文件：%s" % name))
            continue
        with open(full, "rb") as stream:
            data = stream.read()
        try:
            doc = Document(data, name)
        except XmlFormatError as error:
            plan.items.append(Item(feature.label, key, "-", ERROR, str(error)))
            continue
        if doc.root.local != "ECSchema" or doc.root.get("schemaName") != schema_name:
            plan.items.append(Item(feature.label, key, "-", ERROR, "%s 不是 %s 的 Schema 文件。" % (name, schema_name)))
            continue
        plan.originals[key] = data
        plan.docs[key] = doc
    if plan.items:
        return plan
    plan.items = plan_feature(feature, plan.docs)
    for item in plan.items:
        if item.patches:
            item.original_line = plan.docs[item.file_key].line_of(min(p.offset for p in item.patches))
    return plan


def running_opm():
    try:
        output = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except OSError:
        return []
    found = set()
    for line in output.splitlines():
        name = line.split(",", 1)[0].strip().strip('"').lower()
        if name in OPM_PROCESSES:
            found.add(name)
    return sorted(found)


def _locate_line(doc, steps):
    node = doc.root
    for local, attrs in steps:
        node = next((c for c in node.children if c.local == local
                     and all(c.get(k) == v for k, v in attrs.items())), None)
        if node is None:
            return None
    return node.line


def _check_untouched(old, new, items):
    types = set(i.locate[0][1].get("typeName") for i in items if i.locate)
    if new.data[:new.root.start_end] != old.data[:old.root.start_end]:
        raise PatchError("%s 自检失败：文件头或根节点被改动。" % old.name)
    if new.data[new.root.end:] != old.data[old.root.end:]:
        raise PatchError("%s 自检失败：根节点之后的内容被改动。" % old.name)
    original = old.root.children
    current = new.root.children
    if len(current) < len(original):
        raise PatchError("%s 自检失败：顶层节点数量减少。" % old.name)
    for before, after in zip(original, current):
        if before.local != after.local or before.get("typeName") != after.get("typeName"):
            raise PatchError("%s 自检失败：顶层节点顺序变化（第 %d 行）。" % (old.name, before.line))
        if before.get("typeName") not in types and old.raw(before) != new.raw(after):
            raise PatchError("%s 自检失败：未涉及的节点 %s 被改动。" % (old.name, before.get("typeName") or before.local))
    existing = set(c.get("typeName") for c in original)
    expected_new = types - existing
    extra = current[len(original):]
    names = [c.get("typeName") for c in extra]
    if any(c.local != "ECClass" for c in extra) or sorted(names) != sorted(expected_new):
        raise PatchError("%s 自检失败：新增的顶层类与计划不符。" % old.name)


def build_new_files(plan):
    """在内存中生成修改后的文件并自检；返回 {key: (bytes, Document)}。"""
    patches = plan.patches_by_file()
    result = {}
    docs = dict(plan.docs)
    for key, file_patches in patches.items():
        data = plan.docs[key].apply(file_patches)
        try:
            docs[key] = Document(data, file_name(key))
        except XmlFormatError as error:
            raise PatchError("修改后的 %s 无法解析：%s" % (file_name(key), error))
        result[key] = (data, docs[key])
    recheck = plan_feature(plan.feature, docs)
    bad = [i for i in recheck if i.status != INSTALLED]
    if bad:
        raise PatchError("写入前自检失败：" + "；".join("%s %s %s" % (file_name(i.file_key), i.target, i.message) for i in bad))
    for key in result:
        _check_untouched(plan.docs[key], docs[key], [i for i in plan.pending if i.file_key == key])
    for item in plan.pending:
        item.new_line = _locate_line(docs[item.file_key], item.locate)
    return result


def _run_dir(backup_root, feature_key):
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(backup_root, "SchemaPatch_%s_%s" % (stamp, feature_key))
    candidate, index = base, 1
    while os.path.exists(candidate):
        index += 1
        candidate = "%s_%d" % (base, index)
    return candidate


def _replace_bytes(target, data):
    temporary = "%s.%s.tmp" % (target, uuid.uuid4().hex)
    try:
        with open(temporary, "wb") as stream:
            stream.write(data)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def _inside(child_path, parent_path):
    child_path = os.path.normcase(os.path.abspath(child_path))
    parent_path = os.path.normcase(os.path.abspath(parent_path))
    return child_path == parent_path or child_path.startswith(parent_path.rstrip("\\/") + os.sep)


class ApplyResult(object):
    def __init__(self, run_dir, log_path, receipt_path, log_text, files):
        self.run_dir = run_dir
        self.log_path = log_path
        self.receipt_path = receipt_path
        self.log_text = log_text
        self.files = files


def apply_plan(plan, backup_root, check_processes=True):
    if plan.blocked:
        raise PatchError("存在冲突或错误，未修改任何文件。")
    if not plan.pending:
        raise PatchError("当前选择的 Schema 文件已经具备这些字段，无需修改。")
    if not backup_root or not backup_root.strip():
        raise PatchError("请先指定备份文件夹。")
    backup_root = os.path.abspath(backup_root)
    if _inside(backup_root, plan.schema_dir):
        raise PatchError("备份文件夹不能放在 Schema 目录里面，请换一个位置。")
    if check_processes:
        running = running_opm()
        if running:
            raise PatchError("检测到 %s 正在运行，请先保存并关闭 OPM 再修改 Schema。" % "、".join(running))

    new_files = build_new_files(plan)
    for key in new_files:
        with open(plan.paths[key], "rb") as stream:
            if sha256(stream.read()) != sha256(plan.originals[key]):
                raise PatchError("%s 在检查之后被其他程序修改，请重新检查。" % file_name(key))

    run_dir = _run_dir(backup_root, plan.feature.key)
    try:
        os.makedirs(run_dir)
    except OSError as error:
        raise PatchError("无法创建备份文件夹 %s：%s" % (run_dir, error))
    records = []
    for key in new_files:
        backup = os.path.join(run_dir, file_name(key) + ".bak")
        shutil.copy2(plan.paths[key], backup)
        with open(backup, "rb") as stream:
            if sha256(stream.read()) != sha256(plan.originals[key]):
                raise PatchError("备份校验失败：%s，未修改任何文件。" % backup)
        records.append({"key": key, "schema": plan.paths[key], "backup": backup,
                        "before": sha256(plan.originals[key]), "after": sha256(new_files[key][0])})

    applied = []
    try:
        for record in records:
            key = record["key"]
            with open(plan.paths[key], "rb") as stream:
                if sha256(stream.read()) != record["before"]:
                    raise PatchError("%s 在准备期间被修改，停止写入。" % file_name(key))
            _replace_bytes(plan.paths[key], new_files[key][0])
            applied.append(record)
    except Exception as error:
        problems = []
        for record in applied:
            try:
                with open(record["schema"], "rb") as stream:
                    if sha256(stream.read()) != record["after"]:
                        raise PatchError("写入后文件又被改动，拒绝回滚覆盖")
                with open(record["backup"], "rb") as stream:
                    _replace_bytes(record["schema"], stream.read())
            except Exception as rollback_error:
                problems.append("%s：%s" % (file_name(record["key"]), rollback_error))
        hint = "（如提示拒绝访问，请以管理员身份运行本工具）" if isinstance(error, PermissionError) else ""
        message = "写入失败%s：%s。" % (hint, error)
        if problems:
            message += "回滚未完成：" + "；".join(problems) + "。请用备份文件夹中的 .bak 手动恢复：" + run_dir
        else:
            message += "已回滚，工作集文件保持原样。"
        raise PatchError(message)

    log_text = format_log(plan, records, run_dir)
    log_path = os.path.join(run_dir, "SchemaPatch.log")
    with open(log_path, "w", encoding="utf-8-sig") as stream:
        stream.write(log_text)
    receipt_path = os.path.join(run_dir, "receipt.json")
    receipt = {
        "Time": plan.created.isoformat(timespec="seconds"),
        "Feature": plan.feature.key,
        "FeatureLabel": plan.feature.label,
        "SchemaDirectory": plan.schema_dir,
        "Files": [{"Schema": r["schema"], "Backup": r["backup"], "BeforeSHA256": r["before"],
                   "AfterSHA256": r["after"]} for r in records],
        "Changes": [{"File": file_name(i.file_key), "Feature": i.feature, "Action": STATUS_TEXT[i.status],
                     "Target": i.target, "OriginalLine": i.original_line, "NewLine": i.new_line,
                     "Message": i.message, "Details": i.details} for i in plan.pending],
    }
    with open(receipt_path, "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
    return ApplyResult(run_dir, log_path, receipt_path, log_text, records)


def describe_plan(plan):
    """供界面显示的 (级别, 文本) 列表。"""
    lines = [("info", "修改内容：%s" % plan.feature.label), ("info", "Schema 目录：%s" % plan.schema_dir)]
    for item in plan.items:
        level = {INSTALLED: "ok", ADD: "change", MODIFY: "change", CONFLICT: "error", ERROR: "error"}[item.status]
        where = " 原第 %d 行" % item.original_line if item.original_line else ""
        lines.append((level, "[%s] %s  %s%s\n      %s" % (STATUS_TEXT[item.status], file_name(item.file_key),
                                                       item.target, where, item.message)))
    if plan.blocked:
        lines.append(("error", "存在冲突或错误，不能修改。请按提示人工核对后再试。"))
    elif plan.nothing_to_do:
        lines.append(("ok", "当前选择的 Schema 文件已经具备这些字段，无需修改。"))
    else:
        files = sorted(set(file_name(i.file_key) for i in plan.pending))
        lines.append(("warn", "共%d处需要修改，涉及：%s。点击「执行修改」写入（会先备份）。" % (len(plan.pending), "、".join(files))))
    return lines


def _indent_block(text, prefix="        "):
    return "\n".join(prefix + line for line in text.replace("\r\n", "\n").split("\n"))


def format_log(plan, records=None, run_dir=None):
    out = ["==== OpenPlant 工作集 Schema 增补记录 ====",
           "时间：%s" % plan.created.strftime("%Y-%m-%d %H:%M:%S"),
           "修改内容：%s" % plan.feature.label,
           "Schema 目录：%s" % plan.schema_dir]
    if run_dir:
        out.append("备份文件夹：%s" % run_dir)
    if records:
        out.append("")
        out.append("---- 文件变化 ----")
        for record in records:
            out.append(file_name(record["key"]))
            out.append("    原 SHA256：%s" % record["before"])
            out.append("    新 SHA256：%s" % record["after"])
            out.append("    备份：%s" % record["backup"])
    out.append("")
    out.append("---- 明细 ----")
    for item in plan.items:
        head = "[%s] %s" % (STATUS_TEXT[item.status], file_name(item.file_key))
        if item.new_line:
            head += "  修改后第 %d 行" % item.new_line
        if item.original_line:
            head += "（原文件第 %d 行处）" % item.original_line
        out.append(head)
        out.append("    功能：%s" % item.feature)
        out.append("    位置：%s" % item.target)
        out.append("    说明：%s" % item.message)
        if item.details and item.status in (ADD, MODIFY):
            out.append("    内容：")
            for detail in item.details:
                out.append(_indent_block(detail))
        out.append("")
    if plan.blocked:
        out.append("结论：存在冲突或错误，未修改任何文件。")
    elif plan.nothing_to_do:
        out.append("结论：当前选择的 Schema 文件已经具备这些字段，无需修改。")
    elif records:
        out.append("结论：已修改 %d 处，涉及 %d 个文件。重启 OPM 后生效。" % (len(plan.pending), len(records)))
    else:
        out.append("结论：只读检查，共 %d 处需要修改，尚未写入。" % len(plan.pending))
    return "\n".join(out) + "\n"
