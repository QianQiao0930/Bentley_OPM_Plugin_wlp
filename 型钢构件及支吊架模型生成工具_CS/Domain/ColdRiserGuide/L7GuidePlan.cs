namespace SteelSectionProbe
{
    internal sealed class L7GuidePlan
    {
        internal L7GuideKind Kind;
        internal ColdRiserGuideSeries Series;
        internal N8Plan Connection;
        internal double AllowableLoadKn;
        internal string MaterialCode;
        internal bool HasMember {get{return Series==ColdRiserGuideSeries.L8 || Kind==L7GuideKind.Type1;}}
        internal string Code {get{return Series.ToString();}}
        internal A22ClampPlan Clamp;
        internal T4ShoeLayout Bearing;
        internal T4ShoeBooleanLayout BearingBoolean;
        internal double LengthMm,AngleDeg,BearingLengthMm,MemberStartMm,MemberLengthMm;
        internal string MemberFamily,MemberProfile,MemberLabel,Number,Specification,PipeNumber;
    }
}
