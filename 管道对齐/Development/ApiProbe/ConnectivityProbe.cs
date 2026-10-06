// 仅编译，不执行。排除历史上不可消费的原生接口探针：
// dotnet build ApiProbe.csproj -c Release /p:ConnectivityOnly=true
using Bentley.ECObjects.Instance;
using Bentley.OpenPlant.Modeler.Api;
using Bentley.DgnPlatformNET;

namespace PipeAlignApiProbe
{
    internal static class ConnectivityProbe
    {
        internal static void Touch(BMECObject component, int portId, IECInstance port)
        {
            BMECObject neighbor = component.GetConnectedComponentAtPort(portId);
            IECInstance owner = BMECApi.Instance.GetPortOwnerComponent(port);
            IECInstance cached = neighbor == null ? null : neighbor.Instance;
            System.Console.WriteLine(owner == null || cached == null);
            double minimumMm = BMECApi.GetMinimumPipeLengthInMM(component);
            bool active = TransactionManager.IsActive;
            TransactionManager.CloseCurrentTransaction(true);
            TransactionPosition mark = TransactionManager.CurrentTransactionPosition;
            StatusInt cancelled = TransactionManager.CancelToPosition(mark, false);
            System.Console.WriteLine(minimumMm + " " + active + " " + cancelled);
        }
    }
}
