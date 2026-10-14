using System;
using System.Collections.Generic;
namespace SteelSectionProbe
{
 internal static class ProductInfo {internal const string DisplayVersion="V0.0.3",AuthorName="魏";}
 internal static class LicenseService {internal static bool IsLicensingEnabled=true,IsActivated=true;internal static string DisplayStatus {get{return IsActivated?"已激活":"未激活";}}internal const string LicenseDescription="离线UI测试授权状态";}
 internal sealed class MainWindow {internal static MainWindow Current=new MainWindow();internal void BeginTitleDrag(){}internal void MinimizeFromHome(){}internal void Close(){}}
 internal static class HomePreferenceFixture
 {
  internal static void Reload()
  {
   typeof(HomePreferences).GetField("cache",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Static).SetValue(null,null);
  }
  internal static void Write(string json)
  {System.IO.File.WriteAllText(HomePreferences.FilePath,json);Reload();}
  internal static void Seed()
  {
   var records=new Dictionary<string,HomePreferenceRecord>();
   string[] ids={"pipe-clamp","n3-single-bracket","q1-small-pipe-support","n4-double-bracket"};
   double[] minutes={1,1,60,1320};
   for(int i=0;i<ids.Length;i++)records[ids[i]]=new HomePreferenceRecord{Stars=i==0?3:0,TotalUseCount=8-i,LastUsedUtc=DateTime.UtcNow.AddMinutes(-minutes[i]).ToString("o"),MonthlyUse=new Dictionary<string,int>{{DateTime.UtcNow.ToString("yyyy-MM"),2}}};
   records["steel-sections"]=new HomePreferenceRecord{TotalUseCount=21,MonthlyUse=new Dictionary<string,int>{{DateTime.UtcNow.ToString("yyyy-MM"),5}}};
   records["component-properties"]=new HomePreferenceRecord{LastUsedUtc=DateTime.UtcNow.AddMinutes(-2).ToString("o")};
   records["tank-manhole"]=new HomePreferenceRecord{LastUsedUtc=DateTime.UtcNow.AddMinutes(-3).ToString("o")};
   Write(new System.Web.Script.Serialization.JavaScriptSerializer().Serialize(new HomePreferences.Store{Features=records}));
  }
 }
}
