using System;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Markup;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Xml.Linq;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            string project = Path.GetFullPath(args[0]);
            string output = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "previews");
            Directory.CreateDirectory(output);
            UserControl home = LoadPage(Path.Combine(project, "UI", "HomePage.xaml"));
            var activationButton = (Button)home.FindName("ActivationButton");
            var sortBox = (ComboBox)home.FindName("SortBox");
            ((TextBlock)home.FindName("VersionText")).Text = "V0.0.3";
            ((TextBlock)home.FindName("AuthorText")).Text = "· 作者：魏";
            sortBox.SelectedIndex = 0;
            foreach (int width in new[] { 520, 640, 840 })
            {
                foreach (string state in new[] { "未激活", "已激活", "试用中" })
                {
                    activationButton.Content = state;
                    Arrange(home, width, 650);
                    Point activationEnd = activationButton.TranslatePoint(new Point(activationButton.ActualWidth, 0), home);
                    var search = (TextBox)home.FindName("SearchBox");
                    Point searchStart = search.TranslatePoint(new Point(0, 0), home);
                    if (activationEnd.X + 4 > searchStart.X)
                    {
                        throw new InvalidOperationException("首页授权按钮与搜索框重叠：" + width);
                    }

                    var aboutButton = (Button)home.FindName("AboutButton");
                    Point aboutEnd = aboutButton.TranslatePoint(new Point(aboutButton.ActualWidth, 0), home);
                    if (aboutButton.ActualWidth < 100 || aboutEnd.X > width + 1)
                    {
                        throw new InvalidOperationException("版本与作者按钮超出首页边界：" + width);
                    }
                }
            }

            activationButton.Content = "未激活";
            Arrange(home, 640, 650);
            Save(home, Path.Combine(output, "home-activation.png"), 640, 650);
            UserControl page = LoadPage(Path.Combine(project, "UI", "Licensing", "ActivationPage.xaml"));
            ((TextBlock)page.FindName("ActivationStatusText")).Text = "未激活";
            ((TextBlock)page.FindName("LicenseInfoText")).Text = "尚未激活，请复制机器码向软件作者申请激活码。";
            ((TextBox)page.FindName("MachineCodeText")).Text = "SSP-01234567-89ABCDEF-01234567-89ABCDEF";
            Arrange(page, 520, 650);
            var machine = (TextBox)page.FindName("MachineCodeText");
            var copy = (Button)page.FindName("CopyMachineButton");
            if (machine.ActualWidth < 300 || copy.ActualWidth < 80)
            {
                throw new InvalidOperationException("激活页机器码或复制按钮空间不足。");
            }

            Save(page, Path.Combine(output, "activation-page.png"), 520, 650);
            UserControl about = LoadPage(Path.Combine(project, "UI", "About", "AboutPage.xaml"));
            ((TextBlock)about.FindName("VersionText")).Text = "V0.0.3";
            ((TextBlock)about.FindName("AuthorText")).Text = "作者：魏";
            ((TextBox)about.FindName("EmailText")).Text = "yo196544wobi@163.com";
            Arrange(about, 520, 650);
            Save(about, Path.Combine(output, "about-page.png"), 520, 650);
            Console.WriteLine("PASS: WPF themes, about and trial layouts at 520 / 640 / 840 px. " + output);
            return 0;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(exception);
            return 1;
        }
    }

    private static UserControl LoadPage(string filePath)
    {
        XDocument document = XDocument.Load(filePath);
        XNamespace xaml = "http://schemas.microsoft.com/winfx/2006/xaml";
        document.Root.Attribute(xaml + "Class").Remove();
        document.Root.Attribute(xaml + "ClassModifier")?.Remove();
        string[] handlers = { "Click", "TextChanged", "SelectionChanged", "ContextMenuOpening" };
        foreach (XElement element in document.Descendants())
        {
            foreach (XAttribute attribute in element.Attributes().Where(value => handlers.Contains(value.Name.LocalName)).ToArray())
            {
                attribute.Remove();
            }

            if (element.Name.LocalName == "ResourceDictionary" && element.Attribute("Source") != null)
            {
                element.Attribute("Source").Value = new Uri(Path.GetFullPath(Path.Combine(
                    Path.GetDirectoryName(filePath), element.Attribute("Source").Value))).AbsoluteUri;
            }
        }

        return (UserControl)XamlReader.Parse(document.ToString());
    }

    private static void Arrange(FrameworkElement element, int width, int height)
    {
        element.Measure(new Size(width, height));
        element.Arrange(new Rect(0, 0, width, height));
        element.UpdateLayout();
    }

    private static void Save(FrameworkElement element, string path, int width, int height)
    {
        var bitmap = new RenderTargetBitmap(width, height, 96, 96, PixelFormats.Pbgra32);
        bitmap.Render(element);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(bitmap));
        using (Stream stream = File.Create(path))
        {
            encoder.Save(stream);
        }
    }
}
