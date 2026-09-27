using System;
using System.Linq;

namespace SteelSectionProbe
{
    /// <summary>管夹种类。四种管夹共用“点选管道 / 直线 → 在点击处沿轴线放置”的操作方式。</summary>
    internal enum PipeClampKind
    {
        A2StandardTwoBolt=0,
        E1Guide=1,
        K1Limit=2,
        T4Insulated=3
    }

    /// <summary>一种管夹的元数据：下拉标签、清单类型名与 ASCII 代号、组合单元名。</summary>
    internal sealed class PipeClampType
    {
        internal PipeClampKind Kind;
        /// <summary>图纸编号前缀（A2 / E1 / K1 / T4）。</summary>
        internal string Code;
        /// <summary>下拉框里的标签。</summary>
        internal string Label;
        /// <summary>写入 <c>PipeSupportComponents</c> 的中文类型名。</summary>
        internal string SupportType;
        /// <summary>ASCII 代号，只用于 ItemType 命名。</summary>
        internal string SupportCode;
        internal string CellName;
        /// <summary>面板顶部的说明文字。</summary>
        internal string Hint;
    }

    /// <summary>
    /// 四种管夹的注册表。首页只有一个“放置管夹”入口，进入后由本表驱动下拉切换。
    /// 纯数据，不引用 Bentley API。
    /// </summary>
    internal static class PipeClampCatalog
    {
        private static readonly PipeClampType[] Types={
            new PipeClampType {
                Kind=PipeClampKind.A2StandardTwoBolt,Code="A2",
                Label="A2 标准型 2 螺栓管夹（DN15~750）",
                SupportType="A2-[标准型2螺栓管夹]",SupportCode="STD_2BOLT_CLAMP",
                CellName="STD_2BOLT_CLAMP",
                Hint="点选管道或直线，在点击处沿其轴线生成管夹。管道自动读公称直径与保温厚度；"+
                    "选中直线或读不到管道属性时，改用面板输入的管径与保温厚度建模。" },
            new PipeClampType {
                Kind=PipeClampKind.E1Guide,Code="E1",
                Label="E1 不保温管导向架（DN15~900）",
                SupportType=E1GuideCatalog.SupportType,SupportCode=E1GuideCatalog.SupportCode,
                CellName="E1_RACK",
                Hint="点选管道或直线，在点击处沿其轴线生成两根镜像竖直构件。点取 OpenPlant 直管时"+
                    "读取其 EC 管径；点取普通直线或多段线时使用页面所选 DN。" },
            new PipeClampType {
                Kind=PipeClampKind.K1Limit,Code="K1",
                Label="K1 不保温管限位架（1/2″~36″）",
                SupportType=K1LimitCatalog.SupportType,SupportCode=K1LimitCatalog.SupportCode,
                CellName=K1LimitCatalog.CellName,
                Hint="点选一根水平管道或直线，在点击处生成两组一前一后的限位块，中间夹住已有钢构"+
                    "（间距 W 由面板输入）。子项按 DN 自动选，可改。" },
            new PipeClampType {
                Kind=PipeClampKind.T4Insulated,Code="T4",
                Label="T4 高温隔热限位管托（DN80~600）",
                SupportType=T4ShoeCatalog.SupportType,SupportCode=T4ShoeCatalog.SupportCode,
                CellName=T4ShoeCatalog.CellName,
                Hint="点选一条管道轴线，在点击处生成高温隔热限位管托：上下两片包保温层的筒形承重板"+
                    "（对开 45°）与弧顶支撑底座。H 由隔热层厚度 B 查表。" }
        };

        internal static PipeClampType[] All { get { return Types; } }

        internal static PipeClampType Type(PipeClampKind kind)
        {
            var found=Types.FirstOrDefault(x=>x.Kind==kind);
            if(found==null) throw new InvalidOperationException("未知的管夹种类。");
            return found;
        }

        internal static PipeClampType Default { get { return Types[0]; } }
    }
}
