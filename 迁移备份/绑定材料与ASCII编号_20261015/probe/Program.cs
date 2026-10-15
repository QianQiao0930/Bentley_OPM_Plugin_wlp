using System.Reflection;
using System.Reflection.Emit;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using System.Text.RegularExpressions;
using var stream=File.OpenRead(args[0]);
using var pe=new PEReader(stream);
var md=pe.GetMetadataReader();
string Name(EntityHandle h)=>h.Kind switch {
 HandleKind.TypeDefinition=>md.GetString(md.GetTypeDefinition((TypeDefinitionHandle)h).Name),
 HandleKind.TypeReference=>md.GetString(md.GetTypeReference((TypeReferenceHandle)h).Name),
 HandleKind.MemberReference=>Name(md.GetMemberReference((MemberReferenceHandle)h).Parent)+"."+md.GetString(md.GetMemberReference((MemberReferenceHandle)h).Name),
 HandleKind.MethodDefinition=>md.GetString(md.GetMethodDefinition((MethodDefinitionHandle)h).Name),
 HandleKind.FieldDefinition=>md.GetString(md.GetFieldDefinition((FieldDefinitionHandle)h).Name),_=>h.Kind.ToString()};
var codes=typeof(OpCodes).GetFields(BindingFlags.Public|BindingFlags.Static).Where(f=>f.FieldType==typeof(OpCode)).Select(f=>(OpCode)f.GetValue(null)).ToDictionary(o=>(ushort)o.Value);
foreach(var th in md.TypeDefinitions){var t=md.GetTypeDefinition(th);if(!Regex.IsMatch(md.GetString(t.Name),args[1]))continue;
 foreach(var mh in t.GetMethods()){var m=md.GetMethodDefinition(mh);if(!Regex.IsMatch(md.GetString(m.Name),args[2])||m.RelativeVirtualAddress==0)continue;
 Console.WriteLine(Name(th)+"."+md.GetString(m.Name));var bytes=pe.GetMethodBody(m.RelativeVirtualAddress).GetILBytes();
 for(int i=0;i<bytes.Length;){int offset=i;ushort n=bytes[i++];if(n==0xfe)n=(ushort)(0xfe00|bytes[i++]);var op=codes[n];string value="";int size=op.OperandType switch{OperandType.InlineNone=>0,OperandType.ShortInlineBrTarget or OperandType.ShortInlineI or OperandType.ShortInlineVar=>1,OperandType.InlineVar=>2,OperandType.InlineI8 or OperandType.InlineR=>8,OperandType.InlineSwitch=>4+4*BitConverter.ToInt32(bytes,i),_=>4};
 if(size==4&&new[]{OperandType.InlineField,OperandType.InlineMethod,OperandType.InlineType,OperandType.InlineTok}.Contains(op.OperandType))value=Name(MetadataTokens.EntityHandle(BitConverter.ToInt32(bytes,i)));
 else if(op.OperandType==OperandType.InlineString)value=md.GetUserString(MetadataTokens.UserStringHandle(BitConverter.ToInt32(bytes,i)&0xffffff));
 else if(size>0)value=Convert.ToHexString(bytes.AsSpan(i,size));i+=size;Console.WriteLine($" {offset:X4}: {op.Name} {value}");}
 }}
