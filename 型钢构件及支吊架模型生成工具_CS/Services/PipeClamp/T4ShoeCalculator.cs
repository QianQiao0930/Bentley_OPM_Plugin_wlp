using System;
using System.Collections.Generic;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>
    /// T4 高温隔热限位管托的尺寸推导与布尔布局。与 Python
    /// <c>模块/保温管夹/保温管夹_几何.py</c> 的 <c>build_layout</c> / <c>build_boolean_layout</c>
    /// 逐项对齐。纯计算，不引用 Bentley API。
    /// <para>坐标系：原点取管道轴线（管托 L 中心），X 沿管轴，Z 竖直向上；
    /// 管托底面 z = −(管半径 + H)。</para>
    /// </summary>
    internal static class T4ShoeCalculator
    {
        private static string F1(double value)
        { return value.ToString("0.#",CultureInfo.InvariantCulture); }

        /// <summary>切口坐标系方向余弦：本地点 = (x, a·c − b·s, a·s + b·c)。</summary>
        internal static void CutFrame(double splitAngleDeg,out double c,out double s)
        {
            double angle=splitAngleDeg*Math.PI/180.0;
            s=Math.Sin(angle);
            c=Math.Cos(angle);
        }

        /// <summary>由 DN 与用户输入推导整套尺寸（对应 Python build_layout）。</summary>
        internal static T4ShoeLayout BuildLayout(T4ShoeParameters parameters)
        {
            return BuildLayout(parameters,false,null,null);
        }

        /// <summary>
        /// 由 DN 与用户输入推导整套尺寸。点选到 OpenPlant 管道时（<paramref name="isPipe"/>）
        /// 优先用管道的公称直径（匹配表 1）与保温厚度，读不到才回落到面板值；
        /// 点选普通直线时**完全用面板值** —— 对应 Python 的 <c>_resolve_source</c>。
        /// </summary>
        internal static T4ShoeLayout BuildLayout(T4ShoeParameters parameters,bool isPipe,
            double? nominalMm,double? insulationMm)
        {
            if(parameters==null) throw new ArgumentNullException("parameters");
            int dn=parameters.Dn;
            if(isPipe)
            {
                int? matched=T4ShoeCatalog.MatchDn(nominalMm);
                if(matched.HasValue) dn=matched.Value;
            }
            double insulationValue=isPipe && insulationMm.HasValue
                ?insulationMm.Value
                :parameters.InsulationMm;
            var row=T4ShoeCatalog.Require(dn);
            bool simpleBase=T4ShoeCatalog.UsesSimpleBase(dn);
            double insulation=insulationValue;
            // H（管道不含保温底部 → 管托底面）由隔热层厚度 B 查表得到，面板只读显示。
            double height=T4ShoeCatalog.HeightForInsulation(insulation);
            double shoeLength=parameters.LengthMm;

            if(double.IsNaN(insulation) || double.IsInfinity(insulation) ||
                insulation<T4ShoeCatalog.MinInsulationMm)
                throw new InvalidOperationException("隔热层厚度 B="+F1(insulation)+
                    " mm 过小，要求 ≥ "+F1(T4ShoeCatalog.MinInsulationMm)+" mm。");
            if(double.IsNaN(height) || double.IsInfinity(height) ||
                height<T4ShoeCatalog.MinHeightMm)
                throw new InvalidOperationException("管托高 H="+F1(height)+
                    " mm 过小，要求 ≥ "+F1(T4ShoeCatalog.MinHeightMm)+" mm。");
            if(double.IsNaN(shoeLength) || double.IsInfinity(shoeLength) ||
                shoeLength<T4ShoeCatalog.MinShoeLengthMm)
                throw new InvalidOperationException("管托长 L="+F1(shoeLength)+
                    " mm 过小，要求 ≥ "+F1(T4ShoeCatalog.MinShoeLengthMm)+" mm。");

            double pipeRadius=row.OutsideMm/2.0;
            double insulationRadius=pipeRadius+insulation;
            double insulationOd=2.0*insulationRadius;
            double clampOuterRadius=insulationRadius+row.T3Mm;
            double baseWidth=T4ShoeCatalog.BaseWidthForInsulationOd(insulationOd);
            double shoeBottomZ=-(pipeRadius+height);
            double baseTopZ=shoeBottomZ+row.T1Mm;

            var layout=new T4ShoeLayout {
                Dn=row.Dn,Nps=row.Nps,OutsideMm=row.OutsideMm,PipeRadiusMm=pipeRadius,
                InsulationMm=insulation,InsulationRadiusMm=insulationRadius,
                InsulationOdMm=insulationOd,
                T1Mm=row.T1Mm,T2Mm=row.T2Mm,T3Mm=row.T3Mm,
                ClampOuterRadiusMm=clampOuterRadius,
                ClampWidthMm=T4ShoeCatalog.DefaultClampWidthMm,
                HeightMm=height,
                Height1Mm=height-row.T1Mm,
                ShoeLengthMm=shoeLength,ShoeBottomZMm=shoeBottomZ,
                BaseWidthMm=baseWidth,BaseTopZMm=baseTopZ,
                BoltCount=T4ShoeCatalog.BoltCount(row.Dn),
                Bolt=row.Bolt,BoltDiameterMm=row.BoltDiameterMm,
                BoltLengthMm=2.0*row.EarThicknessMm+T4ShoeCatalog.BoltExtraMm,
                EarWidthMm=row.EarWidthMm,EarHeightMm=row.EarHeightMm,
                EarThicknessMm=row.EarThicknessMm,
                BoltCenterCMm=row.BoltCenterCMm,WeldLegKMm=row.WeldLegKMm,
                PlateGapJMm=row.PlateGapJMm,
                SplitAngleDeg=T4ShoeCatalog.DefaultSplitAngleDeg,
                Code="T4",MinLengthMm=T4ShoeCatalog.MinShoeLengthMm,
                EarEndOffsetMm=T4ShoeCatalog.EarEndOffsetMm,
                SupportEndOffsetMm=T4ShoeCatalog.SupportEndOffsetMm,
                HasMiddleRib=!simpleBase && shoeLength>T4ShoeCatalog.MiddleRibLengthMm,
                TopPlateTopZMm=-clampOuterRadius
            };
            layout.Number=T4ShoeCatalog.BuildNumber(parameters.Name,row.Dn,
                parameters.TemperatureCode,height,shoeLength,parameters.MaterialCode,
                parameters.FCode);
            return layout;
        }

        /// <summary>孔心的有符号 a 坐标；同一分口两孔取相同 a，保证同轴。</summary>
        internal static double EarHoleA(double a0,double a1,double b0,double b1,
            double outerRadius,double boltCenterC,double holeDiameter,double earWidth)
        {
            double bMid=(b0+b1)/2.0;
            double contactA=Math.Sqrt(outerRadius*outerRadius-bMid*bMid);
            double side=a0+a1>0.0?1.0:-1.0;
            double holeA=side*(contactA+boltCenterC);
            double radius=holeDiameter/2.0;
            if(earWidth/2.0<=radius || !(a0<holeA-radius && holeA+radius<a1))
                throw new InvalidOperationException("孔超出耳板边界，请调整 C、孔径或耳板尺寸。");
            double nearestB=Math.Min(Math.Abs(b0),Math.Abs(b1));
            double surfaceA=Math.Sqrt(outerRadius*outerRadius-nearestB*nearestB);
            if(Math.Abs(holeA)-radius<=surfaceA)
                throw new InvalidOperationException("孔与管夹本体相交，请增大 C 或减小孔径。");
            return holeA;
        }

        /// <summary>由 layout 推导布尔建模所需的全部尺寸（对应 Python build_boolean_layout）。</summary>
        internal static T4ShoeBooleanLayout BuildBooleanLayout(T4ShoeLayout layout)
        {
            if(layout==null) throw new ArgumentNullException("layout");
            double length=layout.ShoeLengthMm;
            double outerRadius=layout.ClampOuterRadiusMm;
            double innerRadius=layout.InsulationRadiusMm;
            double gapJ=layout.PlateGapJMm;
            double earWidth=layout.EarWidthMm;
            double earHeight=layout.EarHeightMm;
            double earThickness=layout.EarThicknessMm;
            bool simpleBase=T4ShoeCatalog.UsesSimpleBase(layout.Dn);

            if(length<layout.MinLengthMm)
                throw new InvalidOperationException("管夹长度 L 必须至少 "+
                    F1(layout.MinLengthMm)+" mm。");
            if(gapJ>=2.0*innerRadius)
                throw new InvalidOperationException("承重板间隙 J 必须小于管夹内径。");

            int count=simpleBase?2:(T4ShoeCatalog.EarGroupCount!=0?T4ShoeCatalog.EarGroupCount
                :(length>T4ShoeCatalog.MiddleRibLengthMm?3:2));
            double span=length-2.0*layout.EarEndOffsetMm;
            if(layout.EarEndOffsetMm<earWidth/2.0 || span/(count-1)<=earWidth)
                throw new InvalidOperationException("耳板重叠或超出管夹端部，请增大 L 或调整端距及组数。");
            var earCenterX=new double[count];
            for(int i=0;i<count;i++) earCenterX[i]=-span/2.0+i*span/(count-1);

            var supportCenterX=new List<double>();
            if(!simpleBase)
            {
                double supportEndOffset=layout.SupportEndOffsetMm;
                if(!(layout.T2Mm/2.0<supportEndOffset && supportEndOffset<length/2.0-layout.T2Mm))
                    throw new InvalidOperationException("横向支撑端距不合理。");
                supportCenterX.Add(-length/2.0+supportEndOffset);
                if(length>T4ShoeCatalog.MiddleRibLengthMm) supportCenterX.Add(0.0);
                supportCenterX.Add(length/2.0-supportEndOffset);
            }

            double baseBottomZ=layout.ShoeBottomZMm;
            double baseTopZ=layout.BaseTopZMm;
            if(baseTopZ>=-outerRadius)
                throw new InvalidOperationException("H 不足，底板与管夹相交或没有支撑净高。");
            double overlap=T4ShoeCatalog.SupportOverlapMm;
            if(overlap>=Math.Min(layout.T3Mm,layout.T1Mm))
                throw new InvalidOperationException("搭接量必须小于承重板及底板厚度。");

            double halfSpan=simpleBase?layout.T2Mm/2.0:
                layout.BaseWidthMm/2.0-T4ShoeCatalog.SupportSideInsetMm;
            double trimRadius=outerRadius-overlap;
            if(!(halfSpan>0.0 && halfSpan<trimRadius) ||
                (!simpleBase && halfSpan<=layout.T2Mm/2.0))
                throw new InvalidOperationException("横向支撑宽度不适合当前管夹直径。");
            double supportTopZ=-Math.Sqrt(trimRadius*trimRadius-halfSpan*halfSpan);

            double bNear=gapJ/2.0+T4ShoeCatalog.EarSetbackMm;
            double bFar=bNear+earThickness;
            if(bFar>=outerRadius)
                throw new InvalidOperationException("耳板位置超出管夹外圆，请调整间隙、退让或耳板厚度。");
            double aRoot=Math.Sqrt(outerRadius*outerRadius-bFar*bFar)-T4ShoeCatalog.EarRootOverlapMm;
            if((simpleBase || layout.Code=="L2") && bNear<innerRadius)
                aRoot=Math.Max(aRoot,Math.Sqrt(innerRadius*innerRadius-bNear*bNear)+
                    T4ShoeCatalog.EarRootOverlapMm);
            if(aRoot<=0.0 || Math.Sqrt(aRoot*aRoot+bNear*bNear)<=innerRadius)
                throw new InvalidOperationException("耳板根部会穿入保温层，请调整耳板位置或搭接量。");
            if(aRoot>=Math.Sqrt(outerRadius*outerRadius-bNear*bNear))
                throw new InvalidOperationException("耳板根部无法与承重板搭接，请调整耳板位置。");
            if(earWidth>length)
                throw new InvalidOperationException("耳板轴向宽度不得超过管夹长度。");
            if(aRoot+earHeight<=Math.Sqrt(outerRadius*outerRadius-bNear*bNear))
                throw new InvalidOperationException("耳板高度不足以伸出管夹外圆。");

            var bounds=new List<double[]>();
            foreach(int radialSide in new[]{-1,1})
            {
                double a0,a1;
                if(radialSide<0) { a0=radialSide*(aRoot+earHeight); a1=radialSide*aRoot; }
                else { a0=radialSide*aRoot; a1=radialSide*(aRoot+earHeight); }
                foreach(int plateSide in new[]{-1,1})
                {
                    double b0,b1;
                    if(plateSide<0) { b0=plateSide*bFar; b1=plateSide*bNear; }
                    else { b0=plateSide*bNear; b1=plateSide*bFar; }
                    bounds.Add(new[]{a0,a1,b0,b1});
                }
            }

            double holeDiameter=layout.BoltDiameterMm+T4ShoeCatalog.HoleClearanceMm;
            var holeA=new double[bounds.Count];
            for(int i=0;i<bounds.Count;i++)
            {
                var b=bounds[i];
                holeA[i]=EarHoleA(b[0],b[1],b[2],b[3],outerRadius,
                    layout.BoltCenterCMm,holeDiameter,earWidth);
            }

            double c,s;
            CutFrame(layout.SplitAngleDeg,out c,out s);
            if(c<=0.0) throw new InvalidOperationException("切口角度不合理。");
            double maxB=Math.Abs(s)*halfSpan+c*supportTopZ;
            if(!simpleBase && maxB>=gapJ/2.0)
                throw new InvalidOperationException("当前切口角度或支撑宽度会使支撑接触上半承重板。");

            return new T4ShoeBooleanLayout {
                InnerRadiusMm=innerRadius,OuterRadiusMm=outerRadius,
                ClampLengthMm=length,CutAngleDeg=layout.SplitAngleDeg,GapJMm=gapJ,
                EarCenterXmm=earCenterX,
                SupportCenterXmm=supportCenterX.ToArray(),
                BaseBottomZMm=baseBottomZ,BaseTopZMm=baseTopZ,
                SupportHalfSpanMm=halfSpan,SupportTopZMm=supportTopZ,
                TrimRadiusMm=trimRadius,
                EarBounds=bounds.ToArray(),EarHoleA=holeA,
                HoleDiameterMm=holeDiameter,
                EarWidthMm=earWidth,EarHeightMm=earHeight,EarThicknessMm=earThickness,
                EarSetbackMm=T4ShoeCatalog.EarSetbackMm
            };
        }

        /// <summary>面板规格信息行。</summary>
        internal static string Describe(T4ShoeLayout layout,T4ShoeBooleanLayout bl)
        {
            if(layout==null) throw new ArgumentNullException("layout");
            var row=T4ShoeCatalog.Require(layout.Dn);
            string text="高温隔热限位管托：DN"+layout.Dn+"（"+layout.Nps+"，OD "+
                F1(layout.OutsideMm)+"）；隔热层 B="+F1(layout.InsulationMm)+
                "（保温层外径 D="+F1(layout.InsulationOdMm)+"）；H="+F1(layout.HeightMm)+
                "（底板顶面以上 "+F1(layout.Height1Mm)+"）；L="+F1(layout.ShoeLengthMm)+
                "；管夹外径 "+F1(layout.ClampOuterRadiusMm*2.0)+"；底板宽 W="+F1(layout.BaseWidthMm)+
                "；"+row.Bolt+"×"+layout.BoltCount+"；T1/T2/T3="+F1(layout.T1Mm)+"/"+
                F1(layout.T2Mm)+"/"+F1(layout.T3Mm)+"；允许荷载 垂直 "+F1(row.VerticalLoadKn)+
                " / 横向 "+F1(row.LateralLoadKn)+" / 轴向 "+F1(row.AxialLoadKn)+" kN。";
            if(layout.Number.Length>0) text+=" 编号 "+layout.Number+"。";
            else text+="（名称留空，不生成编号。）";
            if(bl!=null)
                text+=" 耳板 "+bl.EarCenterXmm.Length+" 组 × 4 块（板 "+
                    F1(bl.EarWidthMm)+"×"+F1(bl.EarHeightMm)+"×"+F1(bl.EarThicknessMm)+
                    "）；"+(T4ShoeCatalog.UsesSimpleBase(layout.Dn)
                        ?"底板 + 中央纵向腹板，无横向弧顶支撑。"
                        :"横向支撑 "+bl.SupportCenterXmm.Length+" 道"+
                            (layout.HasMiddleRib?"（含中间肋板）":"")+"。");
            return text;
        }

        /// <summary>构件清单条目：<c>{code, name, specification, length, quantity, unit}</c>。
        /// 条目与顺序对齐 Python <c>T4-[高温隔热限位管托].py</c> 的 <c>bom_items</c>。</summary>
        internal static string[][] ComponentItems(T4ShoeLayout layout,T4ShoeBooleanLayout bl,
            bool builtPipe,bool builtInsulation)
        {
            if(layout==null) throw new ArgumentNullException("layout");
            double clampLength=bl!=null?bl.ClampLengthMm:layout.ShoeLengthMm;
            int groups=bl!=null?bl.EarCenterXmm.Length:0;
            string lengthText=clampLength.ToString("0",CultureInfo.InvariantCulture);
            var items=new List<string[]>();
            if(builtPipe)
                items.Add(new[]{"Pipe","管道",
                    "OD"+layout.OutsideMm.ToString("0.0",CultureInfo.InvariantCulture),
                    lengthText,"1","件"});
            if(builtInsulation)
                items.Add(new[]{"Insulation","保温层","B="+F1(layout.InsulationMm),
                    lengthText,"1","件"});
            items.Add(new[]{"ClampUpper","承重板（上半）","T3="+F1(layout.T3Mm),lengthText,"1","件"});
            items.Add(new[]{"ClampLower","承重板（下半）","T3="+F1(layout.T3Mm),lengthText,"1","件"});
            items.Add(new[]{"Base","管夹底座",
                "W="+F1(layout.BaseWidthMm)+" / T2="+F1(layout.T2Mm),lengthText,"1","件"});
            items.Add(new[]{"Ear","耳板",
                F1(layout.EarWidthMm)+"×"+F1(layout.EarHeightMm)+"×"+F1(layout.EarThicknessMm),
                "0",(4*groups).ToString(CultureInfo.InvariantCulture),"块"});
            items.Add(new[]{"Bolt","螺栓",layout.Bolt,
                layout.BoltLengthMm.ToString("0",CultureInfo.InvariantCulture),
                (2*groups).ToString(CultureInfo.InvariantCulture),"套"});
            return items.ToArray();
        }
    }
}
