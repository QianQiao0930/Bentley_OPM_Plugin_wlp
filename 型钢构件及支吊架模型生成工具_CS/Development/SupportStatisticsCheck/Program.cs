using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Web.Script.Serialization;
using System.Xml;
using System.IO.Packaging;

namespace SteelSectionProbe
{
    internal static class Program
    {
        private static void Check(bool okay,string name)
        {
            if (!okay) throw new Exception(name);
        }
        private static void Main()
        {
            Check(SupportExportName.Suggest(@"C:\Models\A-101.dgn",
                new DateTime(2026,9,25,14,5,6))==
                "A-101_支吊架材料表_20260925140506","活动文档导出建议名");            var report=SupportStatisticsCalculator.Summarize(new [] {
                new SupportRecord { ElementId=10,RecordKind="Assembly",SupportType="弯头耳轴",
                    AssemblyTag="F2-DN100-DN50",Quantity=2 },
                new SupportRecord { ElementId=10,RecordKind="Component",SupportType="弯头耳轴",
                    ComponentName="耳轴",Specification="DN50",Unit="件",Quantity=3,DesignLengthMm=300 },
                new SupportRecord { ElementId=11,RecordKind="Component",SupportType="弯头耳轴",
                    ComponentName="耳轴",Specification="DN50",Unit="件",Quantity=1,DesignLengthMm=200 }
            });
            Check(report.AssemblyCount==2,"套数");
            Check(report.ComponentRecordCount==2,"构件记录数");
            Check(report.Materials.Count==1 && report.Materials[0].Quantity==4 &&
                report.Materials[0].TotalDesignLengthMm==1100,"材料汇总");
            string dir=Path.Combine(Path.GetTempPath(),"SupportStatisticsCheck_"+Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);
            try
            {
                string json=Path.Combine(dir,"report.json"),xlsx=Path.Combine(dir,"report.xlsx");
                SupportStatisticsExporter.WriteJson(json,report);
                SupportStatisticsExporter.WriteExcel(xlsx,report);
                var value=new JavaScriptSerializer().DeserializeObject(File.ReadAllText(json));
                var payload=(Dictionary<string,object>)value;
                Check(Convert.ToInt32(payload["assemblyCount"])==2,"JSON 套数");
                Check(((object[])payload["records"]).Length==3,"JSON 明细");
                using(var zip=ZipFile.OpenRead(xlsx))
                {
                    Check(zip.GetEntry("xl/workbook.xml")!=null,"Excel 工作簿");
                    Check(zip.GetEntry("xl/worksheets/sheet1.xml")!=null,"Excel 汇总");
                    Check(zip.GetEntry("xl/worksheets/sheet2.xml")!=null,"Excel 支吊架表");
                    Check(zip.GetEntry("xl/worksheets/sheet3.xml")!=null,"Excel 材料汇总表");
                    foreach(var entry in zip.Entries.Where(e=>e.FullName.EndsWith(".xml")))
                    {
                        using(var reader=XmlReader.Create(entry.Open()))
                            while(reader.Read()) { }
                    }
                }
                using(var package=Package.Open(xlsx,FileMode.Open,FileAccess.Read))
                {
                    Check(package.PartExists(new Uri("/xl/workbook.xml",UriKind.Relative)),
                        "Excel OPC 工作簿部件");
                }                Console.WriteLine("SupportStatisticsCheck: summary, JSON and three-sheet XLSX passed.");
            }
            finally { Directory.Delete(dir,true); }
        }
    }
}
