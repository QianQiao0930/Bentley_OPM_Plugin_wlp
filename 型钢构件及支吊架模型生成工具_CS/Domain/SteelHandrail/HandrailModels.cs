using System;
using System.Collections.Generic;
namespace SteelSectionProbe
{
    internal struct HandrailPoint
    {
        internal double X,Y,Z;
        internal HandrailPoint(double x,double y,double z){X=x;Y=y;Z=z;}
        internal static HandrailPoint Up {get{return new HandrailPoint(0,0,1);}}
        public static HandrailPoint operator +(HandrailPoint a,HandrailPoint b){return new HandrailPoint(a.X+b.X,a.Y+b.Y,a.Z+b.Z);}
        public static HandrailPoint operator -(HandrailPoint a,HandrailPoint b){return new HandrailPoint(a.X-b.X,a.Y-b.Y,a.Z-b.Z);}
        public static HandrailPoint operator *(HandrailPoint a,double k){return new HandrailPoint(a.X*k,a.Y*k,a.Z*k);}
        internal double Length {get{return Math.Sqrt(X*X+Y*Y+Z*Z);}}
        internal double HorizontalLength {get{return Math.Sqrt(X*X+Y*Y);}}
        internal HandrailPoint Unit(){if(Length<1e-12)throw new InvalidOperationException("路径切向长度为零。");return this*(1/Length);}
        internal HandrailPoint Horizontal(){double l=HorizontalLength;if(l<1e-12)throw new InvalidOperationException("路径含竖直段，无法确定围栏内外侧。");return new HandrailPoint(X/l,Y/l,0);}
        internal HandrailPoint Normal(int side){var t=Horizontal();return new HandrailPoint(-t.Y*side,t.X*side,0);}
        internal static HandrailPoint Cross(HandrailPoint a,HandrailPoint b){return new HandrailPoint(a.Y*b.Z-a.Z*b.Y,a.Z*b.X-a.X*b.Z,a.X*b.Y-a.Y*b.X);}
        internal static double Dot(HandrailPoint a,HandrailPoint b){return a.X*b.X+a.Y*b.Y+a.Z*b.Z;}
    }
    internal enum HandrailConnection {Type1=1,Type2=2,Type3=3,Type4=4}
    internal enum HandrailClosure {None,Start,End,Both}
    internal sealed class HandrailParameters
    {
        internal HandrailConnection Connection=HandrailConnection.Type2;
        internal HandrailClosure Closure;
        internal int Side=1;
        internal bool Reverse;
        internal double StructureOffsetMm=120;
    }
    internal sealed class HandrailPiece
    {
        internal bool IsArc;
        internal HandrailPoint Start,End,Center,Radial,Tangent;
        internal double Radius=140,Angle,StartStation,Length,TurnSign;
        internal double EndStation {get{return StartStation+Length;}}
        internal HandrailPoint At(double fraction)
        {
            if(!IsArc)return Start+(End-Start)*fraction;
            double a=Angle*fraction;return Center+(Radial*Math.Cos(a)+Tangent*Math.Sin(a))*Radius;
        }
        internal HandrailPoint Direction(double fraction)
        {return IsArc?Radial*(-Math.Sin(Angle*fraction))+Tangent*Math.Cos(Angle*fraction):Tangent;}
    }
    internal sealed class HandrailCorner
    {
        internal bool GradeBreak;
        internal double Station,TangentDistance,ArcLength;
    }
    internal sealed class HandrailMaterial
    {
        internal string Code,Name,Specification;
        internal double LengthMm;
        internal int Quantity;
    }
    internal sealed class HandrailNode
    {
        internal HandrailPoint Point,Tangent,Normal,PlateLong,PlateShort,PlateCenter,Bottom,ElbowCenter,ElbowEnd,TubeEnd;
        internal readonly List<HandrailSection> Sections=new List<HandrailSection>();
    }
    internal sealed class HandrailSection
    {
        internal HandrailPoint Center;
        internal double Major,Minor;
        internal HandrailSection(HandrailPoint c,double a,double b){Center=c;Major=a;Minor=b;}
    }
    internal sealed class HandrailPlan
    {
        internal HandrailParameters Parameters;
        internal readonly List<HandrailPiece> Pieces=new List<HandrailPiece>();
        internal readonly List<HandrailCorner> Corners=new List<HandrailCorner>();
        internal List<HandrailPiece> Kickplate;
        internal List<double> Stations;
        internal List<HandrailMaterial> Materials;
        internal double LengthMm;
        internal HandrailPoint Origin;
        internal string Number;
    }
}
