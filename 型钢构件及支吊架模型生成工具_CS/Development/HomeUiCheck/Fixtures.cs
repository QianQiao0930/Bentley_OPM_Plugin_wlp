using System;
using System.Collections.Generic;
namespace SteelSectionProbe
{
 internal static class ProductInfo {internal const string DisplayVersion="V0.0.3",AuthorName="魏";}
 internal static class LicenseService {internal static bool IsLicensingEnabled=true,IsActivated=true;internal static string DisplayStatus {get{return IsActivated?"已激活":"未激活";}}internal const string LicenseDescription="离线UI测试授权状态";}
 internal sealed class MainWindow {internal static MainWindow Current=new MainWindow();internal void BeginTitleDrag(){}internal void MinimizeFromHome(){}internal void Close(){}}
 internal static class HomePreferences
 {
  private static readonly Dictionary<string,HomePreferenceRecord> records=new Dictionary<string,HomePreferenceRecord>();
  internal static void Seed()
  {
   string[] ids={"pipe-clamp","n3-single-bracket","q1-small-pipe-support","n4-double-bracket"};
   double[] minutes={1,1,60,1320};
   for(int i=0;i<ids.Length;i++)records[ids[i]]=new HomePreferenceRecord{Stars=i==0?3:0,TotalUseCount=8-i,LastUsedUtc=DateTime.UtcNow.AddMinutes(-minutes[i]).ToString("o"),MonthlyUse=new Dictionary<string,int>{{DateTime.UtcNow.ToString("yyyy-MM"),2}}};
   records["steel-sections"]=new HomePreferenceRecord{TotalUseCount=21,MonthlyUse=new Dictionary<string,int>{{DateTime.UtcNow.ToString("yyyy-MM"),5}}};
  }
  internal static HomePreferenceRecord RecordFor(string id){HomePreferenceRecord r;return records.TryGetValue(id,out r)?r:null;}
  internal static List<HomeEntry> Rank(DateTime now){return HomeFeatureRanker.Rank(HomeFeatureCatalog.All(),records,now);}
  internal static void SetStars(string id,int value){if(!records.ContainsKey(id))records[id]=new HomePreferenceRecord();records[id].Stars=value;}
  internal static void Reset(){records.Clear();}
 }
}
