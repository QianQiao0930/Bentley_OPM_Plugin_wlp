using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
namespace SteelSectionProbe
{
    /// <summary>首页英文品牌副标题的原型字距；只负责文本绘制。</summary>
    internal sealed class HomeTrackedText:Control
    {
        public static readonly DependencyProperty TextProperty=DependencyProperty.Register("Text",typeof(string),typeof(HomeTrackedText),new FrameworkPropertyMetadata("",FrameworkPropertyMetadataOptions.AffectsMeasure|FrameworkPropertyMetadataOptions.AffectsRender));
        public static readonly DependencyProperty TrackingProperty=DependencyProperty.Register("Tracking",typeof(double),typeof(HomeTrackedText),new FrameworkPropertyMetadata(1.2,FrameworkPropertyMetadataOptions.AffectsMeasure|FrameworkPropertyMetadataOptions.AffectsRender));
        public string Text {get{return (string)GetValue(TextProperty);}set{SetValue(TextProperty,value);}}
        public double Tracking {get{return (double)GetValue(TrackingProperty);}set{SetValue(TrackingProperty,value);}}
        private FormattedText Glyph(char c)
        {return new FormattedText(c.ToString(),CultureInfo.InvariantCulture,FlowDirection.LeftToRight,new Typeface(FontFamily,FontStyle,FontWeight,FontStretch),FontSize,Foreground,VisualTreeHelper.GetDpi(this).PixelsPerDip);}
        protected override Size MeasureOverride(Size available)
        {
            double width=0,height=0;string text=Text??"";
            foreach(char c in text){var glyph=Glyph(c);width+=glyph.WidthIncludingTrailingWhitespace+Tracking;height=System.Math.Max(height,glyph.Height);}
            return new Size(System.Math.Max(0,width-(text.Length>0?Tracking:0)),height);
        }
        protected override void OnRender(DrawingContext drawing)
        {base.OnRender(drawing);double x=0;foreach(char c in Text??""){var glyph=Glyph(c);drawing.DrawText(glyph,new Point(x,0));x+=glyph.WidthIncludingTrailingWhitespace+Tracking;}}
    }
}
