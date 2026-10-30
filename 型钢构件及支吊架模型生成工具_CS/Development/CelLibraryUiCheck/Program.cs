using System;
using System.IO;
using System.Reflection;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Bentley.DgnPlatformNET;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Preview=Bentley.Interop.MicroStationDGN.CellElement;
namespace SteelSectionProbe {
 internal static class Program {
  static int checks;static void Check(bool v,string n){checks++;if(!v)throw new Exception(n);}
  static T C<T>(CelLibraryPage p,string n)where T:class{return p.FindName(n) as T;}
  static void Click(CelLibraryPage p,string n){C<Button>(p,n).RaiseEvent(new RoutedEventArgs(Button.ClickEvent));}
  static void Invoke(object o,string n,params object[] a){o.GetType().GetMethod(n,BindingFlags.NonPublic|BindingFlags.Instance).Invoke(o,a);}
  static void Pump(){Dispatcher.CurrentDispatcher.Invoke(()=>{},DispatcherPriority.ApplicationIdle);}
  [STAThread]static int Main(string[] args){try{
   Fixture.Reset();var page=new CelLibraryPage();NativePanelLayout.Apply(page);page.OnActivated();
   Check(page.PageId=="cel-library"&&C<ComboBox>(page,"CellCombo").Items.Count==2,"real page reads dropdown");
   Check(C<TextBlock>(page,"LibraryCountText").Text.Contains("2")&&C<Button>(page,"StartButton").IsEnabled,"count and preview enable start");
   Check(Session.Instance.Model.Elements.Count==0,"panel preview never persists");
   bool busySeen=false;UiFixture.DuringRead=()=>{busySeen=page.IsBusy&&!C<Button>(page,"StartButton").IsEnabled;bool blocked=false;try{page.OnDeactivated();}catch{blocked=true;}Check(blocked,"busy navigation blocked");};Click(page,"RefreshLibraryButton");Check(busySeen&&!page.IsBusy,"read busy restored");UiFixture.DuringRead=null;
   C<TextBox>(page,"AngleText").Text="bad";Check(!C<Button>(page,"StartButton").IsEnabled,"invalid angle disables start");C<TextBox>(page,"AngleText").Text="90";Invoke(page,"Preview_Tick",null,EventArgs.Empty);
   Click(page,"StartButton");Check(CelPlacementTool.IsActive,"start installs tool");var tool=DgnPrimitiveTool.Installed;tool.Dynamic(new DPoint3d(1000,2000,0));tool.Click(new DPoint3d(1000,2000,0));
   Check(Session.Instance.Model.Elements.Count==1&&C<TextBlock>(page,"PlacementStateText").Text.Contains("1"),"single click page feedback");Click(page,"ReadStatisticsButton");Check(C<TextBlock>(page,"StatisticsCountText").Text.Contains("合计 1")&&C<Button>(page,"ExportButton").IsEnabled,"actual marked root statistics");
   TransactionManager.Undo();Check(C<TextBlock>(page,"StatisticsCountText").Text=="尚未统计"&&!C<Button>(page,"ExportButton").IsEnabled,"undo invalidates snapshot/export");
   tool.Dynamic(new DPoint3d(2000,3000,0));Fixture.FailReset=true;bool rejected=false;try{page.OnDeactivated();}catch{rejected=true;}Check(rejected&&CelPlacementTool.NeedsCleanup,"cleanup failure blocks navigation retains owner");Fixture.FailReset=false;page.OnDeactivated();Check(!CelPlacementTool.NeedsCleanup&&!C<Button>(page,"StartButton").IsEnabled,"deactivate retry cleans pending and disables");
   page.OnActivated();UiFixture.FailRead=true;Click(page,"RefreshLibraryButton");Check(C<TextBlock>(page,"LibraryCountText").Text.Contains("失败")&&!C<Button>(page,"StartButton").IsEnabled,"read failure no stale valid preview");UiFixture.FailRead=false;Click(page,"RefreshLibraryButton");
   UiFixture.FailGeometry=true;C<ComboBox>(page,"CellCombo").SelectedIndex=1;Click(page,"StartButton");Check(!CelPlacementTool.IsActive,"actual geometry failure still blocks tool installation independently of picture status");UiFixture.FailGeometry=false;C<ComboBox>(page,"CellCombo").SelectedIndex=0;
   // Actual preview wrapper, with the host producing a synthetic off-center white pen on transparency.
   var preview=C<CelLibraryPreviewControl>(page,"CellPreview");int pictureCount=Preview.Pictures;int transformCount=Preview.Transforms;preview.SetTopView(true);
   Check(Preview.Pictures==pictureCount+1&&!Preview.DrawBackground&&Preview.Transforms==transformCount,"top preview renders real picture without background or view rotation");
   preview.SetTopView(false);Check(Preview.Transforms==transformCount+1,"isometric transform affects preview copy only");
   var entry=(CelLibraryEntry)C<ComboBox>(page,"CellCombo").SelectedItem;Click(page,"StartButton");Preview.FailPicture=true;preview.SetTopView(true);Check(preview.IsReady&&C<Button>(page,"StartButton").IsEnabled&&CelPlacementTool.IsActive,"direction render failure retains image and continuous placement");
   DgnPrimitiveTool.Installed.Click(new DPoint3d(4000,5000,0));Check(Session.Instance.Model.Elements.Count==2,"cell can be placed after direction picture failure");
   Preview.FailPicture=false;int failedPictures=Preview.Pictures;preview.SetTopView(true);Check(preview.IsReady&&Preview.Pictures==failedPictures+1,"failed direction can be retried without reselecting the cell");Click(page,"EndButton");
   CheckOlePictures();
   using(var fixture=new System.Drawing.Bitmap(200,100,System.Drawing.Imaging.PixelFormat.Format32bppArgb)){
    using(var g=System.Drawing.Graphics.FromImage(fixture)){g.Clear(System.Drawing.Color.Transparent);g.FillRectangle(System.Drawing.Brushes.White,5,9,100,16);}
    var composed=CelLibraryPreviewControl.Compose(fixture);var bounds=InkBounds(composed);
    Check(composed.PixelWidth>composed.PixelHeight*2,"wide object retains aspect and fills a wide panel");
    Check(Math.Abs(bounds.Width/bounds.Height-100.0/16)<.35,"source aspect preserved within antialiasing fringe: "+bounds);
    Check(Math.Abs((bounds.Left+bounds.Right)/2.0-composed.PixelWidth/2.0)<1&&Math.Abs((bounds.Top+bounds.Bottom)/2.0-composed.PixelHeight/2.0)<1,"off-center source ink becomes centered on both axes");
    Check(WhiteCorner(composed),"preview background is opaque white");
   }
   string output=Path.GetFullPath(args.Length>0?args[0]:"previews");Directory.CreateDirectory(output);
   // Screenshots explicitly distinguish the test fixture from real CEL geometry.
   preview.Clear("离线界面检查\n实际 CEL 几何在 OPM 中显示");Invoke(page,"UpdateEnabled");
   foreach(var size in new[]{new Size(398,512),new Size(400,560),new Size(400,600),new Size(400,880),new Size(520,720)}){
    page.Measure(size);page.Arrange(new Rect(new Point(),size));page.UpdateLayout();Pump();var start=C<Button>(page,"StartButton");var pos=start.TranslatePoint(new Point(),page);Check(pos.Y>=0&&pos.Y+start.ActualHeight<=size.Height,"fixed bottom visible "+size);
    Check(TextContains(C<ComboBox>(page,"CellCombo"),"地面冲洗水盘管")&&!TextContains(C<ComboBox>(page,"CellCombo"),"SteelSectionProbe"),"cell name visible rather than CLR type "+size);
    var pc=C<Border>(page,"PreviewCard");var pv=pc.TranslatePoint(new Point(),page);Check(pc.ActualHeight>=150&&pv.Y>=0&&pv.Y+pc.ActualHeight<=pos.Y,"panel preview visible "+size);
    var scroll=C<ScrollViewer>(page,"ParameterScroll");Check(scroll.ActualHeight>=40,"parameters remain scrollable "+size);scroll.ScrollToBottom();page.UpdateLayout();Check(Math.Abs(start.TranslatePoint(new Point(),page).Y-pos.Y)<.1,"scroll keeps operation fixed "+size);scroll.ScrollToTop();page.UpdateLayout();
    foreach(double dpi in new[]{1d,1.25,1.5,2}){var bmp=new RenderTargetBitmap((int)(size.Width*dpi),(int)(size.Height*dpi),96*dpi,96*dpi,PixelFormats.Pbgra32);bmp.Render(page);Check(bmp.PixelWidth==(int)(size.Width*dpi),"DPI "+dpi);if(dpi==1){var png=new PngBitmapEncoder();png.Frames.Add(BitmapFrame.Create(bmp));using(var f=File.Create(Path.Combine(output,"cel-page-"+size.Width+"x"+size.Height+".png")))png.Save(f);}}
   }
   page.OnDeactivated();Console.WriteLine("CEL UI: "+checks+" assertions passed; real page/XAML/preview lifecycle, native APIs use fakes. "+output);return 0;
  }catch(Exception ex){Console.Error.WriteLine(ex);return 1;}}
  static void CheckOlePictures(){
   using(var stream=new MemoryStream())
   using(var surface=new System.Drawing.Bitmap(160,80))
   using(var graphics=System.Drawing.Graphics.FromImage(surface)){
    var dc=graphics.GetHdc();System.Drawing.Imaging.Metafile metafile;
    try{metafile=new System.Drawing.Imaging.Metafile(stream,dc,new System.Drawing.Rectangle(0,0,160,80),System.Drawing.Imaging.MetafileFrameUnit.Pixel,System.Drawing.Imaging.EmfType.EmfOnly);}finally{graphics.ReleaseHdc(dc);}
    using(metafile){using(var draw=System.Drawing.Graphics.FromImage(metafile)){draw.FillRectangle(System.Drawing.Brushes.Teal,20,20,100,30);draw.DrawLine(System.Drawing.Pens.White,30,10,90,10);}
     object borrowed=WrapMetafile(metafile);
     for(int i=0;i<24;i++){using(var raster=CelLibraryPreviewControl.ReadPicture(borrowed)){var source=CelLibraryPreviewControl.Compose(raster);Check(source.IsFrozen&&WhiteCorner(source),"repeated borrowed OLE EMF render remains valid and white "+i);}}
     GC.KeepAlive(borrowed);System.Runtime.InteropServices.Marshal.ReleaseComObject(borrowed);
    }
   }
  }
  [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
  struct PictureDescription {public int Size,Type;public IntPtr Image,Palette;}
  [System.Runtime.InteropServices.DllImport("oleaut32.dll",ExactSpelling=true,PreserveSig=false)]
  static extern void OleCreatePictureIndirect(ref PictureDescription description,ref Guid iid,[System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.Bool)]bool own,[System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.Interface)]out object picture);
  static object WrapMetafile(System.Drawing.Imaging.Metafile image){var description=new PictureDescription{Size=System.Runtime.InteropServices.Marshal.SizeOf(typeof(PictureDescription)),Type=4,Image=image.GetHenhmetafile()};var iid=new Guid("7BF80980-BF32-101A-8BBB-00AA00300CAB");object picture;OleCreatePictureIndirect(ref description,ref iid,true,out picture);return picture;}
  static byte[] Pixels(BitmapSource source){var converted=new FormatConvertedBitmap(source,PixelFormats.Bgra32,null,0);var p=new byte[converted.PixelWidth*converted.PixelHeight*4];converted.CopyPixels(p,converted.PixelWidth*4,0);return p;}
  static bool WhiteCorner(BitmapSource source){var p=Pixels(source);return p[0]==255&&p[1]==255&&p[2]==255&&p[3]==255;}
  static Rect InkBounds(BitmapSource source){var p=Pixels(source);int l=source.PixelWidth,t=source.PixelHeight,r=-1,b=-1;for(int y=0;y<source.PixelHeight;y++)for(int x=0;x<source.PixelWidth;x++){int i=(y*source.PixelWidth+x)*4;if(p[i]>245&&p[i+1]>245&&p[i+2]>245)continue;l=Math.Min(l,x);r=Math.Max(r,x);t=Math.Min(t,y);b=Math.Max(b,y);}return new Rect(l,t,r-l+1,b-t+1);}
  static bool TextContains(DependencyObject o,string s){var t=o as TextBlock;if(t!=null&&t.Text.Contains(s))return true;for(int i=0;i<VisualTreeHelper.GetChildrenCount(o);i++)if(TextContains(VisualTreeHelper.GetChild(o,i),s))return true;return false;}
 }
}
