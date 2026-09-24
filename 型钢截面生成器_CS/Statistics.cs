using System;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class Statistics
    {
        private const string LibraryName="PipeSupportComponents";
        private static readonly string[] Names={ "RecordKind","SupportType","AssemblyTag",
            "ComponentName","Specification","DesignLengthMm","Quantity","Unit","PipeNumber" };
        private static readonly CustomProperty.TypeKind[] Kinds={
            CustomProperty.TypeKind.String,CustomProperty.TypeKind.String,CustomProperty.TypeKind.String,
            CustomProperty.TypeKind.String,CustomProperty.TypeKind.String,CustomProperty.TypeKind.Double,
            CustomProperty.TypeKind.Integer,CustomProperty.TypeKind.String,CustomProperty.TypeKind.String };
        private static string Hash10(string value)
        {
            using(var md5=MD5.Create())
            {
                byte[] bytes=md5.ComputeHash(Encoding.UTF8.GetBytes(value));
                var result=new StringBuilder();
                for(int i=0;i<5;i++) result.Append(bytes[i].ToString("x2",CultureInfo.InvariantCulture));
                return result.ToString();
            }
        }
        private static ItemType Ensure(string name,object[] defaults)
        {
            var file=Session.Instance.GetActiveDgnFile();
            ItemTypeLibrary library=ItemTypeLibrary.FindByName(LibraryName,file);
            bool changed=false;
            if(library==null) { library=ItemTypeLibrary.Create(LibraryName,file,false); changed=true; }
            ItemType type=library.GetItemTypeByName(name);
            if(type==null) { type=library.AddItemType(name,false); changed=true; }
            if(type==null) throw new InvalidOperationException("Cannot create ItemType "+name);
            for(int i=0;i<Names.Length;i++)
            {
                CustomProperty property=type.GetPropertyByName(Names[i]);
                if(property!=null) continue;
                property=type.AddProperty(Names[i],false);
                if(property==null) throw new InvalidOperationException("Cannot create property "+Names[i]);
                property.Type=Kinds[i];
                property.DefaultValue=defaults[i];
                changed=true;
            }
            if(changed && !library.Write()) throw new InvalidOperationException("Cannot persist ItemType library");
            library=ItemTypeLibrary.FindByName(LibraryName,file);
            return library.GetItemTypeByName(name);
        }
        internal static void Attach(Element element,FamilyData family,ProfileData profile,double lengthMm)
        {
            string assemblyName="PipeSupportAssembly_STEEL_SECTION_"+Hash10("|"+profile.Name);
            string lengthKey=lengthMm.ToString("F3",CultureInfo.InvariantCulture).Replace('.','_').Replace('-','N');
            string componentName="PipeSupportComponent_STEEL_SECTION_"+family.Id+"_L"+lengthKey;
            object[] assembly={"Assembly","型钢","","支吊架",profile.Name,0.0,1,"套",""};
            object[] component={"Component","型钢","",family.Label,profile.Name,lengthMm,1,"根",""};
            var host=new CustomItemHost(element,false);
            host.ApplyCustomItem(Ensure(assemblyName,assembly));
            host.ApplyCustomItem(Ensure(componentName,component));
        }
    }
}
