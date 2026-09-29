using System;
using System.Collections.Generic;
using System.IO;
using System.Web.Script.Serialization;
using System.Windows.Controls;

namespace SteelSectionProbe
{
    /// <summary>保存页面参数控件的值；模型选择、预览与操作状态不写入偏好。</summary>
    internal static class PageLastInput
    {
        private static string FilePath(string pageId)
        {
            return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "SteelSectionProbe", pageId + "_last_input.json");
        }

        internal static void Save(UserControl page, string pageId, params string[] names)
        {
            try
            {
                var values = new Dictionary<string, string>();
                foreach (string name in names)
                {
                    var combo = page.FindName(name) as ComboBox;
                    if (combo != null) { values[name] = combo.SelectedIndex.ToString(); continue; }
                    var input = page.FindName(name) as TextBox;
                    if (input != null) { values[name] = input.Text ?? ""; continue; }
                    var check = page.FindName(name) as CheckBox;
                    if (check != null) values[name] = check.IsChecked == true ? "true" : "false";
                }
                string path = FilePath(pageId);
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                File.WriteAllText(path, new JavaScriptSerializer().Serialize(values));
            }
            catch { /* 偏好写入失败不得影响建模或关闭页面。 */ }
        }

        /// <summary>按传入顺序恢复，以便先恢复类别，再恢复依赖类别的子项。</summary>
        internal static void Restore(UserControl page, string pageId, params string[] names)
        {
            try
            {
                string path = FilePath(pageId);
                if (!File.Exists(path)) return;
                var values = new JavaScriptSerializer().Deserialize<Dictionary<string, string>>(
                    File.ReadAllText(path));
                if (values == null) return;
                foreach (string name in names)
                {
                    string value;
                    if (!values.TryGetValue(name, out value) || value == null) continue;
                    var combo = page.FindName(name) as ComboBox;
                    if (combo != null)
                    {
                        int index;
                        if (int.TryParse(value, out index) && index >= 0 && index < combo.Items.Count)
                            combo.SelectedIndex = index;
                        continue;
                    }
                    var input = page.FindName(name) as TextBox;
                    if (input != null) { if (value.Length <= 1000) input.Text = value; continue; }
                    var check = page.FindName(name) as CheckBox;
                    if (check != null)
                    {
                        bool selected;
                        if (bool.TryParse(value, out selected)) check.IsChecked = selected;
                    }
                }
            }
            catch { /* 旧版或损坏的偏好回退到页面默认值。 */ }
        }
    }
}
