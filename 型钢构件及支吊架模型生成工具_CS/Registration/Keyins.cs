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

        /// <summary>
        /// 把选中设备的图形图元批量改到当前活动图层。
        /// 只处理 ElementType = Equipment 的普通单元，其余元素一律跳过。
        /// </summary>
        public static void EquipmentLevel(string args)
        {
            EquipmentLevelCommand.Run();
        }

        /// <summary>
        /// 只读探测：把选中元素能否取到图形图元的各条通道全部写进日志。
        /// </summary>
        public static void EquipmentProbe(string args)
        {
            EquipmentLevelProbe.Run();
        }
    }
}
