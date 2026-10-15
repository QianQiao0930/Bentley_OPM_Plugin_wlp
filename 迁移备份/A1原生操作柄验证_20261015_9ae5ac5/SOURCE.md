# A1 原生编辑与随动独立验证

基线：9ae5ac5。原工作区仅有用户的未跟踪管道支吊架日志，本次保留。

source-before.zip 为该基线C#工程源码；*-SteelSectionProbe.dll/pdb 为改前常规/备用/无授权产物，SHA256-before.json 保存改前校验。

新增试验命令 STEELPROBE A1TEST NATIVE 与 CHECKEDIT。SSP_A1_NATIVE_TEST 使用自定义参数化组件及原生 Support handler；正式九类和旧 PLACE 不切换。实际原生操作柄、跟随、重生成、Undo/Redo与ISO提取均未在本次代理环境实测，须按项目 Docs/A1原生编辑与随动验证.md 操作。

用户确认保存关闭 OPM，并明确授权结束 PID 39876/55460 两个无窗口残留进程。只核验并结束这两个进程；Windows尚保留已退出进程记录，安装检查按HasExited排除。之后安装C盘CINF_F1263AA工作集三份schema；只各新增一类，原1362/630/242个节点逐项结构一致。D盘及其他工作集未改。

schema-preview.txt 为预览；schema-backup/ 内 .bak 为字节原件，A1-native-trial-*.json 收据含原路径、备份路径和修改前后哈希。回退须在OPM关闭后按收据恢复；若已有试验件，先保留对应DLL/schema以便编辑或删除。

验证：1942项A1适配器/API替身、6516项正式管夹集成替身、30项隔离Schema安装、16项原引注映射。替身不模拟操作柄或自动跟随。主工程使用本机C盘OpenPlant 2024 SDK编译；最终产物校验见SHA256-after.json。
