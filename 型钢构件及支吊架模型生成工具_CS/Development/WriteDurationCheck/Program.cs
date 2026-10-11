using System;
using System.Globalization;
using SteelSectionProbe;

int checks = 0;
void Equal(string actual, string expected)
{
    checks++;
    if (actual != expected) throw new Exception($"Expected {expected}, got {actual}");
}
foreach (string culture in new[] { "en-US", "zh-CN", "de-DE" })
{
    CultureInfo.CurrentCulture = new CultureInfo(culture);
    Equal(WriteDuration.Format(0), "0 ms");
    Equal(WriteDuration.Format(0.0001), "<0.001 ms");
    Equal(WriteDuration.Format(0.001), "0.001 ms");
    Equal(WriteDuration.Format(75.25), "75.25 ms");
    Equal(WriteDuration.Format(99.999), "99.999 ms");
    Equal(WriteDuration.Format(100), "0.1 s");
    Equal(WriteDuration.Format(125), "0.125 s");
    Equal(WriteDuration.Format(1234), "1.234 s");
}
foreach (double invalid in new[] { -1.0, double.NaN, double.PositiveInfinity, double.NegativeInfinity })
{
    try { WriteDuration.Format(invalid); throw new Exception("Invalid duration accepted"); }
    catch (ArgumentOutOfRangeException) { checks++; }
}
int calls = 0;
string measured = WriteDuration.Measure(() => { calls++; });
if (calls != 1 || string.IsNullOrEmpty(measured)) throw new Exception("Action measurement failed");
checks++;
string elapsed;
int result = WriteDuration.Measure(() => { calls++; return 42; }, out elapsed);
if (calls != 2 || result != 42 || string.IsNullOrEmpty(elapsed)) throw new Exception("Result measurement failed");
checks++;
var failure = new InvalidOperationException("write failed");
try { WriteDuration.Measure(() => { throw failure; }); throw new Exception("Write failure swallowed"); }
catch (InvalidOperationException ex) { if (!ReferenceEquals(ex, failure)) throw; checks++; }
try { WriteDuration.Measure((Action)null); throw new Exception("Null action accepted"); }
catch (ArgumentNullException) { checks++; }
Console.WriteLine($"WriteDurationCheck: {checks} checks passed.");
