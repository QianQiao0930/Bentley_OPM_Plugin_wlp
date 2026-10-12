using System;
using System.Drawing;
using System.IO;
using System.Windows.Forms;

namespace SteelSectionProbe
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            if (args.Length == 3 && args[0] == "--initialize")
            {
                LicenseSigner.InitializeKeys(args[1], args[2]);
                return 0;
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new LicenseIssuerForm());
            return 0;
        }
    }

    /// <summary>
    /// 作者端签发窗口，无 Bentley 依赖，无网络访问。
    /// </summary>
    internal sealed class LicenseIssuerForm : Form
    {
        private readonly TextBox privateKeyText = new TextBox { ReadOnly = true, Dock = DockStyle.Fill };
        private readonly TextBox machineCodeText = new TextBox { Dock = DockStyle.Fill };
        private readonly TextBox userNameText = new TextBox { Text = "正式用户", Dock = DockStyle.Fill };
        private readonly ComboBox licenseTypeBox = new ComboBox
        {
            DropDownStyle = ComboBoxStyle.DropDownList,
            Dock = DockStyle.Fill
        };
        private readonly Label expiryText = new Label { Dock = DockStyle.Fill, AutoSize = true };
        private readonly TextBox activationCodeText = new TextBox
        {
            ReadOnly = true,
            Multiline = true,
            ScrollBars = ScrollBars.Vertical,
            Dock = DockStyle.Fill
        };

        internal LicenseIssuerForm()
        {
            Text = "离线激活码签发工具（仅供作者使用）";
            Font = new Font("Microsoft YaHei UI", 10);
            StartPosition = FormStartPosition.CenterScreen;
            MinimumSize = new Size(640, 580);
            ClientSize = new Size(740, 620);
            var layout = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                Padding = new Padding(20),
                ColumnCount = 2,
                RowCount = 11
            };
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 95));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            for (int row = 0; row < 11; row++)
            {
                layout.RowStyles.Add(new RowStyle(row == 8 ? SizeType.Percent : SizeType.Absolute,
                    row == 8 ? 100 : row == 0 ? 50 : 40));
            }

            var notice = new Label
            {
                Text = "永久授权绑定机器；一个月 / 90 天试用码无需机器码，从签发时刻开始计时。私钥仅供作者保存。",
                Dock = DockStyle.Fill
            };
            layout.Controls.Add(notice, 0, 0);
            layout.SetColumnSpan(notice, 2);
            AddField(layout, "授权私钥", privateKeyText, 1);
            var browse = new Button { Text = "选择私钥文件…", AutoSize = true };
            browse.Click += BrowseKey_Click;
            layout.Controls.Add(browse, 1, 2);
            licenseTypeBox.Items.AddRange(new object[] { "永久授权（绑定机器）", "一个月试用（无需机器码）", "90 天试用（无需机器码）" });
            licenseTypeBox.SelectedIndex = 0;
            AddField(layout, "授权类型", licenseTypeBox, 3);
            AddField(layout, "用户机器码", machineCodeText, 4);
            AddField(layout, "授权用户名", userNameText, 5);
            var generate = new Button { Text = "生成激活码 / 试用码", AutoSize = true };
            generate.Click += Generate_Click;
            layout.Controls.Add(generate, 1, 6);
            layout.Controls.Add(expiryText, 1, 7);
            AddField(layout, "授权码", activationCodeText, 8);
            var copy = new Button { Text = "复制激活码", AutoSize = true };
            copy.Click += Copy_Click;
            layout.Controls.Add(copy, 1, 9);
            Controls.Add(layout);

            string defaultKey = Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,
                "..", "..", "..", "private-key.xml"));
            if (File.Exists(defaultKey))
            {
                privateKeyText.Text = defaultKey;
            }

            // 修改输入后不能再复制上一位用户的激活码。
            privateKeyText.TextChanged += ClearCode;
            machineCodeText.TextChanged += ClearCode;
            userNameText.TextChanged += ClearCode;
            licenseTypeBox.SelectedIndexChanged += LicenseType_Changed;
        }

        private static void AddField(TableLayoutPanel layout, string title, Control field, int row)
        {
            layout.Controls.Add(new Label { Text = title, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft }, 0, row);
            layout.Controls.Add(field, 1, row);
        }

        private void ClearCode(object sender, EventArgs e)
        {
            activationCodeText.Clear();
            expiryText.Text = string.Empty;
        }

        private void LicenseType_Changed(object sender, EventArgs e)
        {
            machineCodeText.Enabled = licenseTypeBox.SelectedIndex == 0;
            ClearCode(sender, e);
        }

        private void BrowseKey_Click(object sender, EventArgs e)
        {
            using (var dialog = new OpenFileDialog { Filter = "授权私钥 (*.xml)|*.xml", Title = "选择作者私钥" })
            {
                if (dialog.ShowDialog(this) == DialogResult.OK)
                {
                    privateKeyText.Text = dialog.FileName;
                }
            }
        }

        private void Generate_Click(object sender, EventArgs e)
        {
            activationCodeText.Clear();
            try
            {
                bool isTrial = licenseTypeBox.SelectedIndex > 0;
                int trialDays = licenseTypeBox.SelectedIndex == 2 ? 90 : 0;
                activationCodeText.Text = LicenseSigner.Issue(privateKeyText.Text, machineCodeText.Text,
                    userNameText.Text, isTrial, trialDays);
                // 到期时间来自本次签名载荷，不按生成后的当前时刻另算。
                string publicKey;
                using (Stream stream = typeof(LicenseSigner).Assembly
                    .GetManifestResourceStream("SteelSectionProbe.license_public_key.xml"))
                using (var reader = new StreamReader(stream))
                {
                    publicKey = reader.ReadToEnd();
                }

                ActivationPayload payload = ActivationCodec.Verify(activationCodeText.Text, publicKey, machineCodeText.Text);
                expiryText.Text = isTrial ? "到期：" + DateTimeOffset.Parse(payload.ExpiresUtc)
                    .ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss") + (payload.TrialDays == 90 ? "（签发日起 90 天）" : "（签发日起一个自然月）")
                    : "永久授权，无到期日。";
            }
            catch (Exception exception)
            {
                MessageBox.Show(this, "签发失败：" + exception.Message, "签发激活码", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void Copy_Click(object sender, EventArgs e)
        {
            if (activationCodeText.Text.Length == 0)
            {
                return;
            }

            try
            {
                Clipboard.SetText(activationCodeText.Text);
                MessageBox.Show(this, "激活码已复制，可发送给对应用户。", "签发激活码");
            }
            catch (Exception exception)
            {
                MessageBox.Show(this, "复制失败，可手动选中复制：" + exception.Message, "签发激活码");
            }
        }
    }
}
