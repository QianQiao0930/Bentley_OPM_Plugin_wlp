using System;
using System.Collections.Generic;
using Bentley.ECObjects.Instance;

namespace Bentley.Building.Mechanical.ComponentLibrary.Supports
{
    public class Supports
    {
        public SteelSectionProbe.ParametricSetupValues BMECObject;
        internal int HostCalls, LengthCalls;
        internal double SupportLength;
        public virtual void Setup() { }
        protected bool SetPipeDiameter() { HostCalls++; return BMECObject.ParentReady; }
        protected void SetSupportLength(double length) { LengthCalls++; SupportLength = length; }
    }
}

namespace SteelSectionProbe
{
    public sealed class ParametricSetupValues
    {
        internal IECInstance Source;
        internal bool ParentReady;
        public int GetIntValue(string name) { return Source[name].IntValue; }
        public double GetUnitlessDoubleValue(string name) { return Source[name].DoubleValue; }
        public string GetStringValue(string name) { return Source[name].StringValue; }
    }

    // Completes the real production Setup partial without loading the native graphics bridge.
#if A1_NATIVE_SETUP_CHECK
    public sealed partial class A1NativeParametricComponent : Bentley.Building.Mechanical.ComponentLibrary.Supports.Supports
    {
        internal static readonly List<string> SetupFailures = new List<string>();
        internal A1ClampPlan PlanForCheck { get { return plan; } }
        private static void SaveTrace(string trace) { SetupFailures.Add(trace); }
    }
#endif
}
