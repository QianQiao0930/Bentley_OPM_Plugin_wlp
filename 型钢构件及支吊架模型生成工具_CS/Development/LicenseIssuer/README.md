# 离线授权：作者签发指南

这是作者端工具，不是发给用户的插件。基于 .NET Framework 4.8 自带 RSA-2048 / SHA-256，无服务器、账户或额外包。

## 使用

1. 双击 `bin/Release/net48/SteelSupportLicenseIssuer.exe`。
2. 私钥默认从本工具源码目录的 `private-key.xml` 加载；移动工具后可点“选择私钥文件”重新指定。
3. 选择授权类型：**永久授权（绑定机器）**、**一个月试用（无需机器码）**或**90 天试用（无需机器码）**。
4. 永久授权需要粘贴机器码；试用模式自动禁用机器码输入。三种类型都可填写授权用户名。
5. 点“生成激活码 / 试用码”，核对到期说明，再点“复制激活码”，发给用户。
6. 用户在插件激活页粘贴整段授权码，点“激活 / 启用试用”，成功后返回首页。

授权码为长文本，允许换行和空格。永久授权保持原有机器绑定、长期有效；两种试用码均不绑定任何机器，同一个码可在不同电脑使用。

## 试用规则：一个月 / 90 天

- 有效期从**作者签发时刻**起算一个自然月，不从用户导入时起算。例：10 月 11 日 15:00 签发，11 月 11 日 15:00 到期；1 月 31 日签发会落到 2 月最后一天，闰年也按自然月计算。
- 选择 **90 天试用**时，有效期为签发时刻加 90 × 24 小时，不是三个自然月。例如 2026-10-11 15:00 签发，2027-01-09 15:00 到期（同一时区）。
- 90 天码使用版本 3 的签名载荷，包含 `trialDays=90`；自然月码继续采用版本 2，永久码继续采用版本 1。原密钥保持不变，旧永久码及一个月码仍有效。用户需更新到支持 90 天码的新版 DLL，旧 DLL 不识别新类型。
- 起止时刻以 UTC 签名保存，界面转换为电脑本地时间显示。签发时刻生效，到期时刻即失效。
- 试用中开放全部功能，首页显示“试用中”，激活页显示到期时间；到期显示“未激活”。工作区每秒检查缓存有效期，通过正常离开页面的生命周期退出点取并清理未确认预览。宿主长时间同步建模时须等 UI 恢复调度。
- 重启、复制到其他电脑、重新导入或删除再导入同一个码，不能改变签名内的到期时间。
- 输入永久码可升级试用；试用码不能覆盖已有永久授权。旧版永久码仍兼容，公钥与私钥没有更换。
- 没有机器码也能导入试用码，即使 Windows 安装标识读取失败也不会阻断免机器码试用。
- 纯离线试用依赖电脑系统时间，校验会拒绝早于签发时间的日期；没有联网可信时钟，也没有系统时间高水位防回拨，**无法彻底防止把系统时间改回有效期内来继续试用**。不提供在线撤销或分发数量限制；通用码可能被转发。

首页右上角版本按钮进入“关于与联系作者”，显示魏、`yo196544wobi@163.com`，可复制邮箱或请求打开默认邮件程序，程序不自动发送邮件。未激活或到期后仍可进入作者页和激活页。

## 密钥保护

- 作者私钥：本目录 `private-key.xml`，已经生成，已通过本目录 `.gitignore` 排除，文件 ACL 仅允许创建它的 Windows 用户和 SYSTEM 访问。
- 插件公钥：`../../Resources/license_public_key.xml`，嵌入插件和签发工具，可提交并分发。
- **请现在把私钥备份到你控制的安全位置。不要发给用户、提交 Git，或与 DLL 一起打包。** 整个开发目录也不应直接发给用户。
- 不得重新生成或覆盖现有密钥。永久激活码依赖这对密钥；更换公钥会使旧码失效。
- 签发器会检查私钥是否与编译时嵌入的产品公钥配对，防止误选其他密钥。
- 生成初始化密钥的命令只用于全新产品的首次部署，不是日常签发操作。正常编译不会生成新密钥。初始化遇到任一密钥已存在会拒绝覆盖。
- 克隆仓库没有私钥是预期行为：可以编译客户端，但不能签发。恢复作者私钥备份才能继续签发。

## 用户端与限制

用户只需要新版 `SteelSectionProbe.dll` 和永久激活码或通用试用码。授权保存到 `%LOCALAPPDATA%/SteelSectionProbe/license/activation.txt`，写入前先验签，写入失败不会解锁；首次加载自动复验，模型交互期间使用缓存，不反复验签；试用的有效状态实时按当前时间判断。

机器码由 Windows 安装标识 MachineGuid 派生，不读取网络服务。同一系统内硬件升级通常不变；重装 Windows 或更换电脑可能需要重新签发。不同 Windows 用户要分别导入同一台电脑的激活码。克隆 Windows 安装标识也会复制机器身份，本方案不提供硬件级防克隆。

纯离线永久授权没有远程撤销、设备数量在线追踪或在线封禁。签名用于防止自行伪造有效码；它无法阻止有能力者修改客户端 DLL 绕过校验。

## 编译与检查

在工程目录执行：

```powershell
dotnet build Development/LicenseIssuer/LicenseIssuer.csproj -c Release
dotnet build SteelSupportModeler.csproj -c Release -p:OutDir=bin\Release\net48_full\
dotnet run --project Development/LicenseCheck/LicenseCheck.csproj -c Release -- `
  "$PWD/Development/LicenseIssuer/private-key.xml" "$PWD/Resources/license_public_key.xml" `
  "$PWD/bin/Release/net48_full/SteelSectionProbe.dll"
dotnet run --project Development/LicenseUiCheck/LicenseUiCheck.csproj -c Release -- "$PWD"
```

`LicenseCheck` 的 125 项检查覆盖签名、格式、机器绑定、原子保存、损坏文件、重启、永久码兼容、免机器码试用、一个月和 90 天签发/到期边界、期限校验、月底/闰年/跨年、一份码用于多台电脑、到期不重启、重新导入不延期、试用升级永久、签发器配对及实际 DLL 公钥/初始化。私钥仅用于签发器配对自检，不输出私钥或激活真实用户目录。不提供参数也可用临时测试密钥运行核心检查。

`LicenseUiCheck` 使用实际首页、激活页、作者页 XAML 和公共主题离线渲染，移除事件处理器后检查三种窗口宽度、三种授权状态的按钮边界；不代表 Bentley 宿主中的完整交互验证。

## 回退到未授权版本

改动前已经提交基线：`f301ea5c470f33b230cab6fb89632ab10e9f829d`，提交说明“V0.0.3 未加入授权功能的基线版本”。源码需要回退时可从该提交创建单独工作区，保留当前开发成果。

未授权 DLL 已另存至工程 `bin/Baselines/V0.0.3_Unlicensed/SteelSectionProbe.dll`，SHA256：

```text
6D29FFA5170D8556B5002422ABBF93839C3B44C4E0B5C710A1F1C2A2FA75576C
```

关闭 OPM 后，将该 DLL 复制回 `bin/Release/net48/SteelSectionProbe.dll` 即可恢复原版。该备份仅供作者回退，不随授权版分发。

## 授权版与无授权版

插件主工程新增 `EnableLicensing` 编译属性，默认 true；设为 false 可编译无授权版。签发器本身仍按原逻辑签名，不受插件构建属性影响。详细命令及产物目录见工程根目录 README 的“授权编译开关”。

双构建检查增加无授权版 DLL 参数（138 项检查）：

```powershell
dotnet run --project Development/LicenseCheck/LicenseCheck.csproj -c Release -- `
  "$PWD/Development/LicenseIssuer/private-key.xml" "$PWD/Resources/license_public_key.xml" `
  "$PWD/bin/Release/net48_full/SteelSectionProbe.dll" "$PWD/bin/Release/Unlicensed/SteelSectionProbe.dll"
```

检查默认授权开关、无授权版直接可用、不处于试用状态，并确认激活页、验签、机器标识、存储类型及公钥未编入无授权版。原 125 项授权检查仍保留。
