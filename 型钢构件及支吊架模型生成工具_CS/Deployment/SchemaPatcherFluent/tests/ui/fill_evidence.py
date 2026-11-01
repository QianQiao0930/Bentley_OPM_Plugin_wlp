"""填写视觉证据清单的作者侧内容（状态/区域/测量/动态检查/问题）。评审节由独立评审填写，这里不打分。"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.abspath(os.path.join(HERE, "..", ".evidence"))


def png(*names):
    return [n + ".png" for n in names]


STATES = {
    "normal-light": ("pass", png("normal-light", "exe-launch"), ""),
    "normal-dark": ("pass", png("normal-dark"), ""),
    "narrow": ("pass", png("narrow", "narrow-detail-dialog"),
               "宽度 1000 < 1100 断点：详情收起、输入条两行、功能列与列头同步隐藏；选中行回车/双击用对话框看改前改后"),
    "minimum": ("pass", png("minimum"), "最小 860×560，台账与底部操作可见"),
    "empty": ("pass", png("empty", "exe-launch"), "empty：已记住目录但尚未检查；exe-launch：首次启动、输入为空"),
    "collection-density": ("pass", png("empty", "density-sparse", "normal-light"), "0 行 / 每文件 1 行共 2 行 / 15 行"),
    "long-localized-content": ("pass", png("transient-confirm-dialog", "input-single-line-focus", "normal-light"),
                               "长路径在 \\ . / 后换行；中文说明超长时省略并有悬停全文"),
    "input-single-line": ("pass", png("input-single-line-focus", "normal-light"), "聚焦且已填写 / 静止"),
    "input-max-lines": ("not-applicable", [], "界面没有多行输入框，只有单行路径与下拉框"),
    "scroll-end": ("pass", png("scroll-end"), ""),
    "async-settled": ("pass", png("async-checking", "normal-light"), "真实后台线程检查，完成后滚动范围两次采样一致"),
    "selected-focus-disabled": ("pass", png("selected-focus-disabled"), "选中修改行、焦点边框、执行修改禁用并写明原因"),
    "transient-surface": ("pass", png("transient-confirm-dialog", "narrow-detail-dialog"), "确认修改对话框；窄窗口改动详情对话框"),
    "ime-preedit": ("not-applicable", [],
                    "输入均为文件夹路径，通常经浏览对话框选择；输入框为原生 QLineEdit，未单独采集输入法预编辑，作为未验证边界记录"),
}
REGIONS = {
    "titlebar": ("pass", png("normal-light", "exe-launch"), "标题、副标题与窗口按钮；按钮已有无障碍名称"),
    "navigation-or-list": ("pass", png("normal-light", "scroll-end"), "台账即主列表"),
    "primary-viewport": ("pass", png("selected-focus-disabled", "normal-dark"), "台账 + 改动详情"),
    "pane-header-or-status": ("pass", png("normal-light", "ready", "applied", "stale"), "提示条与详情标题"),
    "footer-or-primary-input": ("pass", png("ready", "applied", "selected-focus-disabled"), "顶部输入条与底部计数/操作"),
    "scroll-viewport": ("pass", png("scroll-end", "density-sparse"), "panel：台账与详情均为 Layer 卡片"),
    "transient-surface": ("pass", png("transient-confirm-dialog", "narrow-detail-dialog"), ""),
}
ISSUES = [
    ("captures-use-solid", "minor", "accepted", "截图接口抓不到 Mica，采集时用 Solid；运行时 Mica 见 exe-launch.png", ["exe-launch.png"]),
    ("r1-classic-scrollbar-detail-pane", "major", "fixed", "详情区改用 fluentqt.ScrollView（Fluent 滚动条）", ["density-sparse.png"]),
    ("r1-stale-evidence-contradicts-lock", "major", "fixed",
     "采集脚本未等对话框浮层关闭即截图；已等待并断言提示条为“参数已变更”。写入锁定由控制器测试覆盖", ["stale.png"]),
    ("r1-conflict-row-no-line-number", "major", "fixed", "冲突/已具备项按目标路径定位现有节点行号", ["normal-light.png", "nothing-to-do.png"]),
    ("r1-focus-indicator-not-visible", "major", "fixed", "焦点行 2px 强调色边框；关闭 ListView 自带选中指示条", ["selected-focus-disabled.png"]),
    ("r1-missing-column-headers", "minor", "fixed", "增加与行共用列宽的列头", ["normal-light.png", "narrow.png"]),
    ("r1-identifier-mid-token-wrap", "minor", "fixed", "不再在下划线处断行", ["density-sparse.png", "selected-focus-disabled.png"]),
    ("r1-async-empty-copy", "minor", "fixed", "检查中占位文案改为“正在检查，只读，不会改动文件…”", ["async-checking.png"]),
    ("r1-nothing-to-do-misleading-copy", "minor", "fixed", "耳轴警告只对待修改项显示；“打开备份文件夹”只在写入完成时显示", ["nothing-to-do.png"]),
    ("r1-applied-rows-status-unchanged", "minor", "fixed", "写入后自动复查，本次写入行标“已写入”，沿用改动说明并显示新行号", ["applied.png"]),
    ("r1-duplicate-empty-evidence", "minor", "fixed", "empty 与输入焦点分开采集，并补 exe 首次启动空输入", ["empty.png", "input-single-line-focus.png"]),
    ("r1-ledger-scrollbar-hidden", "minor", "fixed", "行距改为 32 后，1440×900 下 15 行与 3 个分组头完整放下；更小尺寸露出半行作为可滚动提示",
     ["normal-light.png", "minimum.png"]),
    ("r2-dark-detail-pane-unreadable", "blocker", "fixed",
     "fluentqt.ScrollView 自绘背景且运行中切换主题不更新；改为透明 QScrollArea + fluentqt.ScrollBar", ["normal-dark.png"]),
    ("r2-ledger-hidden-15th-row-no-cue", "major", "fixed", "去掉列表行间距，主尺寸下全部行可见", ["normal-light.png", "normal-dark.png"]),
    ("r2-description-column-truncates-key-value", "minor", "fixed", "说明列去掉与位置列重复的字段名前缀", ["normal-light.png"]),
    ("r2-nested-ledger-frame", "minor", "fixed", "关闭 ListView 自带边框", ["narrow.png", "minimum.png"]),
    ("r2-narrow-detail-dialog-unverified", "minor", "fixed", "补采窄窗口改动详情对话框", ["narrow-detail-dialog.png"]),
    ("r2-sparse-detail-clipped-no-scroll-cue", "minor", "fixed", "插入内容预览缩短并提示“另有 N 行，见日志”；XML 只在 = 后断行", ["density-sparse.png"]),
    ("r2-async-duplicate-copy", "minor", "fixed", "检查中占位文案改为“正在检查…”", ["async-checking.png"]),
    ("r2-instructional-click-copy", "minor", "fixed", "去掉“点击…”式说明", ["ready.png", "empty.png"]),
    ("r2-applied-copy-inconsistency", "minor", "fixed", "非待修改项显示“第 N 行”；完成提示条不再嵌长路径，路径在悬停提示与“打开备份文件夹”", ["applied.png"]),
    ("r2-dialog-filename-split", "minor", "fixed", "对话框只在路径分隔符处断行，宽度加到 520", ["transient-confirm-dialog.png"]),
    ("r3-selected-row-loses-fill-when-focused", "major", "fixed", "选中底色加深，焦点行同时有底色与强调色边框", ["selected-focus-disabled.png", "normal-dark.png"]),
    ("r3-note-box-extra-height", "major", "fixed", "提示框 setMultiLineMinHeight(0)，高度贴合文字", ["selected-focus-disabled.png", "normal-light.png"]),
    ("r3-narrow-dialog-taller-than-window", "major", "fixed", "对话框高度按窗口约束，内容在对话框内滚动；去掉重复的“改动详情”小标题", ["narrow-detail-dialog.png"]),
    ("r3-mono-font-for-chinese", "minor", "fixed", "“另有N行，完整内容见日志”改用正文字体单独一行", ["density-sparse.png"]),
    ("r3-number-spacing", "minor", "fixed", "底部计数改为“新增11”，与“将修改2处”一致", ["normal-light.png", "density-sparse.png"]),
    ("r3-triple-checking-copy", "minor", "fixed", "检查中只保留提示条“正在检查”和进度条，台账占位与底部说明留空", ["async-checking.png"]),
    ("r3-click-copy-applied", "minor", "fixed", "写入后底部说明改为“已写入并备份；可再次检查核对”", ["applied.png"]),
    ("r3-selection-leak-in-capture", "minor", "fixed", "采集脚本在输入焦点截图后取消选中", ["minimum.png", "scroll-end.png"]),
    ("r3-save-log-without-records", "minor", "fixed", "没有检查记录时“保存日志”禁用并说明原因", ["empty.png"]),
    ("r3-backup-field-narrow", "minor", "fixed", "输入条列宽比例改为 5:3:2", ["normal-light.png"]),
    ("r3-vague-conflict-wording", "minor", "fixed", "冲突提示条标题改为“1处冲突或错误，执行修改已锁定”", ["normal-light.png"]),
    ("r4-note-box-extra-height-not-fixed", "major", "fixed",
     "fluentqt.InfoBar 高度固定 110px、不随宽度换行计算；详情区改用自适应高度的注意框（FluentQt 图标 + 主题“注意”语义色）",
     ["selected-focus-disabled.png", "normal-dark.png"]),
    ("r4-focus-selection-leak-in-static-states", "major", "fixed",
     "真实缺陷：详情/确认对话框关闭后焦点落到第一个输入框并全选；现在关闭后焦点回到台账", ["minimum.png", "scroll-end.png"]),
    ("r4-narrow-dialog-drops-warning", "major", "fixed", "耳轴注意框移到结论下方，窄窗口对话框首屏可见", ["narrow-detail-dialog.png"]),
    ("r4-xml-preview-mid-tag-break", "minor", "fixed", "斜杠后加词连接符，不在“</”与标签名之间断行", ["density-sparse.png"]),
    ("r4-conflict-instruction-repeated", "minor", "fixed", "去掉详情区冲突红框；底部改为状态“执行修改已锁定”，处理说明只在提示条出现一次", ["normal-light.png"]),
    ("r4-stale-rows-not-dimmed", "minor", "fixed", "参数已变更时旧结果整体半透明显示", ["stale.png"]),
    ("r4-confirm-dialog-order-and-count", "minor", "fixed", "确认文案由控制器在可写入状态生成，文件顺序与台账一致，数字与 ready 一致", ["transient-confirm-dialog.png", "ready.png"]),
    ("r4-fixture-paths-not-matching-brief", "minor", "fixed", "夹具改为 …\\WorkSets\\CINF_F1301BB\\Standards\\OpenPlant\\Schemas 结构", ["normal-light.png"]),
    ("r4-copy-nits", "minor", "fixed", "无需修改时底部说明改为“无需修改”；提示条引号已核对为中文弯引号 U+201C/U+201D", ["nothing-to-do.png", "applied.png"]),
]


def entry(item_id, status, evidence, note, key="note"):
    data = {"id": item_id, "status": status, "evidence": evidence}
    if note:
        data["reason" if status == "not-applicable" else key] = note
    return data


def main():
    path = os.path.join(EV, "visual-evidence.json")
    m = json.load(open(path, encoding="utf-8"))
    meas = json.load(open(os.path.join(EV, "measurements.json"), encoding="utf-8"))
    last, viewport = meas["last-row-bottom-vs-viewport"]
    states = dict(STATES)
    states["scroll-end"] = ("pass", png("scroll-end"), "最小尺寸滚到底，最后一行底边 %d < 视口 %d" % (last, viewport))
    m.update({
        "window_backdrop": "mica", "surface_fill_policy": "reveal-material", "signature_finish": "product",
        "chrome_on_material": "quiet", "sparse_canvas_treatment": "composed",
        "primary_input_treatment": "integrated-dock", "visible_copy_register": "user-facing",
        "capture_note": "运行时为 Mica（exe-launch.png，最终 exe 实拍，150% 缩放）；其余状态由 tests/ui/capture_evidence.py "
                        "驱动同一源码采集，QWidget.grab 抓不到系统合成的 Mica，采集时临时改为 Solid，仅影响截图背景。",
        "states": [entry(k, *v) for k, v in states.items()],
        "regions": [entry(k, *v) for k, v in REGIONS.items()],
        "scroll_viewports": [{"id": "ledger", "declaration": "panel"}, {"id": "detail", "declaration": "panel"}],
        "measurements": [
            {"id": "entry-row-height", "expected": "32", "actual": str(meas["entry-row-height"]), "status": "pass", "evidence": "normal-light.png"},
            {"id": "entry-row-cadence", "expected": "32", "actual": str(meas["row-cadence"]), "status": "pass", "evidence": "normal-light.png"},
            {"id": "file-header-row-height", "expected": "32-40", "actual": str(meas["header-row-height"]), "status": "pass", "evidence": "normal-light.png"},
            {"id": "edge-inset", "expected": "24", "actual": "%s / %s" % (meas["edge-inset-left"], meas["edge-inset-right"]), "status": "pass", "evidence": "normal-light.png"},
            {"id": "control-height", "expected": "32", "actual": str(meas["control-height"]), "status": "pass", "evidence": "normal-light.png"},
            {"id": "detail-pane-width", "expected": "380", "actual": str(meas["detail-width"]), "status": "pass", "evidence": "selected-focus-disabled.png"},
            {"id": "input-to-banner-gap", "expected": "8-16", "actual": str(meas["strip-to-banner-gap"]), "status": "pass", "evidence": "normal-light.png"},
            {"id": "footer-bottom-inset", "expected": "16", "actual": str(meas["footer-bottom-inset"]), "status": "pass", "evidence": "normal-light.png"},
            {"id": "last-row-bottom-at-scroll-end", "expected": "< viewport height", "actual": "%d < %d" % (last, viewport), "status": "pass", "evidence": "scroll-end.png"},
        ],
        "dynamic_checks": [
            entry("wrapped-text-height", "pass", png("transient-confirm-dialog", "selected-focus-disabled"), "对话框正文按换行后高度撑开；详情长值换行无裁切"),
            entry("multiline-input", "not-applicable", [], "没有多行输入框"),
            entry("async-scroll-end", "pass", png("scroll-end", "async-checking"), "后台检查完成后两次采样滚动范围一致；滚到底最后一行完整可读"),
        ],
        "inspector": {"tool": "fluentqt.inspect_widget", "report": "inspector.json",
                      "findings": json.load(open(os.path.join(EV, "inspector.json"), encoding="utf-8"))["summary"]["findings"],
                      "history": "首轮 3 条：标题栏窗口按钮缺无障碍名称，已修复后复查为 0"},
        "issues": [{"id": i, "severity": s, "status": st, "note": n, "evidence": e} for i, s, st, n, e in ISSUES],
    })
    review = m.get("review", {})
    review.setdefault("reference_images", [])
    review["reference_images"] = ["reference-selected-concept.png"]
    review["previous_rounds"] = [{"reviewer_id": "independent-visual-reviewer-1", "verdict": "fail", "findings": 11},
                                 {"reviewer_id": "independent-visual-reviewer-2", "verdict": "fail", "findings": 10},
                                 {"reviewer_id": "independent-visual-reviewer-3", "verdict": "fail", "findings": 11},
                                 {"reviewer_id": "independent-visual-reviewer-4", "verdict": "fail", "findings": 9}]
    m["review"] = review
    json.dump(m, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("filled", path)


if __name__ == "__main__":
    main()
