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
                    MainWindow.Current.SetStatus("请先激活软件，再使用型钢生成。", true);
                    return;
                }

                MainWindow.Current.ShowSteelSectionsPage();
            }
        }

        public static void Query(string args)
        {
            MainWindow.ShowWindow();
            if (MainWindow.Current != null)
            {
                MainWindow.Current.ShowComponentPropertiesPage();
            }
        }
    }
}
