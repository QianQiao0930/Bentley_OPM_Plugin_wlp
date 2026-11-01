# -*- coding: utf-8 -*-
"""OPM Python Manager 入口：选择华海灭火器、交互放置及生成 CEL。"""
import json
import math
import sys
import traceback
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from huahai_geometry import SPECS, normalize_capacity, cell_name

SETTINGS = HERE / 'last_selection.json'
LOG = HERE / 'huahai_debug.log'


def read_settings():
    try:
        data = json.loads(SETTINGS.read_text(encoding='utf-8'))
        normalize_capacity(data.get('capacity', '4'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def log_error():
    error = traceback.format_exc()
    try:
        with LOG.open('a', encoding='utf-8') as file:
            file.write('\n%s\n%s' % (datetime.now().isoformat(), error))
    except OSError:
        pass
    return error


def show_dialog(settings, seed, runtime_available=True):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk()
    root.title('华海灭火器 · OPM 建模')
    root.configure(bg='#F4F5F7')
    root.resizable(False, False)
    style = ttk.Style(root)
    style.theme_use('clam')
    font = ('Microsoft YaHei UI', 10)
    style.configure('TLabel', font=font, background='#FFFFFF', foreground='#222A35')
    style.configure('TFrame', background='#FFFFFF')
    style.configure('TButton', font=font, padding=(12, 8))
    style.configure('TCombobox', padding=7, font=font)
    style.configure('Accent.TButton', background='#B42C25', foreground='white')
    style.map('Accent.TButton', background=[('active', '#962720')])

    shell = tk.Frame(root, bg='#F4F5F7', padx=24, pady=20)
    shell.pack(fill='both', expand=True)
    tk.Label(shell, text='华海手提式干粉灭火器', font=('Microsoft YaHei UI', 18, 'bold'),
             bg='#F4F5F7', fg='#222A35').pack(anchor='w')
    tk.Label(shell, text='选定规格后，在三维模型中点取底部中心。', font=font,
             bg='#F4F5F7', fg='#667080').pack(anchor='w', pady=(6,16))
    card = ttk.Frame(shell, padding=20)
    card.pack(fill='both', expand=True)
    form = ttk.Frame(card)
    form.grid(row=0, column=0, sticky='nsew')
    capacity = tk.StringVar(value=normalize_capacity(settings.get('capacity', '4')))
    angle = tk.StringVar(value=str(settings.get('angle', 0)))
    dimensions = tk.StringVar()
    discharge = tk.StringVar()
    name = tk.StringVar()
    weight = tk.StringVar()
    choices = tuple('%s kg  /  %s' % (k,s['model']) for k,s in SPECS.items())
    selected = tk.StringVar(value=choices[list(SPECS).index(capacity.get())])

    ttk.Label(form, text='规格型号').grid(row=0, column=0, sticky='w', pady=8)
    combo = ttk.Combobox(form, textvariable=selected, values=choices,
                         state='readonly', width=27)
    combo.grid(row=0, column=1, sticky='ew', padx=(16,0), pady=8)
    ttk.Label(form, text='绕 Z 轴旋转（°）').grid(row=1, column=0, sticky='w', pady=8)
    ttk.Entry(form, textvariable=angle, width=14, font=font).grid(
        row=1, column=1, sticky='w', padx=(16,0), pady=8)
    ttk.Separator(form).grid(row=2, column=0, columnspan=2, sticky='ew', pady=12)
    for row, label, variable in ((3,'筒径 × 总高',dimensions), (4,'喷射配置',discharge),
                                 (5,'充装总质量',weight), (6,'单元名称',name)):
        ttk.Label(form, text=label).grid(row=row, column=0, sticky='nw', pady=6)
        ttk.Label(form, textvariable=variable, wraplength=260).grid(
            row=row, column=1, sticky='w', padx=(16,0), pady=6)
    preview = tk.Canvas(card, width=128, height=250, bg='white', highlightthickness=0)
    preview.grid(row=0, column=1, padx=(20,0), sticky='n')

    def refresh(*args):
        key = list(SPECS)[choices.index(selected.get())]
        capacity.set(key)
        spec = SPECS[key]
        dimensions.set('Ø%d × %d mm' % (spec['body_diameter'],spec['total_height']))
        discharge.set('直喷嘴，无软管' if key == '2' else '软管 400 mm / 外径 18 mm')
        weight.set('%g kg' % spec['filled_weight_kg'])
        name.set(cell_name(key))
        preview.delete('all')
        # 选型示意：实际实体由毫米几何配方生成。
        preview.create_rectangle(34,77,88,214,fill='#CC0906',outline='')
        preview.create_polygon(34,78,51,54,71,54,88,78,fill='#CC0906',outline='')
        preview.create_rectangle(53,45,69,58,fill='#A6A8AD',outline='')
        preview.create_rectangle(28,32,78,38,fill='#121314',outline='')
        preview.create_line(29,22,77,27,fill='#CC0906',width=5)
        preview.create_oval(51,44,69,62,fill='#F0F0E3',outline='#121314',width=3)
        preview.create_line(60,54,64,47,fill='#121314',width=2)
        preview.create_rectangle(46,113,76,164,fill='#F5F2E0',outline='')
        preview.create_text(61,136,text='%s kg' % key,fill='#B42C25',font=font)
        preview.create_rectangle(34,210,88,218,fill='#121314',outline='')
        if key != '2':
            preview.create_line(73,49,105,50,106,98,106,188,smooth=True,
                                fill='#121314',width=5)
            preview.create_polygon(100,183,112,183,115,203,97,203,fill='#121314')
        else:
            preview.create_line(70,50,99,50,fill='#121314',width=6)
        preview.create_text(64,238,text='外形示意',fill='#667080',font=('Microsoft YaHei UI',9))

    combo.bind('<<ComboboxSelected>>', refresh)
    refresh()
    note = ('尺寸沿用原项目的标称值；阀门、压力表、手柄等为外观简化模型。\n'
            '单元底部中心为放置原点，正面朝 −Y，Z 轴向上。')
    tk.Label(card, text=note, justify='left', bg='#F7F8FA', fg='#667080', font=font,
             padx=12, pady=10).grid(row=1,column=0,columnspan=2,sticky='ew',pady=(16,12))
    result = {}

    def collect():
        value = float(angle.get())
        if not math.isfinite(value):
            raise ValueError('旋转角度必须是有限数值。')
        return dict(capacity=capacity.get(), angle=value)

    def finish(action):
        try:
            data = collect()
        except ValueError as error:
            messagebox.showerror('参数错误',str(error),parent=root)
            return
        if action.startswith('export'):
            initial = '华海灭火器_全部规格' if action=='export_all' else cell_name(data['capacity'])
            output = filedialog.asksaveasfilename(parent=root, title='创建 CEL 单元库',
                initialdir=str(HERE), initialfile=initial+'.cel', defaultextension='.cel',
                filetypes=[('Bentley 单元库','*.cel')])
            if not output:
                return
            if Path(output).exists():
                messagebox.showerror('请选择新文件名','该文件已存在，请选择新的单元库文件名。',parent=root)
                return
            chosen_seed = seed
            if not chosen_seed or not Path(chosen_seed).is_file():
                chosen_seed = filedialog.askopenfilename(parent=root,
                    title='选择空白三维 seed3d.dgn 种子文件',filetypes=[('DGN 种子','*.dgn')])
            if not chosen_seed:
                return
            data.update(output=output,seed=chosen_seed)
        try:
            SETTINGS.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        except OSError:
            pass
        result.update(action=action, **data)
        root.destroy()

    buttons = ttk.Frame(card)
    buttons.grid(row=2,column=0,columnspan=2,sticky='ew')
    for text, action in (('导出此规格 CEL','export_one'),('导出全部规格 CEL','export_all')):
        ttk.Button(buttons,text=text,command=lambda a=action:finish(a),
                   state='normal' if runtime_available else 'disabled').pack(side='left',padx=(0,8))
    ttk.Button(buttons,text='点选位置并建模',style='Accent.TButton',command=lambda:finish('place'),
               state='normal' if runtime_available else 'disabled').pack(side='right')
    if not runtime_available:
        tk.Label(shell,text='界面预览模式：建模与 CEL 导出需要在 OPM Python Manager 中运行。',
                 fg='#B42C25',bg='#F4F5F7',font=font).pack(anchor='w',pady=(12,0))
    root.mainloop()
    return result


def show_message(title, message, error=False):
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    try:
        (messagebox.showerror if error else messagebox.showinfo)(title,message,parent=root)
    finally:
        root.destroy()


def main(preview=False):
    if preview:
        show_dialog(read_settings(), '', False)
        return
    try:
        import huahai_bentley as backend
        backend.active_model()
    except Exception:
        error = log_error()
        show_message('无法启动','请在支持 MSPy 的 OPM Python Manager 中运行，并打开三维 DGN。\n\n'+error,True)
        return
    settings = read_settings()
    seed = settings.get('seed') or backend.default_seed()
    while True:
        action = show_dialog(settings,seed)
        if not action:
            return
        settings = action
        try:
            if action['action']=='place':
                backend.install_placement(action['capacity'],action['angle'])
                return
            capacities = tuple(SPECS) if action['action']=='export_all' else (action['capacity'],)
            # 单元库总是采用零原点、零角度，放置角度只影响活动模型。
            output = backend.export_cell_library(action['output'],capacities,action['seed'])
            seed = action['seed']
            show_message('CEL 已生成','已保存 %d 种灭火器单元：\n%s' % (len(capacities),output))
        except Exception:
            error = log_error()
            show_message('操作失败',error+'\n日志：'+str(LOG),True)


if __name__=='__main__':
    main(preview='--ui-preview' in sys.argv)
