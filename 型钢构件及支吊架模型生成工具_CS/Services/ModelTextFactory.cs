using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 创建按真实模型毫米尺寸显示的普通文字，不受绘图注释比例及持久文字样式影响。
    /// 所有模型标识统一走本工厂；返回离线元素，由调用方的预览/确认会话负责写入。
    /// 维护约定见 Docs/模型文字规范.md。
    /// </summary>
    internal static class ModelTextFactory
    {
        /// <summary>字高使用毫米；原点为活动模型UOR，orientation为构件局部单位轴组成的旋转矩阵。</summary>
        internal static Element Create(DgnModel model, string label, DPoint3d origin,
            DMatrix3d orientation, double heightMm, double uorPerMm, uint color)
        {
            if (model == null)
            {
                throw new InvalidOperationException("模型文字需要有效的活动模型。");
            }

            double heightUor = heightMm * uorPerMm;
            if (double.IsNaN(heightMm) || double.IsInfinity(heightMm) || heightMm <= 0 ||
                double.IsNaN(uorPerMm) || double.IsInfinity(uorPerMm) || uorPerMm <= 0 ||
                double.IsNaN(heightUor) || double.IsInfinity(heightUor) || heightUor <= 0)
            {
                throw new InvalidOperationException("模型文字的毫米字高或模型单位无效。");
            }

            // Clear associations locally, without changing model or active drawing settings.
            var properties = new TextBlockProperties(model);
            properties.RemoveTextStyle();
            properties.ClearAnnotationScale();
            properties.IsViewIndependent = false;
            var paragraph = new ParagraphProperties(model)
            {
                Justification = TextElementJustification.CenterBaseline
            };
            var run = new RunProperties(DgnFontManager.GetDefaultTrueTypeFont(),
                new DPoint2d(heightUor, heightUor), model);
            run.RemoveTextStyle();
            run.FontSize = new DPoint2d(heightUor, heightUor);
            var block = new TextBlock(properties, paragraph, run, model);
            block.AppendText(label);
            block.SetUserOrigin(origin);
            block.SetOrientation(orientation);
            Element element = TextHandlerBase.CreateElement(null, block);
            if (element == null)
            {
                throw new InvalidOperationException("模型文字生成失败：" + label);
            }

            var annotation = AnnotationHandler.GetAsAnnotationHandler(element);
            double annotationScale;
            if (annotation != null && annotation.HasAnnotationScale(out annotationScale))
            {
                throw new InvalidOperationException("模型文字仍带有注释比例，未生成固定尺寸文字：" + label);
            }

            var setter = new ElementPropertiesSetter();
            setter.SetColor(color);
            if (!setter.Apply(element))
            {
                throw new InvalidOperationException("模型文字颜色设置失败。");
            }

            return element;
        }
    }
}
