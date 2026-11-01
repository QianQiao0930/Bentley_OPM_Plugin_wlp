# OPM 实体管口生成器（首版）

这是一个在 Bentley OpenPlant Modeler 的 PowerPlatform Python 环境中运行的可视化实体插件。它不创建 OPM 管道组件、不接入材料表，也不做压力校核。

## 已实现

- PyQt5 参数窗口：CL150 法兰等级、钢管系列、DN、可手动覆盖的钢管壁厚、管口总长度，以及 +X / -X / +Y / -Y / +Z / -Z 六个放置方向。
- 选择“开始放置”后，在三维模型中点取基点；实体沿所选轴的正方向生成。
- 管段：闭合圆轮廓拉伸后，使用 `SolidUtil.Modify.HollowFaces` 生成双端开口的空心管。
- 法兰盘和 2 mm 密封面凸台：分别由圆轮廓拉伸生成。
- 使用 `SolidUtil.Modify.BooleanUnion` 把管段、法兰和凸台相并为一个 SmartSolid。
- 切除中心通孔；“绘制螺栓孔”默认关闭，启用后才按 K、L、n 参数创建法兰螺栓孔。
- 管口总长度 = 钢管名义长度 + 法兰厚度 C；钢管名义长度自动按“总长度 − C”计算。

## 安装与运行

1. 将本目录整体复制到 OPM 的 PowerPlatform Python 脚本目录，或在 OPM 的 Python Manager 中打开 [NozzleGenerator.py](NozzleGenerator.py)。
2. 确认当前为三维设计模型。
3. 运行 `NozzleGenerator.py` 的 `Run()`。
4. 设置参数，点击“开始放置”，再在模型中点击基点。相同参数可连续放置；Reset 可结束放置工具。

## 尺寸数据

[flange_data.json](flange_data.json) 与建模逻辑完全分离。当前包含用户提供的 CL150 法兰连接尺寸（DN15–DN1500）以及两套钢管系列：`Ia_Sch10` 和 `Ia_large_dia_welded_wall12.5`。界面只显示同时具有法兰和对应钢管壁厚数据的 DN，防止错误组合。

数据未给出密封面尺寸，因此当前不生成密封面凸台。其他已提供尺寸均直接参与建模；螺栓孔由 K、L、n 数据生成。

## 后续建议

- 接收你的 GB/T、HG/T 或企业标准数据，扩展 DN/PN 组合。
- 增加轴向、径向或由用户拾取参考面定义的放置方向。
- 增加螺栓孔、法兰型式和焊接坡口。
