using System;
using System.Collections.Generic;
using Bentley.Building.Mechanical.Components;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;
using Bentley.MstnPlatformNET.InteropServices;

namespace SteelSectionProbe
{
    internal static class ActuatorCelGraphics
    {
        private sealed class Template
        {
            internal DgnFile File;
            internal DgnModel Model;
            internal string FileName, Hash, CellName;
            internal ElementHolder Holder;
        }
        private static readonly List<Template> templates = new List<Template>();
        internal static bool HasNativeTemplates { get { return templates.Count > 0; } }

        internal static void RequireContext()
        {
            var model = Session.Instance.GetActiveDgnModel();
            if (!Utilities.IsMicroStationMainThread || model == null || !model.Is3d)
                throw new InvalidOperationException("请在 OPM 主线程激活三维模型。");
            if (Math.Abs(model.GetModelInfo().UorPerMeter - 1000000) > 0.001)
                throw new InvalidOperationException("本轮执行机构验证要求活动模型为 1000000 UOR/m。");
        }

        internal static unsafe ElementHolder Clone(ActuatorCelAsset asset)
        {
            RequireContext();
            var model = Session.Instance.GetActiveDgnModel();
            var file = Session.Instance.GetActiveDgnFile();
            ElementHolder template = null;
            foreach (var item in templates)
                if (ReferenceEquals(item.File, file) && ReferenceEquals(item.Model, model)
                    && item.FileName == file.GetFileName() && item.Hash == asset.Hash && item.CellName == asset.CellName)
                { template = item.Holder; break; }
            if (template == null)
            {
                if (templates.Count >= 32) throw new InvalidOperationException("本轮验证已缓存 32 个模型/单元组合，请正常退出 OPM 后重开。");
                string path = asset.Materialize(ActuatorCelAssetReader.CacheRoot);
                using (var app = new BMApplication())
                {
                    var descriptor = app.GetCellElement(path, asset.CellName);
                    if (descriptor == null) throw new InvalidOperationException("无法读取所选 CEL 的原生几何。");
                    template = new ElementHolder(descriptor);
                    template.SetGraphicsType(BMdGraphicsType.bmdGraphicsTypeEdge, false);
                    templates.Add(new Template { File = file, Model = model, FileName = file.GetFileName(),
                        Hash = asset.Hash, CellName = asset.CellName, Holder = template });
                }
            }
            var clone = template.Clone() as ElementHolder;
            if (clone == null) throw new InvalidOperationException("所选 CEL 原生几何克隆失败。");
            return clone;
        }
    }
}
