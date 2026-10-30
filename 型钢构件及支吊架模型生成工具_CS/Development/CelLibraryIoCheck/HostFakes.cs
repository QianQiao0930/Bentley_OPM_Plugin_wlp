using System;
using System.Collections.Generic;

namespace Bentley.GeometryNET
{
    public struct DPoint3d
    {
        public double X, Y, Z;
        public static DPoint3d Zero { get { return new DPoint3d(); } }
        public DPoint3d(double x, double y, double z) { X = x; Y = y; Z = z; }
    }
}
namespace Bentley.MstnPlatformNET
{
    public sealed class FakeModel { public bool Is3d = true; }
    public sealed class Session
    {
        public static readonly Session Instance = new Session();
        public FakeModel Model = new FakeModel();
        public FakeModel GetActiveDgnModel() { return Model; }
    }
}
namespace Bentley.MstnPlatformNET.InteropServices
{
    public static class Utilities
    {
        public static bool IsMicroStationMainThread = true;
        public static Bentley.Interop.MicroStationDGN.Application ComApp;
    }
}
namespace Bentley.Interop.MicroStationDGN
{
    public struct Point3d { public double X, Y, Z; }
    public struct Matrix3d { public int Axis; public double Radians; }
    public struct MeasurementUnit { public string Label; }
    public enum MsdCellType { Graphic, Menu, Point }
    public enum MsdConversionMode { Never, Always, Prompt }
    public sealed class ModelReference
    {
        public bool Is3D = true, CanBePlacedAsCell = true;
        public MsdCellType CellType = MsdCellType.Graphic;
        public string Name = "盘管", Description = "测试盘管";
        public double UORsPerMasterUnit = 1000;
        public Point3d GlobalOrigin;
        public MeasurementUnit get_MasterUnit() { return new MeasurementUnit { Label = "mm" }; }
    }
    public sealed class DesignFile
    {
        public string FullName;
        public List<ModelReference> Models = new List<ModelReference>();
        public bool Closed, FailClose;
        public void Close() { Closed = true; if (FailClose) throw new InvalidOperationException("close fault"); }
    }
    public sealed class CellLibrary { public string FullName; }
    public sealed class CellElement
    {
        public bool IsValid = true, IsNew = true, Ordinary = true;
        public string Name;
        public Point3d Origin;
        public bool IsCellElement() { return Ordinary; }
    }
    public sealed class Application
    {
        public bool HasActiveDesignFile = true, HasActiveModelReference = true;
        public DesignFile ActiveDesignFile = new DesignFile();
        public ModelReference ActiveModelReference = new ModelReference { UORsPerMasterUnit = 10000 };
        public CellLibrary AttachedCellLibrary;
        public DesignFile Library = new DesignFile();
        public bool IsCellLibraryAttached { get { return AttachedCellLibrary != null; } }
        public bool FailOpen, FailCreate, FailDetach, ReturnWrongOrigin;
        public string FailAttachPath, FailAttachAfterChangePath;
        public int AttachCalls, DetachCalls, CreateCalls, OpenCalls;
        public bool OpenReadOnly, UsedTrueScale;
        public string OpenPath, CreatedName;
        public Point3d CreatedOrigin, CreatedScale;
        public Matrix3d CreatedRotation;
        public DesignFile OpenDesignFileForProgram(string path, bool readOnly)
        { OpenCalls++; OpenPath = path; OpenReadOnly = readOnly; if (FailOpen) throw new InvalidOperationException("open fault"); return Library; }
        public void AttachCellLibrary(string path, MsdConversionMode conversion)
        {
            AttachCalls++;
            if (conversion != MsdConversionMode.Never) throw new InvalidOperationException("source conversion forbidden");
            if (path == FailAttachPath) throw new InvalidOperationException("attach fault");
            AttachedCellLibrary = new CellLibrary { FullName = path };
            if (path == FailAttachAfterChangePath) throw new InvalidOperationException("partial attach fault");
        }
        public void DetachCellLibrary() { DetachCalls++; if (FailDetach) throw new InvalidOperationException("detach fault"); AttachedCellLibrary = null; }
        public Matrix3d Matrix3dFromAxisAndRotationAngle(int axis, double radians) { return new Matrix3d { Axis = axis, Radians = radians }; }
        public CellElement CreateCellElement2(string name, ref Point3d origin, ref Point3d scale, bool trueScale, ref Matrix3d rotation)
        {
            CreateCalls++; CreatedName = name; CreatedOrigin = origin; CreatedScale = scale; UsedTrueScale = trueScale; CreatedRotation = rotation;
            if (FailCreate) throw new InvalidOperationException("create fault");
            var actual = origin; if (ReturnWrongOrigin) actual.X += 2;
            return new CellElement { Name = name, Origin = actual };
        }
    }
}
