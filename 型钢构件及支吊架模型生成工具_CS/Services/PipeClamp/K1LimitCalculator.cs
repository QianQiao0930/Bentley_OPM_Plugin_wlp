using System;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>
    /// K1 不保温管限位架的尺寸与坐标架推导。与 Python
    /// <c>模块/K1限位架/K1限位架_几何.py</c> 的 <c>flange_seat</c> / <c>member_frame</c> /
    /// <c>plate_box</c> / <c>build_layout</c> 逐项对齐。纯计算，不引用 Bentley API。
    /// </summary>
    internal static class K1LimitCalculator
    {
        /// <summary>管轴水平夹角上限（°）。</summary>
        internal const double MaxSlopeDegrees=5.0;

        private static string F1(double value)
        { return value.ToString("0.#",CultureInfo.InvariantCulture); }

        private static double[] Neg(double[] v)
        { return new[]{-v[0],-v[1],-v[2]}; }

        private static double Dot(double[] a,double[] b)
        { return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]; }

        /// <summary>
        /// 由管轴方向给出 <c>(pipeDir, perp)</c>：均为水平单位向量，且 pipeDir × perp = +Z。
        /// 管道与水平面夹角超过 5° 时抛错（K1 仅适用于水平或微倾管道）。
        /// </summary>
        internal static void HorizontalFrame(double axisX,double axisY,double axisZ,
            out double[] pipeDir,out double[] perp)
        {
            double length=Math.Sqrt(axisX*axisX+axisY*axisY+axisZ*axisZ);
            if(length<=1.0e-12) throw new InvalidOperationException("管道轴线长度为零，无法定位。");
            double nx=axisX/length,ny=axisY/length,nz=axisZ/length;
            double horizontal=Math.Sqrt(nx*nx+ny*ny);
            if(horizontal<=1.0e-9)
                throw new InvalidOperationException("管道接近竖直，K1 限位架仅适用于水平（或微倾）管道。");
            if(Math.Abs(nz)>Math.Sin(MaxSlopeDegrees*Math.PI/180.0))
                throw new InvalidOperationException("管道与水平面夹角超过 "+
                    MaxSlopeDegrees.ToString("0",CultureInfo.InvariantCulture)+
                    "°，K1 限位架仅适用于水平管道。");
            pipeDir=new[]{nx/horizontal,ny/horizontal,0.0};
            // cross((0,0,1), pipeDir)
            perp=new[]{-pipeDir[1],pipeDir[0],0.0};
        }

        /// <summary>
        /// 法兰座尺寸。
        /// <paramref name="contactOffsetMm"/>：管道骑在两翼缘端面上时，**管轴 → 翼缘端面**
        /// 的高差 = sqrt((OD/2)² − (b/2)²)，其中 b = 型钢高度 − 2×翼缘厚（两翼缘净距）。
        /// <paramref name="gapMm"/>：钢板顶面与翼缘端面的间距，以 OD 为两腰、b 为底边作等腰
        /// 三角形，底边到顶点的高 h = sqrt(OD² − (b/2)²)，则 gap = 2×(OD − h)。
        /// 子项 A（无底板）返回 <c>(OD/2, 0)</c>。
        /// </summary>
        internal static void FlangeSeat(K1LimitSubitem item,double outsideMm,
            out double contactOffsetMm,out double gapMm)
        {
            if(item==null) throw new ArgumentNullException("item");
            if(item.IsHalfT)
            {
                contactOffsetMm=outsideMm/2.0;
                gapMm=0.0;
                return;
            }
            double baseWidth=item.CrossHeightMm-2.0*item.FlangeThicknessMm;
            double half=baseWidth/2.0;
            double radius=outsideMm/2.0;
            if(half<=0.0 || half>=radius)
                throw new InvalidOperationException("管外径 OD="+F1(outsideMm)+" 与两翼缘净距 b="+
                    F1(baseWidth)+" 不匹配（管子骑不住）。");
            contactOffsetMm=Math.Sqrt(radius*radius-half*half);
            double triangleHeight=Math.Sqrt(outsideMm*outsideMm-half*half);
            gapMm=Math.Max(0.0,2.0*(outsideMm-triangleHeight));
        }

        /// <summary>
        /// 单根限位块的坐标架：<c>originMm</c>、三个单位轴与沿 axisZ 的拉伸长度。
        /// 子项 A 的截面在水平面（axisX = 管轴、axisY = 垂直管轴、axisZ = 竖直）；
        /// 子项 B/C 的截面在竖直面（axisX = ±竖直、axisY = 垂直管轴、axisZ = ±管轴）。
        /// </summary>
        internal static void MemberFrame(K1LimitSubitem item,int side,double[] centerMm,
            double existingWidthMm,double outsideMm,double[] pipeDir,
            out double[] originMm,out double[] axisX,out double[] axisY,out double[] axisZ,
            out double lengthMm)
        {
            if(item==null) throw new ArgumentNullException("item");
            if(pipeDir==null || pipeDir.Length<3) throw new ArgumentNullException("pipeDir");
            double[] perp={-pipeDir[1],pipeDir[0],0.0};
            double cx=centerMm[0],cy=centerMm[1],cz=centerMm[2];
            double pipeBottom=cz-outsideMm/2.0;
            double width=existingWidthMm;
            double s=side>=0?1.0:-1.0;

            if(item.IsHalfT)
            {
                double height=item.HeightMm;
                double uInner=s*width/2.0;
                originMm=new[]{cx+uInner*pipeDir[0],cy+uInner*pipeDir[1],pipeBottom-height};
                axisX=s>0?pipeDir:Neg(pipeDir);
                axisY=s>0?perp:Neg(perp);
                axisZ=new[]{0.0,0.0,1.0};
                lengthMm=height;
                return;
            }

            double length=item.LengthMm;
            double crossWidth=item.CrossWidthMm;
            double plateThickness=item.Plate!=null?item.Plate[2]:0.0;
            double contact,gap;
            FlangeSeat(item,outsideMm,out contact,out gap);
            double flangeTop=cz-contact;
            double innerBeam=s*(width/2.0+plateThickness);
            originMm=new[]{cx+innerBeam*pipeDir[0],cy+innerBeam*pipeDir[1],
                flangeTop-crossWidth/2.0};
            if(s>0)
            {
                axisX=new[]{0.0,0.0,-1.0};
                axisY=perp;
                axisZ=pipeDir;
            }
            else
            {
                axisX=new[]{0.0,0.0,1.0};
                axisY=perp;
                axisZ=Neg(pipeDir);
            }
            lengthMm=length;
        }

        /// <summary>
        /// 底板局部范围 <c>[u0, u1, v0, v1, z0, z1]</c>（u 沿管轴、v 垂直管轴、z 绝对标高）；
        /// 无底板时返回 null。底板焊在型钢朝已有钢构那一端的**截面**上（垂直于管轴的竖直板）。
        /// </summary>
        internal static double[] PlateBox(K1LimitSubitem item,int side,double[] centerMm,
            double existingWidthMm,double outsideMm,double[] pipeDir)
        {
            if(item==null || item.Plate==null) return null;
            double cz=centerMm[2];
            double width=existingWidthMm;
            double sideLength=item.Plate[0];
            double thickness=item.Plate[2];
            double contact,gap;
            FlangeSeat(item,outsideMm,out contact,out gap);
            double plateTop=(cz-contact)-gap;
            double s=side>=0?1.0:-1.0;
            double u0,u1;
            if(s>0) { u0=width/2.0; u1=width/2.0+thickness; }
            else { u0=-(width/2.0+thickness); u1=-width/2.0; }
            return new[]{u0,u1,-sideLength/2.0,sideLength/2.0,plateTop-sideLength,plateTop};
        }

        /// <summary>
        /// 解析面板参数与所选元素信息，得到编号、规格与接触高差。
        /// <paramref name="isPipe"/> 为真且读到公称直径时按其匹配 DN 与子项。
        /// </summary>
        internal static K1LimitPlan Calculate(K1LimitParameters parameters,bool isPipe,
            double? nominalMm)
        {
            if(parameters==null) throw new ArgumentNullException("parameters");
            int dn=parameters.Dn;
            if(isPipe && nominalMm.HasValue)
            {
                int? matched=K1LimitCatalog.MatchDn(nominalMm.Value);
                if(matched.HasValue) dn=matched.Value;
            }
            string key=K1LimitCatalog.IsKnownKey(parameters.SubitemKey)
                ?K1LimitCatalog.Require(parameters.SubitemKey).Key
                :K1LimitCatalog.SubitemForDn(dn);
            return Calculate(dn,key,parameters.ExistingWidthMm,parameters.Material);
        }

        internal static K1LimitPlan Calculate(int dn,string subitemKey,double existingWidthMm,
            string material)
        {
            var item=K1LimitCatalog.Require(subitemKey);
            double outsideMm=K1LimitCatalog.Od(dn);
            foreach(double value in new[]{existingWidthMm,outsideMm})
                if(double.IsNaN(value) || double.IsInfinity(value) || value<=0.0)
                    throw new InvalidOperationException("尺寸参数必须是有限的正数。");
            double contact,gap;
            FlangeSeat(item,outsideMm,out contact,out gap);
            return new K1LimitPlan {
                Dn=dn,SubitemKey=item.Key,OutsideMm=outsideMm,Nps=K1LimitCatalog.Nps(dn),
                ExistingWidthMm=existingWidthMm,SizeMm=item.MainSizeMm,
                SizeLabel=item.MainSizeLabel,
                Plate=item.Plate==null?null:(double[])item.Plate.Clone(),
                ContactOffsetMm=contact,PlateGapMm=gap,
                Number=K1LimitCatalog.BuildNumber(item.Key,dn),
                Specification=item.Specification,
                Material=string.IsNullOrEmpty(material)?K1LimitCatalog.DefaultMaterial:material,
                SupportType=K1LimitCatalog.SupportType,
                SupportCode=K1LimitCatalog.SupportCode,
                CellName=K1LimitCatalog.CellName
            };
        }

        /// <summary>面板规格信息行。</summary>
        internal static string Describe(K1LimitPlan plan)
        {
            if(plan==null) throw new ArgumentNullException("plan");
            string text="K1 限位架：DN"+plan.Dn+"（"+plan.Nps+"，OD "+F1(plan.OutsideMm)+
                "）；子项 "+plan.SubitemKey+"（"+plan.Specification+"）；"+plan.SizeLabel+" "+
                F1(plan.SizeMm)+"；两限位块间距 "+F1(plan.ExistingWidthMm)+
                "（已有钢构宽）；编号 "+plan.Number+"。";
            if(plan.Plate!=null)
                text+=" 底板 "+F1(plan.Plate[0])+"×"+F1(plan.Plate[1])+"×"+F1(plan.Plate[2])+
                    " ×2，顶面比翼缘端面低 "+F1(plan.PlateGapMm)+"。";
            return text;
        }

        /// <summary>构件清单（供 ItemType 写入）。</summary>
        internal static string[][] ComponentItems(K1LimitPlan plan)
        {
            var members=new System.Collections.Generic.List<string[]>();
            members.Add(new[]{"Block","限位块（型钢）",plan.Specification,
                plan.SizeMm.ToString("0",CultureInfo.InvariantCulture),"2","件"});
            if(plan.Plate!=null)
                members.Add(new[]{"BasePlate","底板",
                    F1(plan.Plate[0])+"×"+F1(plan.Plate[1])+"×"+F1(plan.Plate[2]),
                    plan.Plate[2].ToString("0",CultureInfo.InvariantCulture),"2","块"});
            return members.ToArray();
        }
    }
}
