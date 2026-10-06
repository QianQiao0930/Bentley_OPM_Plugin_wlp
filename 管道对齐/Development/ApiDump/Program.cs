// ApiDump —— 只读元数据转储工具（不加载、不执行目标程序集）
//
// 用途：在开发期确认 Bentley 程序集的真实类型与方法签名，避免靠猜写代码。
// 用法：
//   ApiDump <assembly.dll> [类型名过滤正则] [--members] [--all]
//
// 输出：类型全名（含基类 / 接口 / 种类）以及公开成员签名。
// 说明：用 System.Reflection.Metadata 读取元数据，不做 Assembly.LoadFrom，
//       因此不会受安全策略拦截，也不需要在 Bentley 宿主里运行。

using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Text;

namespace ApiDump
{
    internal sealed class TypeNameProvider : ISignatureTypeProvider<string, object>
    {
        private readonly MetadataReader _reader;

        public TypeNameProvider(MetadataReader reader)
        {
            _reader = reader;
        }

        public string GetArrayType(string elementType, ArrayShape shape)
        {
            return elementType + "[" + new string(',', Math.Max(0, shape.Rank - 1)) + "]";
        }

        public string GetByReferenceType(string elementType) { return elementType + "&"; }

        public string GetFunctionPointerType(MethodSignature<string> signature) { return "fnptr"; }

        public string GetGenericInstantiation(string genericType, ImmutableArray<string> typeArguments)
        {
            return genericType + "<" + string.Join(", ", typeArguments) + ">";
        }

        public string GetGenericMethodParameter(object genericContext, int index) { return "!!" + index; }

        public string GetGenericTypeParameter(object genericContext, int index) { return "!" + index; }

        public string GetModifiedType(string modifier, string unmodifiedType, bool isRequired)
        {
            return (isRequired ? "modreq(" : "modopt(") + modifier + ") " + unmodifiedType;
        }

        public string GetPinnedType(string elementType) { return elementType; }

        public string GetPointerType(string elementType) { return elementType + "*"; }

        public string GetPrimitiveType(PrimitiveTypeCode typeCode)
        {
            switch (typeCode)
            {
                case PrimitiveTypeCode.Boolean: return "bool";
                case PrimitiveTypeCode.Byte: return "byte";
                case PrimitiveTypeCode.SByte: return "sbyte";
                case PrimitiveTypeCode.Char: return "char";
                case PrimitiveTypeCode.Int16: return "short";
                case PrimitiveTypeCode.UInt16: return "ushort";
                case PrimitiveTypeCode.Int32: return "int";
                case PrimitiveTypeCode.UInt32: return "uint";
                case PrimitiveTypeCode.Int64: return "long";
                case PrimitiveTypeCode.UInt64: return "ulong";
                case PrimitiveTypeCode.Single: return "float";
                case PrimitiveTypeCode.Double: return "double";
                case PrimitiveTypeCode.String: return "string";
                case PrimitiveTypeCode.Object: return "object";
                case PrimitiveTypeCode.Void: return "void";
                case PrimitiveTypeCode.IntPtr: return "IntPtr";
                case PrimitiveTypeCode.UIntPtr: return "UIntPtr";
                case PrimitiveTypeCode.TypedReference: return "TypedReference";
                default: return typeCode.ToString();
            }
        }

        public string GetSZArrayType(string elementType) { return elementType + "[]"; }

        public string GetTypeFromDefinition(MetadataReader reader, TypeDefinitionHandle handle, byte rawTypeKind)
        {
            return Dump.TypeShortName(reader, handle);
        }

        public string GetTypeFromReference(MetadataReader reader, TypeReferenceHandle handle, byte rawTypeKind)
        {
            TypeReference tr = reader.GetTypeReference(handle);
            string ns = reader.GetString(tr.Namespace);
            string n = reader.GetString(tr.Name);
            return string.IsNullOrEmpty(ns) ? n : ns + "." + n;
        }

        public string GetTypeFromSpecification(MetadataReader reader, object genericContext, TypeSpecificationHandle handle, byte rawTypeKind)
        {
            return reader.GetTypeSpecification(handle).DecodeSignature(this, genericContext);
        }
    }

    internal static class Dump
    {
        public static string TypeShortName(MetadataReader reader, TypeDefinitionHandle handle)
        {
            TypeDefinition td = reader.GetTypeDefinition(handle);
            string ns = reader.GetString(td.Namespace);
            string n = reader.GetString(td.Name);
            return string.IsNullOrEmpty(ns) ? n : ns + "." + n;
        }

        private static string TypeFullName(MetadataReader reader, TypeDefinitionHandle handle)
        {
            TypeDefinition td = reader.GetTypeDefinition(handle);
            string ns = reader.GetString(td.Namespace);
            string n = reader.GetString(td.Name);
            string outer = string.Empty;
            TypeDefinitionHandle declaring = td.GetDeclaringType();
            if (!declaring.IsNil)
            {
                outer = TypeFullName(reader, declaring) + "+";
                ns = string.Empty;
            }
            return outer + (string.IsNullOrEmpty(ns) ? n : ns + "." + n);
        }

        private static string EntityTypeName(MetadataReader reader, EntityHandle handle, TypeNameProvider provider)
        {
            if (handle.IsNil) return "?";
            switch (handle.Kind)
            {
                case HandleKind.TypeDefinition: return TypeFullName(reader, (TypeDefinitionHandle)handle);
                case HandleKind.TypeReference:
                    {
                        TypeReference tr = reader.GetTypeReference((TypeReferenceHandle)handle);
                        string ns = reader.GetString(tr.Namespace);
                        string n = reader.GetString(tr.Name);
                        return string.IsNullOrEmpty(ns) ? n : ns + "." + n;
                    }
                case HandleKind.TypeSpecification:
                    return reader.GetTypeSpecification((TypeSpecificationHandle)handle).DecodeSignature(provider, null);
                default: return "?";
            }
        }

        private static string ReferenceAssemblyScope(MetadataReader reader, EntityHandle handle)
        {
            if (handle.IsNil) return "-";
            try
            {
                if (handle.Kind == HandleKind.TypeReference)
                {
                    TypeReference tr = reader.GetTypeReference((TypeReferenceHandle)handle);
                    if (tr.ResolutionScope.Kind == HandleKind.AssemblyReference)
                    {
                        AssemblyReference ar = reader.GetAssemblyReference((AssemblyReferenceHandle)tr.ResolutionScope);
                        return reader.GetString(ar.Name);
                    }
                }
                if (handle.Kind == HandleKind.TypeDefinition)
                {
                    TypeDefinition td = reader.GetTypeDefinition((TypeDefinitionHandle)handle);
                    return reader.GetString(reader.GetAssemblyDefinition().Name);
                }
            }
            catch { }
            return "-";
        }

        private static string Visibility(TypeAttributes attrs)
        {
            switch (attrs & TypeAttributes.VisibilityMask)
            {
                case TypeAttributes.Public: return "public";
                case TypeAttributes.NotPublic: return "internal";
                case TypeAttributes.NestedPublic: return "public";
                case TypeAttributes.NestedPrivate: return "private";
                case TypeAttributes.NestedFamily: return "protected";
                case TypeAttributes.NestedAssembly: return "internal";
                case TypeAttributes.NestedFamORAssem: return "protected internal";
                default: return "?";
            }
        }

        private static bool IsEnum(MetadataReader reader, TypeDefinition td)
        {
            if (td.BaseType.IsNil) return false;
            string b = EntityTypeName(reader, td.BaseType, new TypeNameProvider(reader));
            return b == "System.Enum";
        }

        private static bool IsValueType(MetadataReader reader, TypeDefinition td)
        {
            if (td.BaseType.IsNil) return false;
            string b = EntityTypeName(reader, td.BaseType, new TypeNameProvider(reader));
            return b == "System.ValueType";
        }

        private static string ParameterList(MetadataReader reader, MethodDefinition md, MethodSignature<string> sig)
        {
            List<string> parts = new List<string>();
            ImmutableArray<string> types = sig.ParameterTypes;
            int index = 0;
            foreach (ParameterHandle ph in md.GetParameters())
            {
                Parameter p = reader.GetParameter(ph);
                if (p.SequenceNumber == 0) continue;
                int slot = p.SequenceNumber - 1;
                string typeName = slot >= 0 && slot < types.Length ? types[slot] : "?";
                string name = reader.GetString(p.Name);
                string modifier = string.Empty;
                if ((p.Attributes & ParameterAttributes.Out) != 0) modifier = "out ";
                else if (typeName.EndsWith("&")) modifier = "ref ";
                parts.Add(modifier + typeName + " " + name);
                index++;
            }
            // 没有 Parameter 行（例如无名字）时退回签名里的类型列表
            if (parts.Count == 0 && types.Length > 0)
            {
                foreach (string t in types) parts.Add(t);
            }
            return string.Join(", ", parts);
        }

        public static void Run(string assemblyPath, string filter, bool members, bool includeNonPublic)
        {
            using (FileStream fs = File.OpenRead(assemblyPath))
            using (PEReader pe = new PEReader(fs))
            {
                MetadataReader reader = pe.GetMetadataReader();
                TypeNameProvider provider = new TypeNameProvider(reader);

                Console.WriteLine("### ASSEMBLY: " + assemblyPath);
                Console.WriteLine("### TYPES: " + reader.TypeDefinitions.Count);

                System.Text.RegularExpressions.Regex rx = string.IsNullOrEmpty(filter)
                    ? null
                    : new System.Text.RegularExpressions.Regex(filter, System.Text.RegularExpressions.RegexOptions.IgnoreCase);

                foreach (TypeDefinitionHandle tdh in reader.TypeDefinitions)
                {
                    TypeDefinition td = reader.GetTypeDefinition(tdh);
                    string full = TypeFullName(reader, tdh);
                    if (rx != null && !rx.IsMatch(full)) continue;

                    string vis = Visibility(td.Attributes);
                    if (!includeNonPublic && vis != "public") continue;

                    string baseName = td.BaseType.IsNil ? "-" : EntityTypeName(reader, td.BaseType, provider);
                    string baseScope = td.BaseType.IsNil ? "-" : ReferenceAssemblyScope(reader, td.BaseType);

                    List<string> ifaces = new List<string>();
                    foreach (InterfaceImplementationHandle ih in td.GetInterfaceImplementations())
                    {
                        InterfaceImplementation ii = reader.GetInterfaceImplementation(ih);
                        ifaces.Add(EntityTypeName(reader, ii.Interface, provider));
                    }

                    string kind = (td.Attributes & TypeAttributes.Interface) != 0
                        ? "interface"
                        : (IsEnum(reader, td) ? "enum" : (IsValueType(reader, td) ? "struct" : "class"));

                    Console.WriteLine();
                    Console.WriteLine("TYPE " + vis + " " + kind + " " + full);
                    if (baseName != "-") Console.WriteLine("  base: " + baseName + "   [asm: " + baseScope + "]");
                    if (ifaces.Count > 0) Console.WriteLine("  impl: " + string.Join(", ", ifaces));

                    if (!members) continue;

                    foreach (EventDefinitionHandle eh in td.GetEvents())
                    {
                        EventDefinition ed = reader.GetEventDefinition(eh);
                        string t = ed.Type.IsNil ? "?" : EntityTypeName(reader, ed.Type, provider);
                        Console.WriteLine("  event " + t + " " + reader.GetString(ed.Name));
                    }

                    foreach (PropertyDefinitionHandle phd in td.GetProperties())
                    {
                        PropertyDefinition pd = reader.GetPropertyDefinition(phd);
                        MethodSignature<string> sig = pd.DecodeSignature(provider, null);
                        PropertyAccessors acc = pd.GetAccessors();
                        List<string> accessors = new List<string>();
                        if (!acc.Getter.IsNil) accessors.Add("get");
                        if (!acc.Setter.IsNil) accessors.Add("set");
                        Console.WriteLine("  prop " + sig.ReturnType + " " + reader.GetString(pd.Name) + " { " + string.Join("; ", accessors) + " }");
                    }

                    foreach (FieldDefinitionHandle fhd in td.GetFields())
                    {
                        FieldDefinition fd = reader.GetFieldDefinition(fhd);
                        if (!includeNonPublic && (fd.Attributes & FieldAttributes.Public) == 0) continue;
                        string t;
                        try { t = fd.DecodeSignature(provider, null); } catch { t = "?"; }
                        Console.WriteLine("  field " + t + " " + reader.GetString(fd.Name));
                    }

                    foreach (MethodDefinitionHandle mhd in td.GetMethods())
                    {
                        MethodDefinition md = reader.GetMethodDefinition(mhd);
                        MethodAttributes ma = md.Attributes;
                        bool pub = (ma & MethodAttributes.Public) != 0;
                        if (!includeNonPublic && !pub) continue;
                        string name = reader.GetString(md.Name);

                        string mods = string.Empty;
                        if ((ma & MethodAttributes.Static) != 0) mods += "static ";
                        if ((ma & MethodAttributes.Abstract) != 0) mods += "abstract ";
                        if ((ma & MethodAttributes.Virtual) != 0 && (ma & MethodAttributes.NewSlot) == 0) mods += "override ";

                        string ret;
                        string ps;
                        try
                        {
                            MethodSignature<string> sig = md.DecodeSignature(provider, null);
                            ret = sig.ReturnType;
                            ps = ParameterList(reader, md, sig);
                        }
                        catch
                        {
                            ret = "?";
                            ps = "?";
                        }
                        Console.WriteLine("  method " + vis + " " + mods + ret + " " + name + "(" + ps + ")");
                    }
                }
            }
        }

        private static int Main(string[] args)
        {
            if (args.Length < 1)
            {
                Console.Error.WriteLine("usage: ApiDump <assembly.dll> [typeFilterRegex] [--members] [--all]");
                return 2;
            }

            string path = args[0];
            string filter = null;
            bool members = false;
            bool all = false;
            for (int i = 1; i < args.Length; i++)
            {
                if (args[i] == "--members") members = true;
                else if (args[i] == "--all") all = true;
                else filter = args[i];
            }

            try
            {
                Run(path, filter, members, all);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("ERROR: " + ex.Message);
                return 1;
            }
            return 0;
        }
    }
}
