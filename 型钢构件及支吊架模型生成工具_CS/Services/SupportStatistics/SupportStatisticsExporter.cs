using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;
using System.Web.Script.Serialization;
using System.Xml;

namespace SteelSectionProbe
{
    internal static class SupportStatisticsExporter
    {
        internal static void WriteJson(string path,SupportStatisticsSnapshot report)
        {
            var payload=new Dictionary<string,object> {
                {"itemTypeLibrary",SupportStatisticsSnapshot.LibraryName},
                {"assemblyCount",report.AssemblyCount},
                {"componentRecordCount",report.ComponentRecordCount},
                {"supportsByType",report.SupportsByType.Select(t=>new {
                    supportType=t.SupportType,assemblyCount=t.AssemblyCount,
                    assemblyTags=t.AssemblyTags
                }).ToArray()},
                {"materials",report.Materials.Select(m=>new {
                    supportType=m.SupportType,componentName=m.ComponentName,
                    specification=m.Specification,unit=m.Unit,quantity=m.Quantity,
                    totalDesignLengthMm=m.TotalDesignLengthMm
                }).ToArray()},
                {"records",report.Records.Select(r=>new {
                    elementId=r.ElementId,itemType=r.ItemType,recordKind=r.RecordKind,
                    supportType=r.SupportType,assemblyTag=r.AssemblyTag,
                    componentName=r.ComponentName,specification=r.Specification,
                    designLengthMm=r.DesignLengthMm,quantity=r.Quantity,
                    unit=r.Unit,pipeNumber=r.PipeNumber
                }).ToArray()}
            };
            var serializer=new JavaScriptSerializer { MaxJsonLength=int.MaxValue };
            File.WriteAllText(path,serializer.Serialize(payload),new UTF8Encoding(false));
        }
        internal static void WriteExcel(string path,SupportStatisticsSnapshot report)
        {
            var sheets=Sheets(report);
            using(var file=File.Create(path))
            using(var zip=new ZipArchive(file,ZipArchiveMode.Create))
            {
                Add(zip,"[Content_Types].xml",w=>{
                    w.WriteStartElement("Types","http://schemas.openxmlformats.org/package/2006/content-types");
                    Default(w,"rels","application/vnd.openxmlformats-package.relationships+xml");
                    Default(w,"xml","application/xml");
                    Override(w,"/xl/workbook.xml","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml");
                    Override(w,"/xl/styles.xml","application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml");
                    for(int i=0;i<sheets.Count;i++)
                        Override(w,"/xl/worksheets/sheet"+(i+1)+".xml",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml");
                    w.WriteEndElement();
                });
                Add(zip,"_rels/.rels",w=>{
                    w.WriteStartElement("Relationships","http://schemas.openxmlformats.org/package/2006/relationships");
                    Relationship(w,"rId1","http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
                        "xl/workbook.xml");
                    w.WriteEndElement();
                });
                Add(zip,"xl/workbook.xml",w=>{
                    w.WriteStartElement("workbook","http://schemas.openxmlformats.org/spreadsheetml/2006/main");
                    w.WriteAttributeString("xmlns","r",null,"http://schemas.openxmlformats.org/officeDocument/2006/relationships");
                    w.WriteStartElement("sheets");
                    for(int i=0;i<sheets.Count;i++)
                    {
                        w.WriteStartElement("sheet");
                        w.WriteAttributeString("name",sheets[i].Key);
                        w.WriteAttributeString("sheetId",(i+1).ToString(CultureInfo.InvariantCulture));
                        w.WriteAttributeString("r","id","http://schemas.openxmlformats.org/officeDocument/2006/relationships",
                            "rId"+(i+1));
                        w.WriteEndElement();
                    }
                    w.WriteEndElement(); w.WriteEndElement();
                });
                Add(zip,"xl/_rels/workbook.xml.rels",w=>{
                    w.WriteStartElement("Relationships","http://schemas.openxmlformats.org/package/2006/relationships");
                    for(int i=0;i<sheets.Count;i++)
                        Relationship(w,"rId"+(i+1),
                            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
                            "worksheets/sheet"+(i+1)+".xml");
                    Relationship(w,"rId"+(sheets.Count+1),
                        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles",
                        "styles.xml");
                    w.WriteEndElement();
                });
                Add(zip,"xl/styles.xml",w=>{
                    const string ns="http://schemas.openxmlformats.org/spreadsheetml/2006/main";
                    w.WriteStartElement("styleSheet",ns);
                    w.WriteStartElement("fonts"); w.WriteAttributeString("count","2");
                    w.WriteStartElement("font"); w.WriteEndElement();
                    w.WriteStartElement("font"); w.WriteStartElement("b"); w.WriteEndElement(); w.WriteEndElement();
                    w.WriteEndElement();
                    w.WriteStartElement("fills"); w.WriteAttributeString("count","2");
                    w.WriteStartElement("fill"); w.WriteStartElement("patternFill"); w.WriteAttributeString("patternType","none"); w.WriteEndElement(); w.WriteEndElement();
                    w.WriteStartElement("fill"); w.WriteStartElement("patternFill"); w.WriteAttributeString("patternType","solid");
                    w.WriteStartElement("fgColor"); w.WriteAttributeString("rgb","FFEAF0F7"); w.WriteEndElement();
                    w.WriteStartElement("bgColor"); w.WriteAttributeString("indexed","64"); w.WriteEndElement();
                    w.WriteEndElement(); w.WriteEndElement(); w.WriteEndElement();
                    w.WriteStartElement("borders"); w.WriteAttributeString("count","1");
                    w.WriteStartElement("border"); foreach(string edge in new[]{"left","right","top","bottom","diagonal"})
                    { w.WriteStartElement(edge); w.WriteEndElement(); } w.WriteEndElement(); w.WriteEndElement();
                    w.WriteStartElement("cellStyleXfs"); w.WriteAttributeString("count","1"); Xf(w,0,0); w.WriteEndElement();
                    w.WriteStartElement("cellXfs"); w.WriteAttributeString("count","2"); Xf(w,0,0); Xf(w,1,1); w.WriteEndElement();
                    w.WriteEndElement();
                });
                for(int i=0;i<sheets.Count;i++)
                {
                    var rows=sheets[i].Value;
                    Add(zip,"xl/worksheets/sheet"+(i+1)+".xml",w=>{
                        w.WriteStartElement("worksheet","http://schemas.openxmlformats.org/spreadsheetml/2006/main");
                        w.WriteStartElement("sheetData");
                        for(int row=0;row<rows.Count;row++)
                        {
                            w.WriteStartElement("row");
                            w.WriteAttributeString("r",(row+1).ToString(CultureInfo.InvariantCulture));
                            for(int column=0;column<rows[row].Length;column++)
                                Cell(w,column,row,rows[row][column],row==0);
                            w.WriteEndElement();
                        }
                        w.WriteEndElement(); w.WriteEndElement();
                    });
                }
            }
        }
        private static List<KeyValuePair<string,List<object[]>>> Sheets(SupportStatisticsSnapshot r)
        {
            var summary=new List<object[]> {
                new object[]{"管道支吊架统计"},
                new object[]{"导出时间",DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")},
                new object[]{"支吊架总套数",r.AssemblyCount},
                new object[]{"构件记录数",r.ComponentRecordCount},
                new object[]{},
                new object[]{"支吊架类型","套数","编号列表"}
            };
            foreach(var t in r.SupportsByType)
                summary.Add(new object[]{t.SupportType,t.AssemblyCount,string.Join("、",t.AssemblyTags)});
            var details=new Dictionary<ulong,List<string>>();
            foreach(var c in r.Records.Where(v=>!string.Equals(v.RecordKind,"Assembly",StringComparison.OrdinalIgnoreCase)))
            {
                List<string> list;
                if (!details.TryGetValue(c.ElementId,out list)) { list=new List<string>(); details.Add(c.ElementId,list); }
                list.Add(c.ComponentName+"("+c.Specification+")"+(c.Quantity!=1?"×"+c.Quantity:""));
            }
            var supports=new List<object[]> {new object[]{"序号","支吊架类型","支吊架编号","管道号","规格","构件明细","元素ID"}};
            int number=0;
            foreach(var a in r.Records.Where(v=>string.Equals(v.RecordKind,"Assembly",StringComparison.OrdinalIgnoreCase)))
            {
                List<string> list;
                details.TryGetValue(a.ElementId,out list);
                supports.Add(new object[]{++number,a.SupportType,a.AssemblyTag,a.PipeNumber,
                    a.Specification,list==null?"":string.Join("；",list),a.ElementId.ToString(CultureInfo.InvariantCulture)});
            }
            var materials=new List<object[]> {new object[]{"支吊架类型","构件名称","规格","单位","数量","总长(mm)"}};
            foreach(var m in r.Materials)
                materials.Add(new object[]{m.SupportType,m.ComponentName,m.Specification,m.Unit,
                    m.Quantity,m.TotalDesignLengthMm});
            return new List<KeyValuePair<string,List<object[]>>> {
                new KeyValuePair<string,List<object[]>>("汇总",summary),
                new KeyValuePair<string,List<object[]>>("支吊架表",supports),
                new KeyValuePair<string,List<object[]>>("材料汇总表",materials)
            };
        }
        private static void Add(ZipArchive zip,string name,Action<XmlWriter> write)
        {
            var entry=zip.CreateEntry(name,CompressionLevel.Optimal);
            using(var stream=entry.Open())
            using(var writer=XmlWriter.Create(stream,new XmlWriterSettings { Encoding=new UTF8Encoding(false),
                CloseOutput=false }))
                write(writer);
        }
        private static void Default(XmlWriter w,string extension,string content)
        {
            w.WriteStartElement("Default"); w.WriteAttributeString("Extension",extension);
            w.WriteAttributeString("ContentType",content); w.WriteEndElement();
        }
        private static void Override(XmlWriter w,string part,string content)
        {
            w.WriteStartElement("Override"); w.WriteAttributeString("PartName",part);
            w.WriteAttributeString("ContentType",content); w.WriteEndElement();
        }
        private static void Relationship(XmlWriter w,string id,string type,string target)
        {
            w.WriteStartElement("Relationship"); w.WriteAttributeString("Id",id);
            w.WriteAttributeString("Type",type); w.WriteAttributeString("Target",target); w.WriteEndElement();
        }
        private static void Xf(XmlWriter w,int font,int fill)
        {
            w.WriteStartElement("xf"); w.WriteAttributeString("numFmtId","0");
            w.WriteAttributeString("fontId",font.ToString()); w.WriteAttributeString("fillId",fill.ToString());
            w.WriteAttributeString("borderId","0"); w.WriteEndElement();
        }
        private static void Cell(XmlWriter w,int col,int row,object value,bool header)
        {
            if (value==null) return;
            w.WriteStartElement("c");
            w.WriteAttributeString("r",Column(col)+(row+1));
            if (header) w.WriteAttributeString("s","1");
            if (value is int || value is double)
            {
                w.WriteStartElement("v"); w.WriteString(Convert.ToString(value,CultureInfo.InvariantCulture)); w.WriteEndElement();
            }
            else
            {
                w.WriteAttributeString("t","inlineStr");
                w.WriteStartElement("is"); w.WriteStartElement("t");
                w.WriteString(Convert.ToString(value,CultureInfo.InvariantCulture));
                w.WriteEndElement(); w.WriteEndElement();
            }
            w.WriteEndElement();
        }
        private static string Column(int index)
        {
            string name="";
            for(int n=index+1;n>0;n=(n-1)/26) name=(char)('A'+(n-1)%26)+name;
            return name;
        }
    }
}
