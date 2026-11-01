# -*- coding: utf-8 -*-
"""开发验证入口：启动隐藏的 OPM 自动化实例，仅打开独立空白测试 DGN。"""
import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pythoncom
import win32com.client

HERE = Path(__file__).resolve().parent
EXE = Path('D:/Program Files/Bentley/OpenPlant 2024/OpenPlantModeler/OpenPlantModeler.exe')
SEED = EXE.parent/'Default/Seed/seed3d.dgn'


def run():
    scratch = HERE/('_opm_check_'+uuid.uuid4().hex[:8]+'.dgn')
    result_path = HERE/'opm_validation_report.json'
    if result_path.exists():
        raise RuntimeError('请保留已有宿主报告，勿覆盖后重复启动自动验证。')
    pythoncom.CoInitialize()
    try:
        # 不接管用户已有的自动化实例。
        try:
            pythoncom.GetActiveObject('MicroStationDGN.Application')
        except pythoncom.com_error:
            pass
        else:
            raise RuntimeError('已有 Bentley 自动化实例，本次不接管。请在 OPM 中手动运行 verify_in_opm.py。')
        shutil.copyfile(SEED,scratch)
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0  # SW_HIDE
        process = subprocess.Popen([str(EXE),'-automation',str(scratch)],startupinfo=startup)
        print('Started isolated OPM process',process.pid,flush=True)
        app = None
        try:
            for attempt in range(18):
                if process.poll() is not None:
                    raise RuntimeError('OPM 启动后退出，退出码：%s' % process.returncode)
                try:
                    raw = pythoncom.GetActiveObject('MicroStationDGN.Application')
                    app = win32com.client.Dispatch(raw.QueryInterface(pythoncom.IID_IDispatch))
                    break
                except pythoncom.com_error:
                    time.sleep(5)
                    if attempt % 2 == 0:
                        print('Waiting for OPM automation...',flush=True)
            if app is None:
                raise RuntimeError('OPM 在 90 秒内未提供 COM 自动化入口，可能需要登录或完成启动配置。')
            app.Visible = False
            app.OpenDesignFile(str(scratch),False)
            opened = Path(app.ActiveDesignFile.FullName).resolve()
            if opened != scratch.resolve():
                raise RuntimeError('活动文件不是独立测试 DGN，已中止。')
            app.CadInputQueue.SendKeyin('PYTHON RUN "%s"' % (HERE/'verify_in_opm.py'))
            print('Submitted native Python verification',flush=True)
            for attempt in range(24):
                time.sleep(5)
                if result_path.exists():
                    report = json.loads(result_path.read_text(encoding='utf-8'))
                    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
                    return report
                if attempt % 2 == 0:
                    print('Waiting for native verification report...',flush=True)
            raise RuntimeError('已发送 Python 运行命令，但 120 秒内没有验证报告。')
        finally:
            if app is not None:
                try:
                    app.Quit()
                except (pythoncom.com_error, AttributeError):
                    pass
            # 仅清理由本脚本启动、只打开测试文件的进程。
            if process.poll() is None:
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.terminate()
    finally:
        pythoncom.CoUninitialize()


if __name__=='__main__':
    run()
