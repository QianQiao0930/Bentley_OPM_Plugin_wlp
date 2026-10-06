using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// <c>PIPEALIGN DEBUG</c> 的属性检查工具（开发指南 §31、§40 Phase 2）。
    /// <para>
    /// **只读**：不修改模型、不写 ItemType、不移动任何对象。用途是在正式开发 UI 之前
    /// 先把"能不能识别 PIPE、能不能拿到中心线、能不能拿到真实外径、能不能拿到连通性"
    /// 这四件事确认下来。
    /// </para>
    /// <para>打印内容刻意覆盖指南 §31 要求的全部字段。</para>
    /// </summary>
    internal static class PipeDebugReport
    {
        internal static string Build(PipeAlignSession session, bool dumpAllProperties)
        {
            if (session == null) throw new ArgumentNullException("session");

            StringBuilder builder = new StringBuilder();
            builder.AppendLine("PipeAlign DEBUG —— 只读数据检查");
            builder.AppendLine("运行参数：" + session.DescribeTolerance());
            builder.AppendLine("OpenPlant 适配器：" + session.Adapter.Name);
            builder.AppendLine();

            List<LocatedElement> candidates = CollectCandidates(session, builder);
            if (candidates.Count == 0)
            {
                builder.AppendLine("没有可检查的对象。");
                builder.AppendLine("用法：先在模型里选中若干管道（或在窗口里选好基准管 / 目标管），再执行 PIPEALIGN DEBUG。");
                return builder.ToString();
            }

            builder.AppendLine("待检查对象：" + candidates.Count + " 个");
            builder.AppendLine(new string('=', 72));

            foreach (LocatedElement located in candidates)
            {
                try
                {
                    PipeInfo pipe = session.ReadPipe(located, dumpAllProperties, true);
                    AppendPipe(builder, pipe, dumpAllProperties);
                }
                catch (Exception ex)
                {
                    builder.AppendLine("元素 0x" + located.ElementId.ToString("X")
                        + " 读取失败：" + ex.Message);
                    builder.AppendLine();
                }
            }

            builder.AppendLine(new string('=', 72));
            builder.AppendLine("提示：本命令只读，模型未被修改。");
            return builder.ToString();
        }

        private static List<LocatedElement> CollectCandidates(PipeAlignSession session, StringBuilder builder)
        {
            var list = new List<LocatedElement>();

            // 1) 窗口里已经选好的对象优先。用 pipe.Source 里记的元素身份（含模型引用），
            //    否则参考文件里的管道会被当成活动模型的同号元素读成别的构件。
            if (session.ReferencePipe != null && session.ReferencePipe.ElementId != 0UL)
                list.Add(SourceOf(session.ReferencePipe));
            foreach (PipeInfo target in session.TargetPipes)
                if (target.ElementId != 0UL)
                    list.Add(SourceOf(target));
            if (list.Count > 0)
            {
                builder.AppendLine("（对象来自窗口里已选的基准管 / 目标管）");
                return list;
            }

            // 2) 否则读当前选择集。
            try
            {
                if (!SelectionSetManager.IsActive() || SelectionSetManager.NumSelected() == 0) return list;
                builder.AppendLine("（对象来自当前选择集）");
                uint count = SelectionSetManager.NumSelected();
                for (uint index = 0; index < count; index++)
                {
                    Element element = null;
                    DgnModelRef modelRef = null;
                    if (SelectionSetManager.GetElement(index, ref element, ref modelRef) != StatusInt.Success)
                        continue;
                    if (element == null) continue;
                    list.Add(new LocatedElement
                    {
                        ModelRef = modelRef ?? element.DgnModelRef,
                        ElementId = (ulong)element.ElementId
                    });
                }
            }
            catch (Exception ex)
            {
                builder.AppendLine("读取选择集失败：" + ex.Message);
            }
            return list;
        }

        /// <summary>取回管道记录里的元素身份；没有记录时退回"活动模型 + 元素 ID"。</summary>
        private static LocatedElement SourceOf(PipeInfo pipe)
        {
            var located = pipe.Source as LocatedElement;
            if (located != null) return located;
            return new LocatedElement { ElementId = pipe.ElementId };
        }

        private static void AppendPipe(StringBuilder builder, PipeInfo pipe, bool dumpAllProperties)
        {
            builder.AppendLine("EC Schema        : " + Show(pipe.SchemaName));
            builder.AppendLine("EC 类            : " + Show(pipe.ClassName));
            builder.AppendLine("Element ID       : " + pipe.ElementIdText);
            builder.AppendLine("实例 ID          : " + Show(pipe.InstanceId));
            builder.AppendLine("管线号           : " + Show(pipe.PipeNumber));
            builder.AppendLine("管道等级         : " + Show(pipe.Specification));
            builder.AppendLine("公称直径 (mm)    : " + Number(pipe.NominalDiameterMm));
            builder.AppendLine("外径 Do (mm)     : " + Number(pipe.OutsideDiameterMm));
            builder.AppendLine("壁厚 (mm)        : " + Number(pipe.WallThicknessMm));
            builder.AppendLine("保温厚度 (mm)    : " + Number(pipe.InsulationThicknessMm));
            builder.AppendLine("保温材料         : " + Show(pipe.InsulationMaterial));
            builder.AppendLine("属性长度单位     : " + pipe.PropertyLengthScale.ToString("G", CultureInfo.InvariantCulture)
                + "（" + Show(pipe.PropertyLengthScaleSource) + "）");
            builder.AppendLine("只读 / 锁定      : " + (pipe.IsReadOnly ? "只读 " : "")
                + (pipe.IsLocked ? "锁定" : (pipe.IsReadOnly ? "" : "否"))
                + (pipe.IsFromReference ? " 参考文件" : ""));
            builder.AppendLine("中心线           : " + (pipe.Axis == null ? "取不到" : pipe.Axis.ToString()));
            builder.AppendLine("中心线来源       : " + Show(pipe.AxisSource));
            builder.AppendLine("中心线标高 Zc    : " + (pipe.Axis == null
                ? "—"
                : pipe.Axis.CenterElevationMm.ToString("F3", CultureInfo.InvariantCulture) + " mm"));
            builder.AppendLine("起点 / 终点      : " + AxisPoints(pipe.Axis));
            builder.AppendLine("水平判定         : " + (pipe.Axis == null
                ? "—"
                : (pipe.Axis.IsHorizontal(1.0) ? "水平（容差 1 mm）" : "非水平，高差 "
                    + pipe.Axis.DeltaZmm.ToString("F3", CultureInfo.InvariantCulture) + " mm")));
            builder.AppendLine("管底 / 管顶 (裸) : " + BottomTop(pipe, SurfaceMode.Pipe));
            builder.AppendLine("管底 / 管顶(保温): " + BottomTop(pipe, SurfaceMode.Insulation));
            builder.AppendLine("连接关系         : " + (pipe.Topology == null ? "未读取" : pipe.Topology.Summary()));
            if (pipe.Topology != null && pipe.Topology.Connections.Count > 0)
            {
                foreach (PipeConnection connection in pipe.Topology.Connections)
                    builder.AppendLine("                  · " + connection.Describe());
            }
            builder.AppendLine("移动能力探测     : " + (pipe.MoveProbe == null ? "未探测" : pipe.MoveProbe.Describe()));
            if (!string.IsNullOrEmpty(pipe.ReadWarning))
                builder.AppendLine("读取提示         : " + pipe.ReadWarning);

            if (dumpAllProperties && pipe.AllProperties.Count > 0)
            {
                builder.AppendLine("---- 全部 EC 属性 (" + pipe.AllProperties.Count + ") ----");
                foreach (KeyValuePair<string, string> pair in pipe.AllProperties)
                    builder.AppendLine("  " + pair.Key + " = " + pair.Value);
            }

            builder.AppendLine();
        }

        private static string BottomTop(PipeInfo pipe, SurfaceMode surfaceMode)
        {
            if (pipe.Axis == null) return "—";
            double diameter = pipe.EffectiveDiameterMm(surfaceMode);
            if (diameter <= 0.0) return "缺少外径";
            double center = pipe.Axis.CenterElevationMm;
            return string.Format(CultureInfo.InvariantCulture,
                "{0:F3} / {1:F3} mm（Deff = {2:F3}）",
                ElevationCalculator.BottomElevation(center, diameter),
                ElevationCalculator.TopElevation(center, diameter), diameter);
        }

        private static string AxisPoints(PipeAxis axis)
        {
            if (axis == null) return "—";
            return string.Format(CultureInfo.InvariantCulture,
                "({0:F2},{1:F2},{2:F2}) → ({3:F2},{4:F2},{5:F2})",
                axis.StartXmm, axis.StartYmm, axis.StartZmm,
                axis.EndXmm, axis.EndYmm, axis.EndZmm);
        }

        private static string Show(string value)
        {
            return string.IsNullOrEmpty(value) ? "—" : value;
        }

        private static string Number(double? value)
        {
            return value.HasValue ? value.Value.ToString("F3", CultureInfo.InvariantCulture) : "—";
        }
    }
}
