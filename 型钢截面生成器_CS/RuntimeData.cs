using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;

namespace SteelSectionProbe
{
    internal sealed class SegmentData
    {
        internal bool IsArc;
        internal double X0,Y0, Xm,Ym, X1,Y1;
    }
    internal sealed class ModeData
    {
        internal string Id, Label;
        internal SegmentData[] Segments;
        public override string ToString() { return Label; }
    }
    internal sealed class ProfileData
    {
        internal string Name;
        internal Dictionary<string,double> Dimensions;
        internal ModeData[] Modes;
        public override string ToString() { return Name; }
    }
    internal sealed class FamilyData
    {
        internal string Id, Label;
        internal ProfileData[] Profiles;
        public override string ToString() { return Label; }
    }
    internal static class RuntimeData
    {
        private static FamilyData[] cached;
        internal static FamilyData[] Families { get { return cached ?? (cached=Load()); } }
        private static string ReadString(BinaryReader reader)
        {
            uint length=reader.ReadUInt32();
            if (length>100000) throw new InvalidDataException("Invalid profile string length");
            byte[] bytes=reader.ReadBytes((int)length);
            if (bytes.Length!=length) throw new EndOfStreamException();
            return Encoding.UTF8.GetString(bytes);
        }
        private static FamilyData[] Load()
        {
            using (Stream stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("SteelSectionProbe.profiles.bin"))
            {
                if (stream==null) throw new InvalidOperationException("Missing embedded profile data");
                using (var reader=new BinaryReader(stream))
                {
                    if (Encoding.ASCII.GetString(reader.ReadBytes(4))!="SSP1") throw new InvalidDataException("Profile data format mismatch");
                    int familyCount=checked((int)reader.ReadUInt32());
                    FamilyData[] families=new FamilyData[familyCount];
                    for (int f=0; f<familyCount; f++)
                    {
                        var family=new FamilyData { Id=ReadString(reader),Label=ReadString(reader) };
                        int profileCount=checked((int)reader.ReadUInt32());
                        family.Profiles=new ProfileData[profileCount];
                        for (int p=0; p<profileCount; p++)
                        {
                            var profile=new ProfileData { Name=ReadString(reader),Dimensions=new Dictionary<string,double>() };
                            int dimensionCount=checked((int)reader.ReadUInt32());
                            for (int d=0; d<dimensionCount; d++) profile.Dimensions.Add(ReadString(reader),reader.ReadDouble());
                            int modeCount=checked((int)reader.ReadUInt32());
                            profile.Modes=new ModeData[modeCount];
                            for (int m=0; m<modeCount; m++)
                            {
                                var mode=new ModeData { Id=ReadString(reader),Label=ReadString(reader) };
                                int segmentCount=checked((int)reader.ReadUInt32());
                                mode.Segments=new SegmentData[segmentCount];
                                for (int s=0; s<segmentCount; s++)
                                    mode.Segments[s]=new SegmentData { IsArc=reader.ReadByte()!=0,
                                        X0=reader.ReadDouble(),Y0=reader.ReadDouble(),
                                        Xm=reader.ReadDouble(),Ym=reader.ReadDouble(),
                                        X1=reader.ReadDouble(),Y1=reader.ReadDouble() };
                                profile.Modes[m]=mode;
                            }
                            family.Profiles[p]=profile;
                        }
                        families[f]=family;
                    }
                    if (stream.Position!=stream.Length) throw new InvalidDataException("Trailing profile data");
                    return families;
                }
            }
        }
    }
}
