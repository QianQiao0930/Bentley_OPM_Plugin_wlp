using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Web.Script.Serialization;

namespace SteelSectionProbe
{
    /// <summary>Only the explicit plan types below can be deserialized. No CLR type names in the payload.</summary>
    internal static class NativePipeSupportRecipeCodec
    {
        private static readonly Type[] types = { typeof(NativePipeSupportRecipe), typeof(A1ClampPlan), typeof(A1ClampRow),
            typeof(U3ClampPlan), typeof(A2ClampPlan), typeof(A22ClampPlan), typeof(E1GuidePlan), typeof(E1GuideItem),
            typeof(K1LimitPlan), typeof(T4ShoeLayout), typeof(T4ShoeBooleanLayout), typeof(VerticalPipeSupportPlan),
            typeof(ElbowTrunnionPlan), typeof(ElbowTrunnionParameters), typeof(ElbowTrunnionSelection), typeof(ElbowFrame), typeof(VectorMm) };
        private static FieldInfo[] Fields(Type type) { return type.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic); }

        private sealed class Plans : JavaScriptConverter
        {
            public override IEnumerable<Type> SupportedTypes { get { return types; } }
            public override IDictionary<string, object> Serialize(object obj, JavaScriptSerializer serializer)
            { return Fields(obj.GetType()).ToDictionary(f => f.Name, f => f.GetValue(obj)); }
            public override object Deserialize(IDictionary<string, object> dictionary, Type type, JavaScriptSerializer serializer)
            {
                if (!types.Contains(type)) throw new InvalidOperationException("不支持的管夹配方类型。");
                if (type == typeof(NativePipeSupportRecipe)
                    && new[] { "Version", "Code", "CellName", "CenterMm", "Axis" }.Any(key => !dictionary.ContainsKey(key)))
                    throw new InvalidOperationException("管夹配方缺少版本或定位字段。");
                var fields = Fields(type);
                if (dictionary.Keys.Any(key => !fields.Any(f => f.Name == key))) throw new InvalidOperationException("管夹配方含未知字段。");
                var result = Activator.CreateInstance(type, true);
                foreach (var field in fields)
                {
                    object value;
                    if (dictionary.TryGetValue(field.Name, out value))
                        field.SetValue(result, value == null ? null : serializer.ConvertToType(value, field.FieldType));
                }
                return result;
            }
        }

        private static JavaScriptSerializer Serializer()
        {
            var serializer = new JavaScriptSerializer { MaxJsonLength = 131072, RecursionLimit = 32 };
            serializer.RegisterConverters(new[] { new Plans() });
            return serializer;
        }

        private static void Values(object value, int depth)
        {
            if (value == null) return;
            if (depth > 16) throw new InvalidOperationException("管夹配方嵌套过深。");
            if (value is double)
            {
                if (double.IsNaN((double)value) || double.IsInfinity((double)value)) throw new InvalidOperationException("管夹配方尺寸不是有限数值。");
                return;
            }
            if (value is string) { if (((string)value).Length > 4096) throw new InvalidOperationException("管夹配方文字过长。"); return; }
            var array = value as Array;
            if (array != null)
            {
                if (array.Length > 1024) throw new InvalidOperationException("管夹配方数组过长。");
                foreach (object item in array) Values(item, depth + 1);
            }
            else if (types.Contains(value.GetType())) foreach (var field in Fields(value.GetType())) Values(field.GetValue(value), depth + 1);
            else if (!value.GetType().IsPrimitive && !value.GetType().IsEnum) throw new InvalidOperationException("不支持的管夹配方数据。");
        }

        internal static string Encode(NativePipeSupportRecipe recipe)
        {
            if (recipe == null) throw new InvalidOperationException("管夹配方为空。");
            Values(recipe, 0); recipe.Validate();
            return Serializer().Serialize(recipe);
        }

        internal static NativePipeSupportRecipe Decode(string json)
        {
            if (string.IsNullOrWhiteSpace(json) || json.Length > 131072) throw new InvalidOperationException("管夹配方缺失或过长。");
            var recipe = Serializer().Deserialize<NativePipeSupportRecipe>(json);
            if (recipe == null) throw new InvalidOperationException("管夹配方为空。");
            Values(recipe, 0); recipe.Validate(); return recipe;
        }
    }
}
