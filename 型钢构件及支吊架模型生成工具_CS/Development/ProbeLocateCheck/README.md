# ProbeLocateCheck

Offline lifecycle regression for the **real** `ProbeLocateTool`, `TFrameLocateTool`,
`PipeClampLocateTool` and `LocatedElement` sources, linked directly into this executable.

```powershell
dotnet run --project Development/ProbeLocateCheck/ProbeLocateCheck.csproj -c Release
```

The minimal Bentley substitutes model the reported host behavior: a nonempty selection
at base installation populates the element agenda; a nonempty agenda or a set/fence
source routes the first click to element modification/restart instead of `DoLocate`.
The checks exercise the actual T-frame and pipe-clamp `Begin`, `OnDataButton`, `End`
and cleanup paths, including delayed cleanup and injected selection-clear failures.

The preview assertion verifies the single `Picked` callback that starts page preview
generation. It does not load WPF, create model geometry or replace OPM host acceptance.
Confirm in OPM that selecting a line first, pressing Start Picking, and clicking once
on the intended line creates the preview; ending picking must not restore old selection.
