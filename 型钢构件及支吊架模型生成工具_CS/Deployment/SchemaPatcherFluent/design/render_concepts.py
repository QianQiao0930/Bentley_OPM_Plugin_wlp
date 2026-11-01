"""用真实 FluentQt 控件搭三套静态设计稿（同一内容、Light、1440×900），截图到 concepts/。仅用于设计选择，不是正式界面。"""
import os
import sys

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

import fluentqt as fq  # noqa: E402
from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPainter, QPen  # noqa: E402
from PySide6.QtWidgets import QApplication, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "concepts")
W, H = 1440, 900
MONO = "Cascadia Mono"
RED, GREEN, AMBER, NEUTRAL = QColor("#C42B1C"), QColor("#0F7B0F"), QColor("#9D5D00"), QColor("#616161")

WORKSPACE = r"C:\ProgramData\Bentley\OpenPlant 2024\Configuration\WorkSpaces\CINF_International_Projects_Workspace\WorkSets\CINF_F1301BB\Standards\OpenPlant\Schemas"
BACKUP = r"D:\Schema备份"
FILES = [
    ("OP3D", "OpenPlant_3D.01.08.ecschema.xml", 38627),
    ("MOD", "OpenPlant_3D_Supplemental_Modeling.01.08.ecschema.xml", 38969),
    ("ISO", "OpenPlant_3D_Supplemental_Isometrics_Isoextractor.01.08.ecschema.xml", 4236),
]
# 状态, 文件, 原行号, 功能, 位置, 说明
ITEMS = [
    ("新增", "OP3D", 31877, "增加耳轴", "SIMPLE_ELBOW_SUPPORT / SSP_RECIPE", "增加字段 SSP_RECIPE(string)"),
    ("新增", "OP3D", 32195, "增加耳轴", "SINGLE_PIPE_TRUNNION / SSP_RECIPE", "增加字段 SSP_RECIPE(string)"),
    ("新增", "OP3D", 32402, "增加耳轴", "DOUBLE_PIPE_TRUNNION / SSP_RECIPE", "增加字段 SSP_RECIPE(string)"),
    ("新增", "OP3D", 38627, "正式管夹", "SSP_PIPE_CLAMP", "新增类，继承 SUPPORT_LOCATION"),
    ("新增", "OP3D", 38627, "执行机构", "SSP_CEL_VALVE_ACTUATOR", "新增类，继承 GEARBOX_OPERATOR，6 个 CEL 字段"),
    ("修改", "MOD", 32735, "增加耳轴", "SINGLE_PIPE_TRUNNION / CREATION_ATTRIBUTE",
     "ASSEMBLY_NAME：Bentley.Building.Mechanical.ComponentLibrary → SteelSectionProbe"),
    ("修改", "MOD", 32760, "增加耳轴", "DOUBLE_PIPE_TRUNNION / CREATION_ATTRIBUTE", "处理器改为 NativePipeSupportComponent"),
    ("修改", "MOD", 32790, "增加耳轴", "SIMPLE_ELBOW_SUPPORT / CREATION_ATTRIBUTE", "处理器改为 NativePipeSupportComponent"),
    ("新增", "MOD", 38969, "正式管夹", "SSP_PIPE_CLAMP", "创建属性指向 NativePipeSupportComponent"),
    ("新增", "MOD", 38969, "执行机构", "SSP_CEL_VALVE_ACTUATOR", "处理器 CelValveActuatorComponent"),
    ("新增", "ISO", 3008, "增加耳轴", "SIMPLE_ELBOW_SUPPORT / BOM_LABELS", "IE_TAG = this.ALIAS"),
    ("新增", "ISO", 3016, "增加耳轴", "SINGLE_PIPE_TRUNNION / BOM_LABELS", "IE_TAG = this.ALIAS"),
    ("新增", "ISO", 3024, "增加耳轴", "DOUBLE_PIPE_TRUNNION / BOM_LABELS", "IE_TAG = this.ALIAS"),
    ("新增", "ISO", 4236, "正式管夹", "SSP_PIPE_CLAMP", "IE_TAG = this.ALIAS"),
    ("冲突", "ISO", 2871, "轴测图出图", "SUPPORT_LOCATION / BOM_LABELS", "SUPPORT_LOCATION 已有项目自定义 BOM 标签，禁止覆盖"),
]
SUMMARY = "检查完成：14处待修改（11新增、3修改）"
CONFLICT = "1处冲突，执行修改已锁定"
STATUS_STYLE = {"新增": (fq.Icons.Add, QColor("#005FB8")), "修改": (fq.Icons.Edit, AMBER),
                "冲突": (fq.Icons.ErrorIcon, RED), "已具备": (fq.Icons.CheckMark, GREEN)}


def label(text, role=fq.FontRole.Body, color=None, mono=False, size=None, wrap=False):
    widget = fq.Label(text, fluentTypography=role)
    if mono:
        font = QFont(MONO)
        font.setPointSizeF(size or 9.5)
        widget.setFont(font)
    if color is not None:
        widget.setStyleSheet("color: %s;" % color.name())
    widget.setWordWrap(wrap)
    return widget


def secondary(text, **kw):
    widget = label(text, **kw)
    widget.setTextColorRole(fq.Label.TextColorRole.Secondary)
    return widget


def icon(glyph, color=None, size=16):
    widget = fq.FontIcon(glyph, iconSize=size)
    if color is not None:
        widget.setColor(color)
    widget.setFixedSize(size + 4, size + 4)
    return widget


def button(text, glyph=None, accent=False, enabled=True, subtle=False):
    widget = fq.Button(text)
    if accent:
        widget.setFluentStyle(fq.Button.ButtonStyle.Accent)
    if subtle:
        widget.setFluentStyle(fq.Button.ButtonStyle.Subtle)
    if glyph:
        widget.setIconGlyph(glyph)
        widget.setFluentLayout(fq.Button.ButtonLayout.IconBefore)
    widget.setEnabled(enabled)
    return widget


def card(appearance=fq.Card.Appearance.Layer):
    widget = fq.Card()
    widget.setAppearance(appearance)
    return widget


def path_field(title, text, glyph):
    edit = fq.LineEdit()
    edit.setText(text)
    edit.setCursorPosition(0)
    field = fq.Field(labelText=title)
    field.setEditor(edit)
    row = QHBoxLayout()
    row.setSpacing(8)
    row.addWidget(field, 1)
    browse = button("", glyph)
    browse.setFluentLayout(fq.Button.ButtonLayout.IconOnly)
    browse.setToolTip("浏览…")
    browse.setFixedWidth(36)
    row.addWidget(browse, 0, Qt.AlignBottom)
    return row


def feature_combo(title="修改内容"):
    combo = fq.ComboBox()
    combo.addItems(["全部（以上四项）", "增加耳轴", "增加正式管夹", "修改轴测图出图", "增加自定义执行机构"])
    field = fq.Field(labelText=title)
    field.setEditor(combo)
    return field


def window_with(content, title):
    window = fq.Window(contentWidget=content)
    window.setWindowTitle(title)
    window.resize(W, H)
    return window


def title_strip(layout, subtitle):
    row = QHBoxLayout()
    row.setSpacing(10)
    row.addWidget(icon(fq.Icons.Document, QColor("#005FB8"), 20))
    row.addWidget(label("Schema 增补", fq.FontRole.BodyStrong))
    row.addWidget(secondary(subtitle, role=fq.FontRole.Caption))
    row.addStretch(1)
    layout.addLayout(row)


# ------------------------------------------------------------------ A 关卡三步

def concept_gate():
    root = QWidget()
    outer = QVBoxLayout(root)
    outer.setContentsMargins(28, 4, 28, 20)
    outer.setSpacing(16)
    title_strip(outer, "OpenPlant 工作集")

    stepper = fq.Stepper()
    for text in ("选择工作集", "只读检查", "备份并写入"):
        stepper.addItem(text)
    stepper.setCurrentIndex(1)
    stepper.setItemState(0, fq.Stepper.State.Completed)
    stepper.setItemState(1, fq.Stepper.State.Error)
    stepper.setItemEnabled(2, False)
    stepper.setFixedHeight(92)
    outer.addWidget(stepper)

    body = QHBoxLayout()
    body.setSpacing(20)
    main = QVBoxLayout()
    main.setSpacing(14)
    main.addWidget(label("只读检查", fq.FontRole.TitleLarge))
    main.addWidget(secondary("CINF_F1301BB · 全部（以上四项） · 未写入任何文件"))
    bar = fq.InfoBar(title="1处冲突", message="SUPPORT_LOCATION 已有项目自定义 BOM 标签，禁止覆盖；请人工合并 IE_TAG 条件表达式后重新检查。",
                     severity=fq.InfoBar.InfoBarSeverity.Error, isOpen=True, isClosable=False)
    main.addWidget(bar)
    main.addWidget(label(SUMMARY, fq.FontRole.BodyStrong))

    short = {"OP3D": "OpenPlant_3D", "MOD": "Modeling", "ISO": "Isoextractor"}
    groups = [("修改轴测图出图", "冲突 · SUPPORT_LOCATION 引注按管架编号", True),
              ("增加耳轴", "9处待修改 · 3 个耳轴类 × 三份 Schema", True),
              ("增加正式管夹", "3处待修改 · SSP_PIPE_CLAMP 隔离类", False),
              ("增加自定义执行机构", "2处待修改 · SSP_CEL_VALVE_ACTUATOR", False)]
    for name, desc, expanded in groups:
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(16, 4, 16, 10)
        cl.setSpacing(6)
        rows = [i for i in ITEMS if i[3] == name.replace("增加自定义", "").replace("修改", "").replace("增加", "")
                or (name == "增加耳轴" and i[3] == "增加耳轴")]
        for status, key, line, _, where, note in rows[:5]:
            glyph, color = STATUS_STYLE[status]
            r = QHBoxLayout()
            r.setSpacing(10)
            r.addWidget(icon(glyph, color, 14))
            f = secondary(short[key], role=fq.FontRole.Caption)
            f.setFixedWidth(84)
            r.addWidget(f)
            w = label(where, fq.FontRole.BodyStrong)
            w.setFixedWidth(330)
            r.addWidget(w)
            r.addWidget(label(note, color=RED if status == "冲突" else None), 1)
            cl.addLayout(r)
        if name == "增加耳轴":
            cl.addWidget(secondary("另有 4 处（Isoextractor 引注）…", role=fq.FontRole.Caption))
        expander = fq.Expander(headerText="%s　%s" % (name, desc), contentWidget=content, expanded=expanded,
                               animationEnabled=False)
        main.addWidget(expander)
    main.addStretch(1)
    body.addLayout(main, 1)

    help_card = card(fq.Card.Appearance.LayerAlt)
    help_card.setFixedWidth(340)
    hl = QVBoxLayout(help_card)
    hl.setContentsMargins(20, 18, 20, 18)
    hl.setSpacing(12)
    row = QHBoxLayout()
    row.addWidget(icon(fq.Icons.Lock, NEUTRAL, 18))
    row.addWidget(label("第 3 步已锁定", fq.FontRole.Subtitle))
    row.addStretch(1)
    hl.addLayout(row)
    hl.addWidget(secondary("解决冲突后重新检查，写入才会解锁。", wrap=True))
    hl.addWidget(fq.Divider(Qt.Horizontal))
    hl.addWidget(label("写入时会依次：", fq.FontRole.BodyStrong))
    for glyph, text in ((fq.Icons.Copy, "备份三份原文件到 D:\\Schema备份"), (fq.Icons.Shield, "内存中修改并自检"),
                        (fq.Icons.Save, "逐个替换工作集文件"), (fq.Icons.Undo, "任一失败自动恢复备份")):
        r = QHBoxLayout()
        r.addWidget(icon(glyph, NEUTRAL, 16))
        r.addWidget(label(text, wrap=True), 1)
        hl.addLayout(r)
    hl.addStretch(1)
    body.addWidget(help_card)
    outer.addLayout(body, 1)

    actions = QHBoxLayout()
    actions.addWidget(button("上一步", fq.Icons.Back))
    actions.addWidget(button("保存日志", fq.Icons.SaveAs, subtle=True))
    actions.addStretch(1)
    actions.addWidget(secondary(CONFLICT))
    actions.addWidget(button("重新检查", fq.Icons.Refresh))
    actions.addWidget(button("下一步：备份并写入", fq.Icons.Forward, accent=True, enabled=False))
    outer.addLayout(actions)
    return window_with(root, "Schema 增补 · 关卡三步")


# ------------------------------------------------------------------ B 增补台账

class Gutter(QWidget):
    """台账左侧行号栏：等宽行号 + 状态色条。"""


def ledger_row(item, selected=False):
    status, key, line, feature, where, note = item
    row = QWidget()
    if selected:
        row.setStyleSheet("background: rgba(0,95,184,0.08); border-radius: 4px;")
    grid = QHBoxLayout(row)
    grid.setContentsMargins(8, 4, 12, 4)
    grid.setSpacing(12)
    glyph, color = STATUS_STYLE[status]
    bar = QWidget()
    bar.setFixedSize(3, 22)
    bar.setStyleSheet("background:%s; border-radius:1px;" % color.name())
    grid.addWidget(bar)
    num = label("L%05d" % line, mono=True, color=QColor("#707070"), size=8.5)
    num.setFixedWidth(64)
    grid.addWidget(num)
    st = label(status, fq.FontRole.BodyStrong, color)
    st.setFixedWidth(40)
    grid.addWidget(st)
    loc = label(where, mono=True, size=8.5)
    loc.setTextElideMode(Qt.ElideMiddle)
    loc.setFixedWidth(360)
    grid.addWidget(loc)
    feat = secondary(feature, role=fq.FontRole.Caption)
    feat.setFixedWidth(76)
    grid.addWidget(feat)
    n = label(note, color=RED if status == "冲突" else None)
    n.setTextElideMode(Qt.ElideRight)
    grid.addWidget(n, 1)
    row.setFixedHeight(32)
    return row


def concept_ledger():
    root = QWidget()
    outer = QVBoxLayout(root)
    outer.setContentsMargins(24, 4, 24, 16)
    outer.setSpacing(12)
    title_strip(outer, "增补台账")

    inputs = QHBoxLayout()
    inputs.setSpacing(12)
    inputs.addLayout(path_field("Schema 目录", WORKSPACE, fq.Icons.Folder), 5)
    inputs.addLayout(path_field("备份文件夹", BACKUP, fq.Icons.Folder), 2)
    combo = feature_combo()
    inputs.addWidget(combo, 2)
    check = button("检查", fq.Icons.Search)
    inputs.addWidget(check, 0, Qt.AlignBottom)
    outer.addLayout(inputs)

    body = QHBoxLayout()
    body.setSpacing(16)
    ledger = card()
    lv = QVBoxLayout(ledger)
    lv.setContentsMargins(8, 10, 8, 10)
    lv.setSpacing(2)
    header = QHBoxLayout()
    header.setContentsMargins(23, 0, 12, 6)
    header.setSpacing(12)
    for text, width in (("行号", 64), ("状态", 40), ("位置", 360), ("功能", 76), ("说明", 0)):
        h = secondary(text, role=fq.FontRole.Caption)
        if width:
            h.setFixedWidth(width)
        header.addWidget(h, 0 if width else 1)
    lv.addLayout(header)
    for key, name, total in FILES:
        fh = QHBoxLayout()
        fh.setContentsMargins(8, 8, 12, 2)
        fh.addWidget(icon(fq.Icons.File, NEUTRAL, 14))
        fh.addWidget(label(name, fq.FontRole.BodyStrong))
        fh.addWidget(secondary("共 %d 行" % total, role=fq.FontRole.Caption))
        fh.addStretch(1)
        lv.addLayout(fh)
        for item in ITEMS:
            if item[1] == key:
                lv.addWidget(ledger_row(item, selected=item[2] == 32735))
    lv.addStretch(1)
    body.addWidget(ledger, 1)

    detail = card(fq.Card.Appearance.LayerAlt)
    detail.setFixedWidth(380)
    dv = QVBoxLayout(detail)
    dv.setContentsMargins(18, 16, 18, 16)
    dv.setSpacing(10)
    dv.addWidget(secondary("改动详情", role=fq.FontRole.Caption))
    dv.addWidget(label("SINGLE_PIPE_TRUNNION", fq.FontRole.Subtitle))
    dv.addWidget(secondary("Modeling · CREATION_ATTRIBUTE · 原第 32735 行", role=fq.FontRole.Caption))
    for field_name, before, after in (("ASSEMBLY_NAME", "Bentley.Building.Mechanical\n.ComponentLibrary", "SteelSectionProbe"),
                                      ("NAMESPACE", "…ComponentLibrary.Supports", "SteelSectionProbe"),
                                      ("CLASS_NAME", "SinglePipeTrunnion", "NativePipeSupportComponent")):
        dv.addWidget(label(field_name, mono=True, color=QColor("#707070"), size=9))
        old = label("− " + before, mono=True, color=RED, wrap=True)
        new = label("+ " + after, mono=True, color=GREEN)
        dv.addWidget(old)
        dv.addWidget(new)
    dv.addWidget(fq.Divider(Qt.Horizontal))
    note = fq.InfoBar(title="注意", message="改的是 OPM 自带耳轴类，改后所有耳轴都需要本插件。",
                      severity=fq.InfoBar.InfoBarSeverity.Warning, isOpen=True, isClosable=False)
    dv.addWidget(note)
    dv.addStretch(1)
    body.addWidget(detail)
    outer.addLayout(body, 1)

    foot = QHBoxLayout()
    foot.setSpacing(16)
    for status, count in (("新增", 11), ("修改", 3), ("冲突", 1)):
        glyph, color = STATUS_STYLE[status]
        foot.addWidget(icon(glyph, color, 14))
        foot.addWidget(label("%s %d" % (status, count), fq.FontRole.BodyStrong, color))
    foot.addWidget(secondary("· " + CONFLICT))
    foot.addStretch(1)
    foot.addWidget(button("保存日志", fq.Icons.SaveAs))
    foot.addWidget(button("执行修改", fq.Icons.Save, accent=True, enabled=False))
    outer.addLayout(foot)
    return window_with(root, "Schema 增补 · 增补台账")


# ------------------------------------------------------------------ C 三联文件

class Ruler(QWidget):
    """文件长度标尺：刻度位置 = 改动所在行 / 文件总行数。"""

    def __init__(self, total, marks):
        super().__init__()
        self.total = total
        self.marks = marks
        self.setFixedWidth(22)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rail = QRectF(9, 4, 4, self.height() - 8)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 22))
        p.drawRoundedRect(rail, 2, 2)
        for line, status in self.marks:
            y = rail.top() + rail.height() * line / float(self.total)
            p.setPen(QPen(STATUS_STYLE[status][1], 3))
            p.drawLine(3, int(y), 19, int(y))
        p.end()


def concept_triptych():
    root = QWidget()
    outer = QVBoxLayout(root)
    outer.setContentsMargins(24, 4, 24, 16)
    outer.setSpacing(14)
    title_strip(outer, "三份 Schema")

    top = QHBoxLayout()
    top.setSpacing(12)
    top.addLayout(path_field("Schema 目录", WORKSPACE, fq.Icons.Folder), 4)
    top.addWidget(feature_combo(), 2)
    top.addWidget(button("检查", fq.Icons.Search), 0, Qt.AlignBottom)
    top.addWidget(button("执行修改", fq.Icons.Save, accent=True, enabled=False), 0, Qt.AlignBottom)
    outer.addLayout(top)

    columns = QHBoxLayout()
    columns.setSpacing(14)
    short = {"OP3D": "OpenPlant_3D", "MOD": "Supplemental_Modeling", "ISO": "Isometrics_Isoextractor"}
    for key, name, total in FILES:
        col = card()
        cv = QVBoxLayout(col)
        cv.setContentsMargins(14, 14, 14, 14)
        cv.setSpacing(8)
        items = [i for i in ITEMS if i[1] == key]
        conflicts = sum(1 for i in items if i[0] == "冲突")
        head = QHBoxLayout()
        head.addWidget(icon(fq.Icons.File, NEUTRAL, 18))
        title = QVBoxLayout()
        title.setSpacing(0)
        title.addWidget(label(short[key], fq.FontRole.Subtitle))
        title.addWidget(secondary(name, role=fq.FontRole.Caption))
        head.addLayout(title, 1)
        badge = label("%d处%s" % (len(items), "，含冲突" if conflicts else ""), fq.FontRole.BodyStrong,
                      RED if conflicts else QColor("#005FB8"))
        head.addWidget(badge, 0, Qt.AlignTop)
        cv.addLayout(head)
        cv.addWidget(fq.Divider(Qt.Horizontal))
        body = QHBoxLayout()
        body.setSpacing(10)
        body.addWidget(Ruler(total, [(i[2], i[0]) for i in items]))
        lst = QVBoxLayout()
        lst.setSpacing(10)
        for status, _, line, feature, where, note in sorted(items, key=lambda i: i[2]):
            glyph, color = STATUS_STYLE[status]
            r = QHBoxLayout()
            r.setSpacing(8)
            r.addWidget(icon(glyph, color, 14), 0, Qt.AlignTop)
            t = QVBoxLayout()
            t.setSpacing(1)
            t.addWidget(label(where, fq.FontRole.BodyStrong, wrap=True))
            t.addWidget(label(note, fq.FontRole.Caption, RED if status == "冲突" else None, wrap=True))
            meta = QHBoxLayout()
            meta.setSpacing(6)
            meta.addWidget(label("L%05d" % line, mono=True, size=8, color=QColor("#707070")))
            meta.addWidget(secondary(feature, role=fq.FontRole.Caption))
            meta.addStretch(1)
            t.addLayout(meta)
            r.addLayout(t, 1)
            lst.addLayout(r)
        lst.addStretch(1)
        body.addLayout(lst, 1)
        cv.addLayout(body, 1)
        foot = secondary("共 %d 行 · 刻度表示改动在文件中的位置" % total, role=fq.FontRole.Caption)
        cv.addWidget(foot)
        columns.addWidget(col, 1)
    outer.addLayout(columns, 1)

    pipe = card(fq.Card.Appearance.LayerAlt)
    pl = QHBoxLayout(pipe)
    pl.setContentsMargins(18, 12, 18, 12)
    pl.setSpacing(14)
    for i, (glyph, text, state) in enumerate(((fq.Icons.Search, "只读检查", "完成"), (fq.Icons.Copy, "备份", "等待"),
                                             (fq.Icons.Save, "写入", "等待"), (fq.Icons.Shield, "自检", "等待"))):
        done = state == "完成"
        pl.addWidget(icon(fq.Icons.CheckMark if done else glyph, GREEN if done else NEUTRAL, 16))
        pl.addWidget(label(text, fq.FontRole.BodyStrong if done else fq.FontRole.Body))
        if i < 3:
            bar = fq.ProgressBar(value=100 if done else 0)
            bar.setFixedWidth(90)
            pl.addWidget(bar)
    pl.addStretch(1)
    pl.addWidget(icon(fq.Icons.ErrorIcon, RED, 16))
    pl.addWidget(label("等待：解决 1 处冲突（Isoextractor · SUPPORT_LOCATION）", fq.FontRole.BodyStrong, RED))
    outer.addWidget(pipe)
    return window_with(root, "Schema 增补 · 三联文件")


def main():
    os.makedirs(OUT, exist_ok=True)
    app = QApplication(sys.argv)
    fq.initialize_resources()
    fq.set_theme(fq.Theme.Light)
    windows = {"guided-flow": concept_gate(), "single-canvas": concept_ledger(), "queue-first": concept_triptych()}
    for name, window in windows.items():
        window.show()
        for _ in range(20):
            app.processEvents()
        target = os.path.join(OUT, name + ".png")
        window.grab().save(target)
        print(target, window.grab().size())
        window.close()


if __name__ == "__main__":
    main()
