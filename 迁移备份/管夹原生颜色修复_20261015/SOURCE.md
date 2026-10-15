颜色修复：2026-10-15
用户授权：修改原生管夹全部变蓝的问题。
修复：正式/A1回调不再调用Supports.SetTypeAndSymbology；共用NativeParametricSupportGraphics仅设置三维Edge分类，保留Builder分件外观。
备份：source-before.zip为修改前项目源码；原三套产物、宿主DLL/PDB和最新正式日志已保存，校验见SHA256-before.json。
验证：10318项正式+1952项A1 API替身回归通过；授权/无授权Release均0警告0错误。真实OPM显示与编辑后颜色仍需复测。
授权版MVID=e673daa7-9018-4f2f-ad97-5c82e6f7b733
授权版SHA256=946F553263A493000E6E23B640F6F24B12E595099C0E1B2A24BEBDE12E38CD3A
Schema未修改。首次宿主更新在运行进程检查处停止，未写宿主文件；部署完成以mdlapps-deployment.json为准。

用户确认关闭OPM后，2026-10-15T11:28:21+08:00已完成宿主DLL/PDB更新，SHA256与授权产物一致；详见mdlapps-deployment.json。
