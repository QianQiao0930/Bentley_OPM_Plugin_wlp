using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    internal static class LineCoordinateEditor
    {
        internal static LineCoordinateSelection Apply(LineCoordinateSelection selection, LineCoordinates target)
        {
            if (!LicenseService.IsActivated) throw new InvalidOperationException("请先激活软件。");
            if (selection == null) throw new InvalidOperationException("请先点取直线段。");
            if (TransactionManager.IsUndoInProgress) throw new InvalidOperationException("正在撤销或重做，请稍后操作。");
            using (var original = LineCoordinateReader.FindWritable(selection.Model, selection.ElementId))
            {
                double scale = selection.Model.GetModelInfo().UorPerMeter / 1000.0;
                if (scale != selection.UorPerMm || selection.Model.Is3d != selection.Is3d)
                    throw new InvalidOperationException("模型单位或维度已改变，请重新点取。");
                var current = LineCoordinateReader.ReadCoordinates(original, scale);
                if (!LineCoordinateCalculator.Same(current, selection.Coordinates, 0))
                    throw new InvalidOperationException("所选线段已被其他操作修改，请重新读取后再编辑。");
                LineCoordinateCalculator.Validate(target, selection.Is3d, 1.0 / scale);
                if (LineCoordinateCalculator.Same(current, target, 0))
                    throw new InvalidOperationException("坐标没有变化，无需应用。");
                DPoint3d originalStart, originalEnd;
                LineCoordinateReader.ReadEndpoints(original, out originalStart, out originalEnd);
                var start = Point(target.Start, current.Start, originalStart, scale);
                var end = Point(target.End, current.End, originalEnd, scale);
                var path = new CurveVector(CurveVector.BoundaryType.Open);
                path.Add(CurvePrimitive.CreateLine(new DSegment3d(start, end)));
                // 原生编辑接口只改曲线几何，保留原 ID、样式和附加属性，绝不删除后新建。
                using (var edit = CurvePathEdit.GetAsCurvePathEdit(original))
                {
                    if (edit == null || edit.SetCurveVector(path) != BentleyStatus.Success)
                        throw new InvalidOperationException("无法修改线段几何，原线段未写入修改。");
                    if (!TransactionManager.IsActive) TransactionManager.Activate();
                    if (!TransactionManager.IsActive) throw new InvalidOperationException("无法启用模型撤销记录。");
                    TransactionManager.CloseCurrentTransaction(true);
                    var mark = TransactionManager.CurrentTransactionPosition;
                    try
                    {
                        var status = edit.ReplaceInModel(original);
                        if (status != StatusInt.Success) throw new InvalidOperationException("线段写入失败：" + status);
                        var result = LineCoordinateReader.Read(new LocatedElement { ModelRef = selection.Model, ElementId = selection.ElementId });
                        if (!LineCoordinateCalculator.Same(result.Coordinates, target, 1.0 / scale))
                            throw new InvalidOperationException("写入后的坐标与输入不一致。");
                        // 单次 Replace 封为独立事务，支持宿主 Ctrl+Z/Redo。
                        TransactionManager.CloseCurrentTransaction(true);
                        return result;
                    }
                    catch (Exception error)
                    {
                        var rollback = TransactionManager.CancelToPosition(mark, false);
                        if (rollback != StatusInt.Success)
                            throw new InvalidOperationException(error.Message + "；回退失败：" + rollback + "，请检查模型。", error);
                        throw;
                    }
                }
            }
        }

        private static DPoint3d Point(LineCoordinatePoint point, LineCoordinatePoint current, DPoint3d original, double scale)
        {
            // 未编辑的轴直接保留原始 UOR，避免毫米往返引入浮点舍入。
            double x = point.X == current.X ? original.X : point.X * scale;
            double y = point.Y == current.Y ? original.Y : point.Y * scale;
            double z = point.Z == current.Z ? original.Z : point.Z * scale;
            if (!LineCoordinateCalculator.Finite(x) || !LineCoordinateCalculator.Finite(y) || !LineCoordinateCalculator.Finite(z))
                throw new InvalidOperationException("坐标超出模型存储范围。");
            return DPoint3d.FromXYZ(x, y, z);
        }
    }
}
