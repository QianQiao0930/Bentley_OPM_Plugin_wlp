using System;
using System.Collections.Generic;
using System.Globalization;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.DgnEC;
using Bentley.DgnPlatformNET.Elements;
using Bentley.EC.Persistence.Query;
using Bentley.ECObjects.Instance;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// 把一根管道元素读成 <see cref="PipeInfo"/> 纯数据（开发指南 §7）。
    /// <para>
    /// ⚠️ 本类遵守仓库既有的两条铁律（都是踩了崩溃才定下的）：
    /// </para>
    /// <list type="number">
    /// <item><description>
    /// **EC 实例绝不带出遍历**：<c>FindInstances</c> 返回的实例只在这次遍历过程中有效，
    /// 物化后留用、或返回给别的函数稍后再访问，会让 OPM 访问违例、进程直接消失（catch 不到）。
    /// 因此"查询 → 遍历 → 取值"全部写在 <see cref="ReadEc"/> 一个函数里，产出的只有纯数据。
    /// </description></item>
    /// <item><description>
    /// **不拿可能不存在的属性名去问 Bentley**：先枚举实例上实际存在的属性，只读其中存在的那些。
    /// </description></item>
    /// </list>
    /// </summary>
    internal static class PipeElementReader
    {
        /// <summary>
        /// 按 **EC 实例 ID** 读取一根管道（Move Group 沿连接关系展开成员时用）。
        /// <para>
        /// 连接关系给出的是对端**实例 ID**，不是元素 ID，所以要反过来找元素。
        /// 走 <c>IDgnECInstance.Element</c> / <c>.ModelRef</c>：DGN 的 EC 实例自带它所属的
        /// 元素与模型引用，不需要再依赖任何"实例 → 元素"的映射 API。
        /// </para>
        /// <para>取不到元素时抛出面向用户的中文异常 —— 组里有成员读不到就必须拒绝整组，
        /// 不能"跳过一个算一个"（那会留下断口）。</para>
        /// </summary>
        internal static PipeInfo ReadByInstanceId(string instanceId, PipeReadOptions readOptions,
            IOpenPlantObjectProbe objectProbe, PipeAlignLog log)
        {
            if (string.IsNullOrEmpty(instanceId))
                throw new InvalidOperationException("实例 ID 为空，无法读取该连通对象。");

            IECInstance instance = null;
            try
            {
                instance = OpenPlantObjectFactory.ResolveInstance(instanceId);
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException("按实例 ID 取 OpenPlant 实例失败：" + ex.Message, ex);
            }
            if (instance == null)
                throw new InvalidOperationException("按实例 ID 取不到 OpenPlant 实例（实例 " + instanceId + "）。");

            var dgnInstance = instance as IDgnECInstance;
            if (dgnInstance == null)
                throw new InvalidOperationException(
                    "该实例不提供所属元素（不是 IDgnECInstance），无法读取几何，因此无法确认它能否一起移动。");

            Element element = dgnInstance.Element;
            if (element == null || !element.IsValid)
                throw new InvalidOperationException("该实例没有可用的图形元素，无法读取几何。");

            ulong id = (ulong)element.ElementId;
            return Read(dgnInstance.ModelRef, id, readOptions, objectProbe, log);
        }

        /// <summary>
        /// 读取一根管道。抛出的异常消息是面向用户的中文文案。
        /// </summary>
        internal static PipeInfo Read(DgnModelRef modelRef, ulong elementId, PipeReadOptions readOptions,
            IOpenPlantObjectProbe objectProbe, PipeAlignLog log)
        {
            if (readOptions == null) readOptions = new PipeReadOptions();

            DgnModel model = LocatedElement.IsReference(modelRef)
                ? (modelRef == null ? null : modelRef.GetDgnModel())
                : Session.Instance.GetActiveDgnModel();
            if (model == null)
                throw new InvalidOperationException("没有活动模型，请先打开一个 DGN 模型。");

            var id = elementId;
            var typedId = new ElementId(ref id);
            Element element = model.FindElementById(typedId);
            if (element == null)
            {
                throw new InvalidOperationException(LocatedElement.IsReference(modelRef)
                    ? "所选元素在它所属的模型里已不存在。"
                    : "所选元素已不存在（可能已被删除或撤消）。");
            }

            PipeInfo info = new PipeInfo
            {
                ElementId = elementId,
                IsFromReference = LocatedElement.IsReference(modelRef),
                // 记下元素身份（含模型引用），App 层重新读取时原样带回。
                Source = new LocatedElement { ModelRef = modelRef, ElementId = elementId }
            };

            double uorPerMm = DgnUnitServiceFactory.UorPerMillimeter(model);
            if (uorPerMm <= 0.0)
                throw new InvalidOperationException("取不到当前模型的主单位换算系数（UorPerMeter），无法换算长度。");

            // ---- 几何：中心线 ----
            PipeGeometryResult geometry = PipeGeometryReader.Read(element, model, uorPerMm);
            info.Axis = geometry.Axis;
            info.AxisSource = geometry.Source;
            if (!string.IsNullOrEmpty(geometry.Warning)) info.ReadWarning = geometry.Warning;
            if (log != null)
            {
                log.Detail(string.Format(CultureInfo.InvariantCulture,
                    "几何：{0}；中心线 {1}",
                    geometry.Source ?? "无", geometry.Axis == null ? "取不到" : geometry.Axis.ToString()));
            }

            // ---- 可写性 ----
            try { info.IsReadOnly = model.IsReadOnly; }
            catch { info.IsReadOnly = false; }
            try { info.IsLocked = element.IsEffectivelyLocked(true, false); }
            catch { info.IsLocked = false; }

            // ---- EC 属性 ----
            ReadEc(element, info, readOptions, objectProbe, uorPerMm, log);

            if (info.IsFromReference && info.Axis != null)
                TransformReferenceAxis(info, modelRef, uorPerMm);
            return info;
        }

        private static void TransformReferenceAxis(PipeInfo info, DgnModelRef modelRef, double sourceUorPerMm)
        {
            var a = info.Axis;
            var start = new Bentley.GeometryNET.DPoint3d(a.StartXmm * sourceUorPerMm, a.StartYmm * sourceUorPerMm, a.StartZmm * sourceUorPerMm);
            var end = new Bentley.GeometryNET.DPoint3d(a.EndXmm * sourceUorPerMm, a.EndYmm * sourceUorPerMm, a.EndZmm * sourceUorPerMm);
            double scale = 1.0;
            var attachment = modelRef.AsDgnAttachment();
            if (attachment == null) throw new InvalidOperationException("参考管缺少附件坐标关系，无法取得活动模型标高。");
            int depth = 0;
            while (attachment != null)
            {
                if (++depth > 32) throw new InvalidOperationException("参考附件嵌套过深。");
                Bentley.GeometryNET.DTransform3d transform;
                attachment.GetTransformToParent(out transform, true);
                var origin = transform.MultiplyPoint(0, 0, 0);
                var x = transform.MultiplyPoint(1, 0, 0);
                var y = transform.MultiplyPoint(0, 1, 0);
                var z = transform.MultiplyPoint(0, 0, 1);
                double sx = Distance(origin, x), sy = Distance(origin, y), sz = Distance(origin, z);
                if (sx <= 0 || Math.Abs(sx-sy) > sx*1e-8 || Math.Abs(sx-sz) > sx*1e-8)
                    throw new InvalidOperationException("参考附件存在非等比缩放，无法确定管底/管顶。");
                if (Math.Abs(Dot(origin,x,y)) > sx*sx*1e-8 || Math.Abs(Dot(origin,x,z)) > sx*sx*1e-8
                    || Math.Abs(Dot(origin,y,z)) > sx*sx*1e-8)
                    throw new InvalidOperationException("参考附件存在剪切变换，无法确定圆管外表面。");
                scale *= sx;
                start = transform.MultiplyPoint(start.X, start.Y, start.Z); end = transform.MultiplyPoint(end.X, end.Y, end.Z);
                attachment = attachment.GetParentDgnAttachment();
            }
            double activeUor = DgnUnitServiceFactory.UorPerMillimeter(Bentley.MstnPlatformNET.Session.Instance.GetActiveDgnModel());
            info.Axis = new PipeAxis(start.X/activeUor, start.Y/activeUor, start.Z/activeUor, end.X/activeUor, end.Y/activeUor, end.Z/activeUor);
            double physicalScale = scale * sourceUorPerMm / activeUor;
            info.OutsideDiameterMm *= physicalScale;
            info.InsulationThicknessMm *= physicalScale;
            info.AxisSource += " → 活动模型坐标";
        }

        private static double Distance(Bentley.GeometryNET.DPoint3d a, Bentley.GeometryNET.DPoint3d b)
        { return Math.Sqrt((a.X-b.X)*(a.X-b.X)+(a.Y-b.Y)*(a.Y-b.Y)+(a.Z-b.Z)*(a.Z-b.Z)); }
        private static double Dot(Bentley.GeometryNET.DPoint3d o, Bentley.GeometryNET.DPoint3d a, Bentley.GeometryNET.DPoint3d b)
        { return (a.X-o.X)*(b.X-o.X)+(a.Y-o.Y)*(b.Y-o.Y)+(a.Z-o.Z)*(b.Z-o.Z); }

        /// <summary>
        /// 读取元素上的 EC 实例并挑选最像"管道元件"的那个。
        /// <para>**查询、遍历、取值全部留在本函数内**，产出的只有 <see cref="PipeInfo"/> 里的纯数据。</para>
        /// </summary>
        private static void ReadEc(Element element, PipeInfo info, PipeReadOptions readOptions,
            IOpenPlantObjectProbe objectProbe, double uorPerMm, PipeAlignLog log)
        {
            try
            {
                var scope = FindInstancesScope.CreateScope(element,
                    new FindInstancesScopeOption(DgnECHostType.Element));
                var query = new ECQuery();
                query.SelectClause.SelectAllProperties = true;
                ECQueryProcessAccessor.SetIn(query.ExtendedDataValueSetter, ECQueryProcessFlags.SearchAllClasses);

                using (var instances = DgnECManager.Manager.FindInstances(scope, query))
                {
                    EcSnapshot best = null;
                    int bestScore = int.MinValue;

                    foreach (IDgnECInstance instance in instances)
                    {
                        EcSnapshot candidate = Capture(instance, readOptions);
                        // DgnElementSchema 的普通单元实例不是 OpenPlant 构件，不能创建业务对象或标定长度。
                        if (candidate == null || candidate.Score < 0) continue;
                        if (candidate.Score > bestScore)
                        {
                            bestScore = candidate.Score;
                            best = candidate;
                            ApplySnapshot(candidate, info, readOptions, log);
                            if (!info.IsFromReference && objectProbe != null && !string.IsNullOrEmpty(info.InstanceId))
                            {
                                ReadTopologySafely(instance, info, readOptions, objectProbe, log);
                                if (!readOptions.SkipMoveProbe)
                                    ProbeMoveSafely(instance, info, objectProbe, uorPerMm, log);
                            }
                        }
                    }

                    if (best == null)
                    {
                        info.ReadWarning = AppendWarning(info.ReadWarning,
                            "该元素上没有 OpenPlant 管道实例（EC 类）。");
                        return;
                    }

                }
            }
            catch (Exception ex)
            {
                info.ReadWarning = AppendWarning(info.ReadWarning, "EC 读取失败：" + ex.Message);
            }
        }

        /// <summary>
        /// 在实例的生存期内读连接关系并转成纯数据。失败不抛异常，只把拓扑标成"未知"
        /// （严格模式下这会拒绝移动，而不是悄悄放行）。
        /// </summary>
        private static void ReadTopologySafely(IECInstance instance, PipeInfo info,
            PipeReadOptions readOptions, IOpenPlantObjectProbe objectProbe, PipeAlignLog log)
        {
            if (!readOptions.ReadTopology)
            {
                info.Topology = new PipeTopology { IsKnown = true };
                return;
            }

            try
            {
                info.Topology = objectProbe.ReadTopology(instance, info.InstanceId)
                    ?? new PipeTopology();
            }
            catch (Exception ex)
            {
                info.Topology = new PipeTopology
                {
                    IsKnown = false,
                    ReadWarning = "读取连接关系失败：" + ex.Message
                };
            }

            // 连通性的来源要进日志：现场出现过"明显连着邻管却报无连接"，
            // 只有把"对象来源 / 端口数 / ConnectedComponents 数"记下来才能判断
            // 到底是真没连接，还是我们没读到。
            if (log != null)
            {
                log.Detail("连接关系：" + info.Topology.Summary()
                    + (string.IsNullOrEmpty(info.Topology.ReadSource)
                        ? "" : "；" + info.Topology.ReadSource)
                    + (string.IsNullOrEmpty(info.Topology.ReadWarning)
                        ? "" : "；警告 " + info.Topology.ReadWarning));
            }
        }

        /// <summary>在实例的生存期内探测几何修改接口与单位（开发指南 §40 Phase 1 的运行时版本）。</summary>
        private static void ProbeMoveSafely(IECInstance instance, PipeInfo info,
            IOpenPlantObjectProbe objectProbe, double uorPerMm, PipeAlignLog log)
        {
            try
            {
                info.MoveProbe = objectProbe.ProbeMoveCapability(instance, info.Axis, uorPerMm)
                    ?? new PipeMoveProbe();
            }
            catch (Exception ex)
            {
                info.MoveProbe = new PipeMoveProbe { Detail = "探测失败：" + ex.Message };
            }

            if (log != null)
                log.Detail("移动能力探测：" + info.MoveProbe.Describe());
        }

        /// <summary>
        /// 一个 EC 实例的**纯数据**快照。构造完成后不再持有任何 Bentley 对象
        /// </summary>
        private sealed class EcSnapshot
        {
            internal string SchemaName;
            internal string ClassName;
            internal string InstanceId;
            internal int Score;


            internal readonly Dictionary<string, string> Text =
                new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

            internal readonly Dictionary<string, double> Numbers =
                new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);

            internal readonly List<KeyValuePair<string, string>> All =
                new List<KeyValuePair<string, string>>();

            internal double? Number(string name)
            {
                double value;
                if (Numbers.TryGetValue(name, out value)) return value;
                return null;
            }

            internal string String(string name)
            {
                string value;
                if (Text.TryGetValue(name, out value)) return value;
                return null;
            }

            internal bool Has(string name)
            {
                return Text.ContainsKey(name) || Numbers.ContainsKey(name);
            }
        }

        /// <summary>在遍历内部把一个 EC 实例读成快照。</summary>
        private static EcSnapshot Capture(IDgnECInstance instance, PipeReadOptions readOptions)
        {
            if (instance == null) return null;

            EcSnapshot snapshot = new EcSnapshot();
            try
            {
                if (instance.ClassDefinition == null) return null;
                snapshot.ClassName = instance.ClassDefinition.Name;
                snapshot.SchemaName = instance.ClassDefinition.Schema == null
                    ? null
                    : instance.ClassDefinition.Schema.Name;
            }
            catch
            {
                return null;
            }

            try { snapshot.InstanceId = instance.InstanceId; }
            catch { snapshot.InstanceId = null; }

            // 枚举**实际存在**的属性；读不到的属性只跳过，不影响其余属性。
            System.Collections.IEnumerable properties;
            try { properties = instance.ClassDefinition.Properties(true); }
            catch { return null; }

            foreach (object item in properties)
            {
                var property = item as Bentley.ECObjects.Schema.IECProperty;
                if (property == null) continue;
                string name = property.Name;
                if (string.IsNullOrEmpty(name)) continue;
                try
                {
                    CaptureValue(instance[name], name, snapshot, readOptions.KeepAllProperties);
                }
                catch
                {
                    // 单个属性不可访问不隐藏其余属性。
                }
            }

            snapshot.Score = Score(snapshot);
            return snapshot;
        }

        private static void CaptureValue(IECPropertyValue value, string name, EcSnapshot snapshot,
            bool keepAll)
        {
            if (value == null || value.IsNull) return;

            if (value.IsArray || value.IsStruct)
            {
                if (value.ContainedValues == null) return;
                foreach (IECPropertyValue child in value.ContainedValues)
                {
                    string childName = string.IsNullOrEmpty(child.AccessString) ? name : child.AccessString;
                    CaptureValue(child, childName, snapshot, keepAll);
                }
                return;
            }

            object native;
            try { native = value.NativeValue; }
            catch { native = null; }

            string text;
            if (native == null)
            {
                try { text = value.XmlStringValue; }
                catch { text = null; }
            }
            else
            {
                text = Convert.ToString(native, CultureInfo.InvariantCulture);
            }

            if (string.IsNullOrWhiteSpace(text)) return;
            snapshot.Text[name] = text;

            double number;
            if (native is double)
                snapshot.Numbers[name] = (double)native;
            else if (double.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out number))
                snapshot.Numbers[name] = number;

            if (keepAll) snapshot.All.Add(new KeyValuePair<string, string>(name, text));
        }

        /// <summary>
        /// 给实例打分，挑出"最像管道"的那个。
        /// <para>
        /// 实例资格**只由 schema 决定**：管道数据都在 <c>OpenPlant*</c> schema 里，而本仓库
        /// 支吊架插件写入的 ItemType 库（<c>PipeSupportComponents</c>）类名也以 <c>Pipe</c> 开头，
        /// 光看类名会把支吊架的设计长度当成管径。因此非 <c>OpenPlant*</c> 一律不认
        /// （与仓库 Python 版读取库同一条规则）。
        /// </para>
        /// </summary>
        private static int Score(EcSnapshot snapshot)
        {
            bool openPlantSchema = !string.IsNullOrEmpty(snapshot.SchemaName)
                && snapshot.SchemaName.StartsWith("OpenPlant", StringComparison.OrdinalIgnoreCase);
            if (!openPlantSchema) return -1000;

            int score = 10;

            // 类名的计分刻意区分"直管"与"其它管道元件"：PIPE_ELBOW / PIPE_TEE 这些类名同样以
            // PIPE 开头，只按前缀加分会让弯头拿到与直管一样的分。仍然**读得出来**
            // （不然 DEBUG 报告只会说"没有管道实例"），但校验层会按类别明确拒绝它们。
            int classNameScore = 0;
            if (!string.IsNullOrEmpty(snapshot.ClassName))
            {
                if (string.Equals(snapshot.ClassName, "PIPE", StringComparison.OrdinalIgnoreCase))
                    classNameScore = 5;
                else if (PipeConnectionClassifier.Classify(snapshot.ClassName) == PipeConnectionKind.Pipe)
                    classNameScore = 3;
            }
            score += classNameScore;

            if (snapshot.Has(PipeEcPropertyNames.OutsideDiameter)) score += 2;
            if (snapshot.Has(PipeEcPropertyNames.Length)) score += 1;
            if (!string.IsNullOrEmpty(snapshot.String(PipeEcPropertyNames.PipeNumber))) score += 1;
            return score;
        }

        private static void ApplySnapshot(EcSnapshot snapshot, PipeInfo info, PipeReadOptions readOptions,
            PipeAlignLog log)
        {
            info.SchemaName = snapshot.SchemaName;
            info.ClassName = snapshot.ClassName;
            info.InstanceId = snapshot.InstanceId;
            info.PipeNumber = snapshot.String(PipeEcPropertyNames.PipeNumber);
            info.Specification = snapshot.String(PipeEcPropertyNames.Specification);
            info.InsulationMaterial = snapshot.String(PipeEcPropertyNames.InsulationMaterial);

            if (readOptions.KeepAllProperties)
            {
                foreach (KeyValuePair<string, string> pair in snapshot.All)
                    info.AllProperties.Add(pair);
            }

            double? rawLength = snapshot.Number(PipeEcPropertyNames.Length);
            info.EcLengthRaw = rawLength;
            double? rawOutside = snapshot.Number(PipeEcPropertyNames.OutsideDiameter);
            double? rawNominal = snapshot.Number(PipeEcPropertyNames.NominalDiameter);
            if (!rawNominal.HasValue)
                rawNominal = snapshot.Number(PipeEcPropertyNames.NominalDiameterRunEnd);
            double? rawWall = snapshot.Number(PipeEcPropertyNames.WallThickness);
            double? rawInsulation = snapshot.Number(PipeEcPropertyNames.InsulationThickness);

            double geometricLengthMm = info.Axis == null ? 0.0 : info.Axis.LengthMm;
            LengthScale scale = ResolveScale(rawLength, rawOutside, rawNominal, geometricLengthMm,
                readOptions.ManualPropertyLengthScale);

            info.PropertyLengthScale = scale.Scale;
            info.PropertyLengthScaleSource = scale.SourceText;
            if (!string.IsNullOrEmpty(scale.Warning))
                info.ReadWarning = AppendWarning(info.ReadWarning, scale.Warning);

            // 诊断用：EC 变换矩阵的 Z 平移分量。名字来自**已经枚举出来的属性**，
            // 不是拿一个可能不存在的名字去问 Bentley（后者会让 OPM 崩溃）。
            info.EcTranslationZRaw = snapshot.Number(PipeEcPropertyNames.TransformationMatrixPrefix + "M11");
            try
            {
                info.EcUorPerSub = Bentley.OpenPlantModeler.SDK.Utilities.DgnUtilities
                    .GetUORPerSubForCurrentDgn();
            }
            catch
            {
                info.EcUorPerSub = 0.0;
            }

            info.OutsideDiameterMm = LengthUnitCalibrator.ToMillimeter(rawOutside, scale.Scale);
            info.NominalDiameterMm = LengthUnitCalibrator.ToMillimeter(rawNominal, scale.Scale);
            info.WallThicknessMm = LengthUnitCalibrator.ToMillimeter(rawWall, scale.Scale);
            info.InsulationThicknessMm = LengthUnitCalibrator.ToMillimeter(rawInsulation, scale.Scale);

            if (log != null)
            {
                log.Detail(string.Format(CultureInfo.InvariantCulture,
                    "EC：{0}.{1}；属性单位 {2}（{3}）；LENGTH={4}；OD={5}；DN={6}；壁厚={7}；保温={8}",
                    snapshot.SchemaName, snapshot.ClassName, scale.Scale, scale.SourceText,
                    Format(rawLength), Format(rawOutside), Format(rawNominal),
                    Format(rawWall), Format(rawInsulation)));
            }
        }

        /// <summary>
        /// 标定 EC 长度属性的单位（开发指南 §17）。
        /// 优先用「属性 LENGTH ↔ 几何长度」标定；LENGTH 不可用时退回到"用外径 / 公称直径做兜底判断"，
        /// 这样才能覆盖"单元格类管道没有长度属性"的情况。
        /// </summary>
        private static LengthScale ResolveScale(double? rawLength, double? rawOutside, double? rawNominal,
            double geometricLengthMm, double? manualScale)
        {
            LengthScale scale = LengthUnitCalibrator.Resolve(rawLength ?? 0.0, geometricLengthMm, manualScale);
            if (scale.Source != LengthScaleSource.Default || manualScale.HasValue) return scale;

            // 走到这里说明既没有手动指定、也没有标定成功。用外径 / 公称直径做一次兜底判断：
            // 工程上管径不会小于 1 mm，所以"数值 < 1"基本可以断定它是用米存的。
            double seed = rawOutside ?? rawNominal ?? 0.0;
            if (seed == 0.0) return scale;
            return LengthUnitCalibrator.Guess(seed);
        }

        private static string Format(double? value)
        {
            return value.HasValue
                ? value.Value.ToString("G", CultureInfo.InvariantCulture)
                : "—";
        }

        private static string AppendWarning(string existing, string addition)
        {
            if (string.IsNullOrEmpty(addition)) return existing;
            if (string.IsNullOrEmpty(existing)) return addition;
            return existing + " " + addition;
        }
    }
}
