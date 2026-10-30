using System;
using System.Collections.Generic;
using System.Windows.Forms;
using Bentley.GeometryNET;
using Com=Bentley.Interop.MicroStationDGN;
namespace Bentley.GeometryNET {
 public struct DVector3d {public double X,Y,Z;public DVector3d(double x,double y,double z){X=x;Y=y;Z=z;}}
 public struct DMatrix3d {
  public DVector3d A,B,C;public static DMatrix3d Identity{get{return FromRows(new DVector3d(1,0,0),new DVector3d(0,1,0),new DVector3d(0,0,1));}}
  public static DMatrix3d FromRows(DVector3d a,DVector3d b,DVector3d c){return new DMatrix3d{A=a,B=b,C=c};}
  public DVector3d Multiply(DVector3d v){return new DVector3d(A.X*v.X+A.Y*v.Y+A.Z*v.Z,B.X*v.X+B.Y*v.Y+B.Z*v.Z,C.X*v.X+C.Y*v.Y+C.Z*v.Z);}
 }
}
namespace Bentley.DgnPlatformNET {public struct ViewFlags {public bool OnOff,Fill,TextNodes,Dimensions,Constructs,Grid,LineWeights,Camera;public int RenderMode;}}
namespace Bentley.Interop.MicroStationDGN {
 public struct Matrix3d {public Point3d RowX,RowY,RowZ;}
 public struct Transform3d {public Matrix3d Matrix;}
 public sealed partial class Application {public Transform3d Transform3dFromMatrix3d(ref Matrix3d m){return new Transform3d{Matrix=m};}}
 public sealed partial class CellElement {
  public static int Pictures,Transforms;public static bool DrawBackground,FailPicture;
  public void Transform(ref Transform3d t){Transforms++;}
  public object GetPicture(int width,int height,bool background){Pictures++;DrawBackground=background;if(FailPicture)throw new Exception("picture fault");var bitmap=new System.Drawing.Bitmap(128,128,System.Drawing.Imaging.PixelFormat.Format32bppArgb);using(var g=System.Drawing.Graphics.FromImage(bitmap)){g.Clear(System.Drawing.Color.Transparent);g.FillRectangle(System.Drawing.Brushes.White,7,15,18,60);}return bitmap;}
 }
}
namespace SteelSectionProbe {
 internal sealed class MainWindow:Form {internal static MainWindow Current;internal void SetStatus(string s,bool e){UiFixture.Status=s;}internal void ShowHome(){}internal void BeginTitleDrag(){}internal void MinimizeFromHome(){}}
 internal static class UiFixture {internal static bool FailRead,FailGeometry;internal static int ReadCalls,GeometryCalls;internal static string Status;internal static Action DuringRead;}
 internal static class CelLibraryReader {
  internal static string DefaultLibraryPath{get{return "E:/fixtures/地面冲洗水盘管.cel";}}
  internal static CelLibraryCatalog Read(string path){UiFixture.ReadCalls++;if(UiFixture.DuringRead!=null)UiFixture.DuringRead();if(UiFixture.FailRead)throw new Exception("read incomplete");return new CelLibraryCatalog(path,new List<CelLibraryEntry>{new CelLibraryEntry(path,"coil","地面冲洗水盘管",true,false,0,0,0,"mm",1000),new CelLibraryEntry(path,"coil-2","加长盘管",true,false,0,0,0,"mm",1000)},1);}
 }
 internal static class CelLibraryGeometry {
  internal static Com.CellElement CreatePreview(CelLibraryEntry e,double a){return Create(e,DPoint3d.Zero,a);}
  internal static Com.CellElement Create(CelLibraryEntry e,DPoint3d p,double a){UiFixture.GeometryCalls++;if(UiFixture.FailGeometry)throw new Exception("geometry unavailable");return new Com.CellElement{Name=e.Name,Origin=new Com.Point3d{X=p.X/1000,Y=p.Y/1000,Z=p.Z/1000}};}
 }
}
