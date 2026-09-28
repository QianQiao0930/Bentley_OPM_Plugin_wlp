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
                MainWindow.Current.ShowSteelSectionsPage();
                MainWindow.Current.SteelSections.Place();
            }
        }
    }
}
