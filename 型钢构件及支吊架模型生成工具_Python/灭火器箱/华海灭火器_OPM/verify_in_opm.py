# -*- coding: utf-8 -*-
"""在 OPM Python Manager 运行：核验五种实体高度并实际导出 CEL。

此脚本不在工程模型中放置几何，输出报告和具有唯一名称的单元库。
"""
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0,str(HERE))


def run():
    report = {'native_host_validated':False,'variants':[]}
    try:
        import huahai_bentley as backend
        from huahai_geometry import SPECS
        scale = backend.active_model().GetModelInfo().GetUorPerMeter()/1000.0
        report['uor_per_mm'] = scale
        for key,spec in SPECS.items():
            cell = backend.build_cell(key)
            bounds = backend.DRange3d()
            identity = backend.Transform()
            identity.InitIdentity()
            backend.check(cell.GetDisplayHandler().CalcElementRange(cell,bounds,identity),'读取单元范围')
            low, high = bounds.low.z/scale,bounds.high.z/scale
            if abs(low)>0.01 or abs(high-spec['total_height'])>0.01:
                raise RuntimeError('%s kg 高度不符：%s..%s mm' % (key,low,high))
            report['variants'].append({'capacity':key,'height_mm':high-low,'cell_valid':cell.IsValid()})
        output = HERE/('华海灭火器_已验证_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.cel')
        report['cel'] = backend.export_cell_library(output)
        report['native_host_validated'] = True
        backend.MessageCenter.ShowInfoMessage('五种灭火器验证通过，CEL 已生成。',report['cel'],False)
    except Exception:
        report['error'] = traceback.format_exc()
        print(report['error'])
        try:
            backend.MessageCenter.ShowErrorMessage('华海灭火器验证失败。',report['error'],False)
        except Exception:
            pass
    finally:
        (HERE/'opm_validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    run()
