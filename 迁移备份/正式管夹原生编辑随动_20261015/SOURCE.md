# 正式管夹原生编辑与随动接入

接入前用户确认A1初始化修复版实测正常。保存的latest.log证实修复版MVID b565a3e8-beef-45c1-9eec-45e1f6a3d9d7、Create=0、父管关系、初始三维与ISO点误差0、Design/SHOP；component-latest.log证实后续操作的几何回调成功。移动后ISO/Undo/重开完整验收未据日志确认。

source-before.zip为本轮改动前真实工作区源码（含尚未提交的A1组件及初始化修复）；三配置DLL/PDB、宿主mdlapps原DLL及成功日志一并备份，SHA256-before.json保存原产物。原有用户未跟踪管道支吊架日志保留。

正式九类新放原生PIPE统一使用SSP_PIPE_CLAMP，继承SUPPORT_LOCATION并存完整SSP_RECIPE配方；Support处理器及参数化组件复用A1的初始化时序、离线图形桥接和ISO点同步。原Builder、材料编号、参考体选项、预览/确认/授权和失败回滚保持，旧模型不迁移。

用户保存关闭OPM并授权完成部署后，向C盘CINF_F1263AA基础/Modeling/Isoextractor各新增一类，原1363/631/243节点逐项结构比较保持。schema-backup内字节备份和SSP_PIPE_CLAMP-*.json收据用于回退；不改软件自带或旧A1试验类。D盘及其他工作集未修改。

正式版授权/无授权C盘SDK编译均0警告0错误；10318项正式会话/配方/重生成采样/初始化/回滚检查、1952项A1、31项正式及30项A1 Schema、16项原引注部署检查通过。API替身不执行实际扫掠、操作柄、自动随动、ISO或Undo。正常/备用DLL/PDB及宿主授权副本校验见SHA256-after.json和mdlapps-deployment.json。

正式MVID f2719cdf-3542-4fb9-a72e-ae2145fa0b52；授权DLL SHA256 CC5C3AD638FF223CAE40425233ACF31A81E34DC97507E7E00175BA392850BDC3。重启后在正式页面新放，逐类宿主核对。规范位于工程Docs/正式管夹原生编辑与随动.md。
