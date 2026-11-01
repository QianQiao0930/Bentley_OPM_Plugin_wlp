using System.Collections.Immutable;
using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Reflection.Emit;
class Types : ISignatureTypeProvider<string, object?> {
 public string GetArrayType(string t,ArrayShape s)=>t+"[]"; public string GetByReferenceType(string t)=>"ref "+t;
 public string GetFunctionPointerType(MethodSignature<string> s)=>"fn"; public string GetGenericInstantiation(string t,ImmutableArray<string>a)=>t+"<"+string.Join(",",a)+">";
 public string GetGenericMethodParameter(object? c,int i)=>"!!"+i; public string GetGenericTypeParameter(object? c,int i)=>"!"+i;
 public string GetModifiedType(string m,string t,bool r)=>t; public string GetPinnedType(string t)=>t; public string GetPointerType(string t)=>t+"*";
 public string GetPrimitiveType(PrimitiveTypeCode c)=>c.ToString(); public string GetSZArrayType(string t)=>t+"[]";
 public string GetTypeFromDefinition(MetadataReader r,TypeDefinitionHandle h,byte k){var t=r.GetTypeDefinition(h);return r.GetString(t.Namespace)+"."+r.GetString(t.Name);}
 public string GetTypeFromReference(MetadataReader r,TypeReferenceHandle h,byte k){var t=r.GetTypeReference(h);return r.GetString(t.Namespace)+"."+r.GetString(t.Name);}
 public string GetTypeFromSpecification(MetadataReader r,object? c,TypeSpecificationHandle h,byte k)=>r.GetTypeSpecification(h).DecodeSignature(this,c);
}
class Program {
 static int Main(string[] args){using var f=File.OpenRead(args[0]);using var pe=new PEReader(f);var r=pe.GetMetadataReader();var ts=new Types();
 foreach(var h in r.TypeDefinitions){var t=r.GetTypeDefinition(h);var n=r.GetString(t.Namespace)+"."+r.GetString(t.Name);if(!args.Skip(1).Any(q=>n.Contains(q,StringComparison.OrdinalIgnoreCase)))continue;
 string bn=t.BaseType.IsNil?"none":t.BaseType.Kind==HandleKind.TypeDefinition?ts.GetTypeFromDefinition(r,(TypeDefinitionHandle)t.BaseType,0):t.BaseType.Kind==HandleKind.TypeReference?ts.GetTypeFromReference(r,(TypeReferenceHandle)t.BaseType,0):t.BaseType.Kind.ToString();Console.WriteLine("TYPE "+n+" base="+bn);
 foreach(var mh in t.GetMethods()){var m=r.GetMethodDefinition(mh);var mf=args.FirstOrDefault(a=>a.StartsWith("--method="))?.Substring(9);if(mf!=null&&!r.GetString(m.Name).Contains(mf,StringComparison.OrdinalIgnoreCase))continue;var s=m.DecodeSignature(ts,null);Console.WriteLine(m.Attributes+" "+s.ReturnType+" "+r.GetString(m.Name)+"("+string.Join(", ",s.ParameterTypes)+") ["+string.Join(", ",m.GetParameters().Select(p=>r.GetParameter(p)).Select(p=>p.SequenceNumber+":"+r.GetString(p.Name)))+"]");if(args.Contains("--il") && m.RelativeVirtualAddress!=0 && (m.ImplAttributes & MethodImplAttributes.CodeTypeMask)==MethodImplAttributes.IL)Dump(pe.GetMethodBody(m.RelativeVirtualAddress).GetILBytes()!,r);}
 foreach(var ph in t.GetProperties()){var p=r.GetPropertyDefinition(ph);var s=p.DecodeSignature(ts,null);Console.WriteLine("PROP "+s.ReturnType+" "+r.GetString(p.Name));}
 }return 0;}
 static void Dump(byte[] il,MetadataReader r){var ops=typeof(OpCodes).GetFields(BindingFlags.Public|BindingFlags.Static).Select(f=>(OpCode)f.GetValue(null)!).ToDictionary(o=>(ushort)o.Value);for(int p=0;p<il.Length;){int start=p;ushort key=il[p++];if(key==0xfe)key=(ushort)(0xfe00|il[p++]);var op=ops[key];int size=op.OperandType switch{OperandType.InlineNone=>0,OperandType.ShortInlineBrTarget or OperandType.ShortInlineI or OperandType.ShortInlineVar=>1,OperandType.InlineVar=>2,OperandType.InlineI8 or OperandType.InlineR=>8,OperandType.InlineSwitch=>4+4*BitConverter.ToInt32(il,p),_=>4};string arg=size>0?BitConverter.ToString(il,p,size):"";if(op.OperandType==OperandType.InlineString)arg="STRING: "+r.GetUserString(System.Reflection.Metadata.Ecma335.MetadataTokens.UserStringHandle(BitConverter.ToInt32(il,p)&0x00ffffff));if(size==4 && (op.OperandType==OperandType.InlineMethod||op.OperandType==OperandType.InlineField||op.OperandType==OperandType.InlineType)){var h=System.Reflection.Metadata.Ecma335.MetadataTokens.EntityHandle(BitConverter.ToInt32(il,p));arg=h.Kind switch{HandleKind.MemberReference=>r.GetString(r.GetMemberReference((MemberReferenceHandle)h).Name),HandleKind.MethodDefinition=>r.GetString(r.GetMethodDefinition((MethodDefinitionHandle)h).Name),HandleKind.FieldDefinition=>r.GetString(r.GetFieldDefinition((FieldDefinitionHandle)h).Name),HandleKind.TypeReference=>r.GetString(r.GetTypeReference((TypeReferenceHandle)h).Name),HandleKind.TypeDefinition=>r.GetString(r.GetTypeDefinition((TypeDefinitionHandle)h).Name),_=>h.Kind.ToString()};}Console.WriteLine("  "+start.ToString("X4")+" "+op.Name+" "+arg);p+=size;}}
}
