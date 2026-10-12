namespace SteelSectionProbe
{
    public static class Keyins
    {
        public static void Show(string args)
        {
            MainWindow.ShowWindow();
        }

        public static void Place(string args)
        {
            MainWindow.ShowWindow();
            if (MainWindow.Current != null)
            {
                if (!LicenseService.IsActivated)
                {
                    MainWindow.Current.ShowActivationPage();
                    MainWindow.Current.SetStatus("请先激活软件，再放置型钢。", true);
                    return;
                }

                MainWindow.Current.ShowSteelSectionsPage();
                MainWindow.Current.SteelSections.Place();
            }
        }
    }
}
