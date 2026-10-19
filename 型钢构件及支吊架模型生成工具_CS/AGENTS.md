# 型钢构件及支吊架模型生成工具：AI 与开发者协作规范

当前版本：V1.0.0（程序集/文件版本1.0.0.0；唯一来源App/AssemblyInfo.cs，首页及作者页自动读取）。

2026-10-17直线点取区固定精简：LineCoordinatesPage将SelectionCard移出ParameterScroll，位于顶部Auto行，坐标/快速对齐在中间滚动，底部OperationCard保持固定。点取区约72 DIP，第一行标题与点取/结束按钮，第二行只读选择状态与毫米/模型XYZ单位；原说明移至悬停提示，长选择状态单行显示、悬停查看全文。具名控件、默认值、事件及业务源码保持。ToolPagesUiCheck 201项（新增点取区高度和滚动固定检查）、LineCoordinatesCheck 93项通过，授权/无授权Release均0警告0错误，常规/备用DLL同步；OPM宿主尚未实测。改前源码/原型/DLL/PDB及SHA256位于仓库迁移备份/直线点取区固定精简_20261017。

2026-10-17墙面爬梯参数双列：WallLadderPage五个填写框按原顺序从左到右、从上到下排布，梯宽/距墙、最低横担离地/支架间距各一行，方向角在第三行左侧；两列等宽、间距10，同行标题和输入分别共享Auto行，标题换行不影响输入对齐，护笼勾选保持整行。仅调整XAML布局，原字段/默认值/事件及业务源码保持。ModelingUiCheck 406项、WallLadderCheck 12372项通过；授权/无授权Release均0警告0错误，常规/备用DLL已同步。OPM宿主界面尚未实测。改前源码/原型/DLL/PDB与SHA256位于仓库迁移备份/墙面爬梯双列布局_20261017，源码基线7eb5679。

2026-10-15直线坐标显示与快速对齐措辞：坐标框改为显示2位小数（LineCoordinateCalculator.Display，0.##）；应用修改时未编辑字段沿用精确值——字段文本与显示值逐字一致即视为未改动，避免只改一项时把其余五项舍入；G17的Format保留供往返精度与检查使用。四个正交按钮改为按结果分组的措辞（竖直线·两端X/Y对齐 / 水平线·两端Z对齐，各「终点贴起点」「起点贴终点」），「对齐到管道…」改「贴合到管道底标高…」；控件名、事件与只填草稿的行为不变。LineCoordinatesCheck 93项、ToolPagesUiCheck 199项通过；授权Release 0警告0错误。宿主显示与真实写回仍需OPM实测。

2026-10-15支吊架Schema安装合并为单实现：Deployment/Install-NativeSupportEditing.ps1 现在是唯一的 Schema 修改实现（`-Features All|Trunnion|PipeClamp`），一次遍历三份 schema、共用一份备份/替换/回滚/收据，写入自带耳轴三类（SSP_RECIPE/参数化组件/IE_TAG=ALIAS）与正式管夹隔离类 SSP_PIPE_CLAMP。原 Install-NativeSupportSchema.ps1、Install-TrunnionStockParametric.ps1、Install-TrunnionNativeEditing.ps1、Install-PipeClampNativeEditing.ps1、Install-TrunnionStockIsoTag.ps1 已删除（含旧 -Mode Trunnion 隔离类方案）；离线检查直接调用本脚本并显式传 -Features。默认只读预览，关OPM后 -Apply，写前SHA256备份、部分失败回滚、重复幂等。工作集 CINF_F1263AA 实测两套类均已就位；旧的无配方耳轴件与非参数化管夹件须删除后重放。备份/收据在 迁移备份/耳轴Schema安装_20261015 与 迁移备份/管夹Schema安装_20261015。

2026-10-15直线坐标快速对齐：直线坐标修改页起点/终点改一行两列，标题中「起点」「终点」15号加粗#1F6FEB突出；新增“04 快速对齐”卡四个正交按钮（按起点/终点对齐竖直线：另一端XY贴合锚点端、各自Z保持；按起点/终点对齐水平线：另一端Z贴合锚点端）与“对齐到管道”。按钮只按规则**重新填写两端草稿坐标**、不写模型，写回仍走应用修改的完整校验/独立Undo/耗时状态；快速对齐工具与直线点取互斥，离开/关闭/撤销规则不变。对齐到管道：新增Tools层LineCoordinatePipeTool（活动模型管道定位，OnPostLocate拒绝参考/附件，ev.Point写入LocatedElement.Click），Data层LineCoordinatePipeReader复用管道对齐模块PipeElementReader的EC读取（只读轴线/外径/管号，probe与日志传空，不探测连接与移动能力），管线Or外径读不到明确拒绝不猜。Services层LinePipeAlign纯计算：水平/竖直判据为分量≤线长×1e-6；水平线+水平管→两端Z=Floor(轴线低端标高−外径/2)（底标高不含保温，提示注明）；竖直线→两端XY=点取位置（毫米）、终点Z=同式取整、起点Z保持；零长、斜线、二维、点取坐标非有限、水平线遇立管均拒绝并给中文原因。Domain新增LinePipeSurvey。LineCoordinatesCheck扩展至93项、ToolPagesUiCheck直线页扩展（199项总数）通过；授权/无授权Release 0警告0错误。ev.Point坐标系、真实管道EC读取与写入随动仍需OPM实测；管道底标高口径若需含保温需另行授权修改。改前源码备份在迁移备份/直线坐标快速对齐_20261015。

2026-10-15组合绑定换行：轴测NOTE模板为$(IE_TAG)，ALIAS里单个$紧挨(2)会被当成属性删掉，编号粘成一行。组合引注改用$$分行，与样式R=$(BRADIUS)$$(BANGLE)相同。已保存绑定须重新保存后再出图。用户确认整体功能及ISO多行框良好，截图圈码变问号、承重钢构未进ISO材料表。当前序号改ASCII(1)/(2)，旧Version1绑定重新保存即可换码。用户明确共架由最大公称管径管道计材料，其余只引用编号；同架允许多管夹引用，不重复建钢构。新增OpenPlant/SupportBinding/SupportBindingMaterials，沿用工作集ADDITIONAL_MATERIAL/CT_ADDITEM及SDK NoteExample已核对的Create→BMECApi.AddNoteToComponent→Serialize；每真实钢构一条附加材料，单独BomMaterial标记记录模型/钢构ID、材料类型/编号、OwnerSupportInstanceId、ParentInstanceId、OwnerDn、NoteInstanceId。主表归属按真实父管DN选最大，核对管夹计划DN/父管关系，同DN保留原归属，首次按持久ID；改绑转移、末引用移除删材料。不同钢构同编号仍各一套，不以规格编号去重。原管夹描述、编号、父管、配方和PipeSupportComponents不改。

保存绑定时ALIAS/绑定/附加材料归属同一事务；创建/删除/缓存所有权跟踪，失败回滚刷新/回收，回滚失败保留所有权并明确报错。仅删除身份和图形匹配的本插件附加材料，不改用户其他NOTE。新增“同步本模型组合材料”，重算全部已保存引用并清理孤立材料（含删除管夹/钢构后）；无自动事件监听，未保存草稿不参与。实际附加材料BOM/分类、单次计量、管道移动后位置、Undo/Redo/重开仍待宿主新版本验证，不能将旧多行引注成功扩大为新BOM已实测。改前源码ZIP、DLL/PDB、只读元数据探针及校验在迁移备份/绑定材料与ASCII编号_20261015。此条替代下方第一版“不增加ISO材料”的范围说明。

2026-10-15新增支吊架组合绑定support-binding：首页支吊架分类第18入口，总33可用+1占位。Domain/Data/Services/Infrastructure/Tools/UI独立分层，点选本插件正式原生管夹/耳轴，再连续点选活动模型承重钢构Assembly；显式有序引用，不自动合组或随动。独立SteelSectionProbeSupportBindings/SupportBinding固定String字段Payload/BaseTag/CombinedTag，版本1记录目标原生实例ID、原单件编号及子项持久模型ID/元素ID/Assembly类型/编号快照。ALIAS按①②③与字面$编码，IE_TAG复用已有映射；原PlacedPipeSupport.IsoTag、材料AssemblyTag、配方/父管/位置保持。禁止把组合串写回原单件编号或复制承重材料。共架允许多管夹引用，材料按原根仅统计一次，列入引注不代表进入ISO BOM。

支持排序/移除/解除全部/重新读取放弃草稿/主动核对更新编号；保存前重读目标快照与各成员，拒绝删除/改号/跨模型/锁定等。最多19个成员为圈码保护。Editor借API文档对象，禁止游离写回或释放缓存对象；ALIAS+附加项同一独立Undo事务、临时立即提交/finally恢复、精确持久读回，失败回滚刷新缓存、恢复失败明确报错。点取幂等及AccuSnap恢复、Dispatcher/revision防过期回调，离开/关闭/Undo丢弃草稿。新页沿用SupportTheme/PrototypeChrome/v4及固定操作区，不适用历史UI-only业务冻结。说明与宿主验收见Docs/支吊架组合绑定.md；API替身和编译不能代替实际ISO/原生Serialize/Undo/重开验收。改前源码ZIP、DLL/PDB与SHA256在仓库迁移备份/支吊架组合绑定_20261015。

2026-10-15耳轴落自带类并恢复操作柄：F6/F10→SINGLE_PIPE_TRUNNION、F7→DOUBLE_PIPE_TRUNNION、F2/F2-HE/F4/F5→SIMPLE_ELBOW_SUPPORT；参数化 NativePipeSupportComponent+SSP_RECIPE，立管开滑动/旋转柄，弯头关柄仍随动。安装用 Install-NativeSupportEditing.ps1（-Features Trunnion）：给三类加 SSP_RECIPE、Modeling CREATION_ATTRIBUTE→本插件、IE_TAG=ALIAS，保留 ClassMap/SUPP_TRUNNION|SUPP_ELBOW。立管 PlacementFrame 对齐自带 SinglePipeTrunnion：X=管轴，−Z=方位伸出（旋转柄/LENGTH 沿 Z，勿把 Z 设成管轴）。点串保持(−X,+Z)。Setup 无配方只跳过不弹 FATAL，PrepareGraphics 仍要求配方。仅换 DLL 不够，须重装 Schema 并新放；旧无配方件删除后重放。说明见 Docs/耳轴原生编辑与随动.md。

2026-10-15原生管夹颜色修复：用户反馈正式件全部变蓝，核对SDK确认Supports.SetTypeAndSymbology除Edge分类外还调用BaseGeometry.SetSymbologyForElementTypes→GetModelSymbology/SetElementListSymbology，覆盖原Builder分件外观。正式/A1组件删除此调用，共用NativeParametricSupportGraphics仅对实体及方向标记设置三维bmdGraphicsTypeEdge，保留结构钢RGB127/163/124、紧固件和参考体原外观；父管/端口、操作长度、方向标记、Transform及ISO同步保持。禁止用全局Support样式或修改共享工厂默认色解决；无需Schema修改，不批量改旧件颜色。10318项正式与1952项A1离线回归通过，授权/无授权Release均0警告0错误；DLL核对确认两回调无统一样式调用且共用桥接保留分类。宿主新放、编辑重生成后的颜色/操作柄/随动仍需复测，旧件未重生成可能仍蓝。改前源码/DLL/PDB/日志在../迁移备份/管夹原生颜色修复_20261015。

颜色修复版已在用户确认保存关闭OPM后部署至C盘实际mdlapps，DLL/PDB与已验证授权产物SHA256一致；MVID=e673daa7-9018-4f2f-ad97-5c82e6f7b733，DLL SHA256=946F553263A493000E6E23B640F6F24B12E595099C0E1B2A24BEBDE12E38CD3A。此次未改Schema，收据见上述备份目录mdlapps-deployment.json。下方f2719cdf为修色前版本。

2026-10-15正式管夹原生编辑/随动：用户确认A1初始化修复版实测正常，授权核对日志并沉淀到正式放置管夹。最新A1日志MVID b565a3e8-beef-45c1-9eec-45e1f6a3d9d7，Create=0、父管/初始三维与ISO各0mm、Design/SHOP，后续几何回调成功无异常；未取得移动后CHECK/ISO/Undo/重开的完整证据。正式九类统一用独立SSP_PIPE_CLAMP继承SUPPORT_LOCATION，原生Support handler/PipeSupportPlacementTool与公开NativePipeSupportComponent。不得覆盖自带类或把A1实测扩大为其他八类宿主通过。

完整计划与初始毫米坐标架存SSP_RECIPE Version1，白名单Codec仅处理11种领域配方/计划类型的实例字段（含内部字段/嵌套数组），限制长度/递归/数组并拒绝非有限值、缺版本/坐标、混配与未知字段/CLR类型。配方冻结原几何参数，RecipeGraphics用原九类Builder在保存架重建并转局部，当前原生Transform负责编辑位置与姿态；不追写初始配方坐标，不重复写模型/统计。材料/编号/参考体开关及E1方向保持，单根Attach仍在确认事务中。持久对象重读校验参数化类、SSPPC/ALIAS、原始配方全文及三维/ISO点；正式记录Version1可选RecipeVersion=1。

共用NativeParametricSupportGraphics由已验证的原生桥接提取而来，负责离线Element→独立克隆ElementHolder、原生方向标记和当前ISO点的UOR换算。组件Setup在构造阶段仅解析自身配方，PrepareGraphics才SetPipeDiameter/SetSupportLength，保留初始化弹窗修复。正式日志NativePipeSupport/latest.log及component-latest.log覆盖保存。原预览暂态/授权/源复核/独立Undo/立即提交/缓存所有权/失败回滚规则保持；无补偿移动监听。辅助线与参考来源仍普通Cell，旧Cell/旧非参数化原生件不自动迁移。

安装用 Install-NativeSupportEditing.ps1（-Features PipeClamp / All），仅向基础/Modeling/Isoextractor各新增SSP_PIPE_CLAMP和SSP_RECIPE/string，类级IE_TAG取ALIAS。默认预览、关OPM后Apply、先备份SHA256、冲突拒绝、重复幂等、部分失败回滚。10318项正式九类真实会话/Codec/几何分派/Setup/API替身检查、31项正式Schema及16项原引注检查通过；Builder替身不证明实际实体/操作柄/随动/ISO/Undo，正式件仍须逐类宿主试放。当前规范Docs/正式管夹原生编辑与随动.md优先于下方旧非参数化历史。改前完整工作区源码ZIP（包含A1尚未提交的实测版）、DLL/PDB与成功日志备份在../迁移备份/正式管夹原生编辑随动_20261015。

正式版已按用户保存关闭OPM后的授权部署至C盘CINF_F1263AA；三份Schema原1363/631/243节点逐项结构一致，仅各新增正式类，重复预览返回已安装。C盘SDK授权/无授权Release均0警告0错误；常规/备用DLL及PDB一致，宿主mdlapps授权副本已同步校验。正式MVID=f2719cdf-3542-4fb9-a72e-ae2145fa0b52，SHA256=CC5C3AD638FF223CAE40425233ACF31A81E34DC97507E7E00175BA392850BDC3；收据在上述备份目录。D盘工作集副本未修改。

当前UI规范：[Docs/UI规范-v4.md](Docs/UI规范-v4.md)。下方带日期的旧改造记录为历史；当前规格与第9节优先。

2026-10-15：用户仅授权A1/A2编号调整。Domain/PipeClamp/PipeClampNumbering统一生成A1/A2-DN{管径}-{材料代码}，默认C1，去首尾空白/转大写，仅非空ASCII字母数字；A1移除编号中的螺杆/角度，A2补类型/材料，S放材料段不另追加后缀。A1Calculator新增可选材料参数，A2Parameters新增MaterialCode，计划保存规范代码。几何、实体材质/隔离层、其他类别外层编号保持，原Statistics与ALIAS映射自动采用新AssemblyTag；不改Schema、不迁移旧件。

PipeClampPage的A1/A2参数卡各新增MaterialCodeText，沿用ModelInput/LostFocus→Parameter_Changed原预览更新流程，规格行显示编号；PipeClampLastChoice独立记忆两代码，旧数据缺字段默认C1。这是授权业务修改，UI契约仅更新该页业务SHA并增两字段，保留原控件/事件。6516项会话/编号/清单/ALIAS/旧偏好默认与JSON往返、原管夹回归及16976项Q1/Q2通过；597项真实XAML布局/DPI检查新增A1/A2输入边界与停靠尺寸，业务事件使用空夹具；宿主输入联动/重开记忆/ISO尚未实测。双版本零警告零错误。基线67884d9及源码/原型/DLL/PDB校验在../迁移备份/A1A2编号材料代码_20261015_67884d9。

2026-10-14 引注按原管架编号：用户要求九类标注只显示原材料AssemblyTag（E1示例E1-B-107），替代下方旧“类别/DN/规格+自动编号”规则。NativePipeSupportDefinition.Label取原计划AssemblyTag/Number，详细ASCII规格仅留Description，不截断/重编码显示编号，单件空号或控制字符/$拒绝。SUPPORT.NAME为计算业务键，不拿重复规格编号覆盖原生身份；DEVICE_TYPE_CODE=SSPPC、ALIAS=原编号、NAME仍由原生命名。JSON Version1保留IsoTag并可选新增NativeName。共用Writer末尾可选validateReadback在持久对象校验后调用；正式会话检查标记及ALIAS，丢失回滚。

此次用户引注修改需要工作集部署映射，覆盖下方上一轮“不改Schema”的范围限制。Deployment/Install-PipeClampIsoTag.ps1仅在SUPPORT_LOCATION添加当前基类BOM_LABELS副本，IE_TAG仅SSPPC对象取ALIAS，否则保留原表达式；不动其他类、符号、style.xml。实际写前字节备份和SHA256，默认只读预览、重复幂等，已有类级项目映射冲突拒绝覆盖。部署后须重启OPM，新放/重提ISO；其他工作集也需部署，旧件无标记不迁移。脚本UTF8 BOM保证Windows PowerShell5.1正确解码。6484项九类真实会话配替身及16项XML部署；宿主ISO表达式/单件新引注仍须验证。基线085db60和源码/DLL/PDB/用户截图/日志/工作集备份在../迁移备份/管夹引注按管架编号_20261014_085db60。

组合多行本轮仅沉淀方案，不加组合UI或自动分组：单组合根/单站位/有序子件编号与数量，ISO用$分行，一图符一引线一框，材料避免根与子件重复。圈码①②③字体以及TAG/NOTE框的实际多行与行距需在当前样式验证；官方示例及后续接口见Docs/原生支吊架与轴测图接入.md。

2026-10-14：用户实测确认原生支吊架的ISO位置、编号和Supports材料行成功，并授权将流程沉淀后接入正式“放置管夹”九类别（A1/U3/A2/A22/A24/E1/K1/T4/L2）。共用能力在OpenPlant/NativePipeSupport的Writer/Data/Elements/Graphics/Source；不再在生产路径复制试验事务。正式类别统一SUPPORT_LOCATION支架位置类，经继承的ClassMap(...,"SUPP")使用通用简化符号；该类补充Schema的NOMINAL_DIAMETER为string，须按实际字段类型写。DEVICE_TYPE_CODE/NAME包含类别、DN和关键尺寸，DESCRIPTION用ASCII英文避开当前ISO种子的中文缺字。原中文PipeSupportComponents九字段、Builder几何与统计方法保持，根元素另存SteelSectionProbeNativeSupports/PlacedPipeSupport Version1 JSON身份/坐标记录。详见[接入说明](Docs/原生支吊架与轴测图接入.md)。

PipeClampReader捕获原生实例ID/模型指针标识/UOR比例；会话成功预览后绑定数值快照，确认前重读真实可写活动PIPE、身份/轴段/DN/外径/保温/单位，超轴段定位拒绝。参考物化线和辅助线仅普通Cell/本地清单，页面明确提示无ISO关联；原生失败禁止静默降级。正式确认用当前计划重建世界几何，逆变换为局部后交给共用Writer，避免二次平移旋转；Source.Frame沿管轴建立正交架，支持各Builder原范围，不把试验的水平限制搬到U3立管等类别。Writer临时立即提交、Design/SHOP、按mm写ISO点、唯一DEVICE关系、缓存所有权与持久对象重读检查、独立Undo回滚规则必须保留。

管夹预览改COM暂态显示，替代该模块原持续AddToModel的普通预览：在同一短事务内物化普通Cell→由ID获取COM图形→创建暂态副本→立即删临时Cell，Add/Delete不可跨事务且不写材料。新显示成功才释放旧显示，释放失败保留全部显示所有权供取消重试。正式确认只落最终根，释放预览不改DGN，因此Undo不会复活未管理的普通预览；普通来源确认也在事务中重建Cell/写清单，失败保留预览。方向/滑动/更新/取消/离开和已确认所有权继续遵守原规则。不得从正式持久元素直接Extract非参数化几何。旧模型不自动改、工作集Schema/符号库/ISO样式不改，本轮不增加自动跟随事件监听。

5823项正式九类真实会话/共用Writer/暂态生命周期配API替身、原PipeClamp/E1计算、551项真实XAML布局及控件/事件契约通过。PipeClampPage仅增加源绑定和结果状态文字，UI-only快照仅更新授权的该页业务摘要。替身不验证Bentley扫掠、实际COM暂态复制/显示、SUPPORT_LOCATION双横线样式、九类ISO输出或原生Undo/Redo/移动，必须逐类宿主试放；不能把单个试验成功泛化为全部新集成实测。改前431bf95及源码/DLL/PDB、成功截图和原始ISO证据在../迁移备份/放置管夹原生ISO集成_20261014_431bf95。

2026-10-14：用户授权原生停靠改造，覆盖历史固定400×880窗口壳。MainWindow仍以Adapter/ElementHost承载WPF，但通过WindowManager.GetForMicroStation().DockPanel注册稳定ID SteelSectionProbe.Workspace，默认右侧，支持左右/浮动/标签/自动隐藏；不得再AttachAsTopLevelForm或使用圆角Region/固定MaximumSize。初始400×720 DIP、最小400×560，尺寸交给Bentley，DPI变更只更新最小尺寸。SetHomeLayout/ApplyHomeWidth保留兼容接口但不改尺寸。

NativePanelLayout仅在工作区接入页面时隐藏Home/Q1自绘32标题行，以及PrototypeChrome内32标题行，将模块父行改Auto；保留63模块头、导航、页内控件和固定操作。源XAML保留用于独立预览，但正式工作区没有双标题/圆角外框。关闭按钮与原生X先OnPanelHidden结束当前点取并保存偏好，再隐藏复用面板；自动隐藏/标签切换不走关闭清理。重开激活当前页并检查授权；Dispose清理全部页面和timer。AddIn.UnloadingEvent先清理再RemoveContent，清理失败UnloadAbort且保留所有权供重试。稳定ID的跨次布局恢复由Bentley管理，禁止自行加载覆盖宿主全局布局。

改前已提交首页基线48618d5，源码/原型/DLL/PDB及校验备份于../迁移备份/原生停靠改造_20261014。DockingCheck链接真实窗口/工作区/AddIn与窗口API替身；五套真实WPF检查增加变高/DPI覆盖。所有离线检查不能代替OPM实际拖拽、自动隐藏、跨次位置和卸载测试。

2026-10-14 N4槽钢用户修正：子项A/B两侧横担与斜撑必须腹板背靠背、开口朝外，替代旧Python同向截面布置。BracketBuilder中geometric_center槽钢开口沿截面+X；N4负横向侧镜像截面宽轴，正侧保留，beam及brace共用同一方向。N3单架及N4的H型钢C～F原坐标架保留；构件C、中心间距、板中心距/防碰撞、剪切延长与清单不变。EquipmentSupportCheck链接真实Builder与profiles.bin，隔离API记录384组N3/N4、全子项、上下类型、反向、占位与朝向组合，合计6426项回归。OPM原生布尔/扫掠/交互仍需试放；旧模型不自动改，更新未确认预览或重新生成。改前源码/DLL/PDB及用户截图备份于仓库迁移备份/N4槽钢背靠背修正_20261014。

2026-10-14：新增查询分类 line-coordinates（直线坐标修改），当前32可用+1占位，12建模/17支吊架/3查询。用户授权查询分类增加编辑入口，现有构件特性/统计仍只读。Domain/Data/Services/Tools/UI按LineCoordinates分层；通过UorPerMeter/1000显示/编辑模型XYZ毫米值，G17保留往返精度，二维Z=0只读。仅活动模型独立LineElement/MSElementType.Line，不接收LineString、复杂链、块内子线、附件、只读或锁定元素。点取结束再按revision排队读取，不保留Element句柄；Begin幂等，结束恢复捕捉。输入不自动写模型，应用前按模型/ID重读并校验单位/维度及原坐标未被其他操作改变。原生CurvePathEdit仅改几何，ReplaceInModel保留ID/属性；一次替换封成单独TransactionManager事务，失败CancelToPosition，不清Undo缓冲。复用WriteDuration计时，不写支吊架清单。不保存线段坐标至用户偏好；离开/关闭丢弃草稿，撤销/重做失效快照。新页沿用v4和PrototypeTheme。LineCoordinatesCheck验证真实Reader/Editor配API替身；ToolPagesUiCheck链接真实页面/计算/编辑与隔离模型API。首页登记与回归同步；宿主原生写入、坐标属性、样式/EC、捕捉及Undo仍需试用。改前基线319db61及DLL/PDB/原型/校验备份于仓库迁移备份/直线坐标修改_20261014_319db61。

2026-10-14：用户授权首页选择记忆与最近混排功能修复，允许改HomePage展示逻辑和HomePreferences持久化，不适用纯外观改造的源码冻结。HomePreferences.Store新增View（Compact/SortMode/CategoryTab/PinStars），仍兼容原Version=1及Features，未知模块记录保留，不存具体模块排列；缺失/空/非法View安全回落。界面切换立即保存，初始化先恢复再启用事件。重置星标/统计保留View；重置筛选保存新选择。

最近排序使用独立SortedList，跨全部可用模块混排，每项仅一次，隐藏分类及最近四项快捷区；显式分类/收藏和搜索继续过滤。星标置顶规则保持，关闭时按最近时间；默认/频次/名称沿用分类。SortedList必须参与卡片密度、选择导航与尺寸测量。HomeUiCheck链接真实存储，通过仅该检查工程定义的HOME_UI_CHECK把文件隔离在测试输出目录；不得在正式构建定义该符号。63项真实WPF/存储检查与HomeCheck通过；OPM窗口重开未实测。基线319db61，改前备份在../迁移备份/首页记忆和最近混排_20261014_319db61。悬停预览按用户要求暂缓。

2026-10-11：新增 EnableLicensing 编译开关，缺省 true（授权版），false 生成无授权版；只有编译参数生效，无用户配置开关。无授权构建排除激活页面、授权领域/验签/存储/机器标识及公钥，LicenseService 不访问授权文件，全部业务入口开放，隐藏首页激活按钮和作者页授权卡片，不启动到期定时器。Deployment/build_version.ps1 的 Licensed / Unlicensed 输出隔离；默认安装脚本仍只安装授权版。两种 DLL 编译零警告、零错误，138 项授权及双构建检查通过。


2026-10-11：签发器新增“90 天试用（无需机器码）”，保留一个自然月及永久授权。90 天码从签发 UTC 时刻起计时，到期自动为未激活；同一码可用于多台电脑，重复导入不延长期限。新版签名载荷 version=3、trialDays=90，严格校验到期日；原密钥及旧码保持兼容，接收 90 天码需更新 DLL。125 项授权检查通过，插件与签发器 Release 编译零警告、零错误。


2026-10-11：版本角标改为按钮，点击进入“关于与联系作者”；作者魏，邮箱 yo196544wobi@163.com，可复制邮箱、打开默认邮件草稿及进入激活页。版本显示改由 App/ProductInfo.cs 读取 App/AssemblyInfo.cs 信息版本，升级时不再修改首页硬编码文字。新增签发日起一个自然月的通用试用码，不绑定机器，到期为未激活；后台状态按当前 UTC 判断，工作区每秒检查到期并退出业务页面。旧永久激活码保持兼容，密钥不变。103 项授权检查及三种宽度 WPF 布局检查通过；邮件客户端与 OPM 到期清理仍需宿主实测。


2026-10-11：新增离线永久授权。首页搜索框左侧显示“未激活 / 已激活”，点击进入独立激活页；未激活不能进入业务页，STEELPROBE PLACE 和型钢直接放置也拦截。RSA-2048/SHA-256 签名绑定 Windows 安装机器码，授权保存至 %LOCALAPPDATA%/SteelSectionProbe/license/activation.txt，首次读取验签后缓存，错误码不覆盖现有授权，保存失败不解锁。无服务器、期限或远程撤销。作者签发工具及私钥保护/回退说明见 Development/LicenseIssuer/README.md。改动前已提交未授权基线 f301ea5；原 DLL 备份在 bin/Baselines/V0.0.3_Unlicensed。48 项授权检查、首页检查和 WPF 离线布局通过；OPM 宿主中激活、重启与 Key-in 交互仍需实测。


2026-10-11：当前版本更新为 V0.0.3。App/AssemblyInfo.cs 的程序集/文件版本为 0.0.3.0，信息版本为 0.0.3；首页角标 Text 与 ToolTip 同步。后文 V0.0.2 为历史记录。

2026-10-06：版本号 0.0.2。本工程 `<GenerateAssemblyInfo>false</GenerateAssemblyInfo>` 且原先没有 AssemblyInfo，DLL 文件版本一直是 0.0.0.0；程序集版本的**唯一来源**是 `App/AssemblyInfo.cs`（`AssemblyVersion` / `AssemblyFileVersion` = 0.0.2.0，`AssemblyInformationalVersion` = 0.0.2）。**csproj 里加 `<Version>` 不会生效**，不要那样改。改版本必须同时改 `UI/HomePage.xaml` 标题栏角标「V0.0.x · 开发：魏」（`Text` 与 `ToolTip` 各一处），否则界面与 DLL 版本不一致。Release 默认用 D 盘 SDK（`D:\Program Files\Bentley\OpenPlant 2024\OpenPlantModeler`，csproj 里 D 判断在前，C 盘只作兜底）；实测 `bin\Release\net48` 与 `bin\Release\net48_full` 两个产物的 SHA256 一致（`5A7950A7C4718B2468C9B754FB463F8C52B68332FF1684EBB493F2539D79449C`），符合 §11.3 的备用件一致性要求。

2026-10-04：锁 Z 支持 1～15 起点批量，独立路由计算位移，重叠同目标去重，冲突及其重叠组跳过；所有模式一次实际修改最多 15 根直管（含随动水平管及伸缩立管，管件另计），超出整批拒绝。参考文件只读水平管允许作基准，附件逐层 GetTransformToParent 将本地 UOR 转至活动模型 UOR，再转毫米；外径/保温按等比缩放，非等比及剪切拒绝，目标仍只许活动模型。参考对象禁止构造修改/拓扑探测对象。56 项纯计算检查通过，参考附件变换、批量几何写回及 Undo 须宿主实测。

本文件适用于 `型钢构件及支吊架模型生成工具_CS/` 目录及其全部子目录。

管道对齐UI按用户要求隐藏SingleScope（Collapsed），只展示GROUP/ZSTRETCH。页面构造时将旧SelectedOnly迁移至ConnectedGroup并排队保存；ReadParameters缺省为ConnectedGroup，禁止隐藏选项仍被后台选中。底层SelectedOnly业务及兼容配置枚举保留。

用户授权梯梁光滑化：SpiralStairBuilder使用HandrailSmoothPath.Runs划分梁段，曲线段全部竖直U截面BodyFromLoft(false,false)，直线平台/顶部折回保留CreateDgnRuledSweep。禁止跨变坡/急转进行平滑，保持原截面方向。梁/踏步/平台专用颜色127,163,124，仅在盘梯Builder设置，不修改公共实体工厂或围栏颜色。旧“梯梁不改光滑”的记录由本条替代；宿主表现需实测。

混合栏杆光滑试验：HandrailSmoothPath按变坡/真实圆弧/急转分Runs，Spline生成穿点C1三次Hermite样条；HandrailBuilder.SmoothMixedPath仅替换密集曲线采样段，保留直线和真圆弧。SpatialKickplate在各曲线run用BodyFromLoft(periodic=false,segment=false)，直线扫掠，并整体相并；原竖直截面与共用端面保留。SpiralStairCheck增加288组组合的穿点、C1和小于1mm偏差检查。梯梁此轮不改为光滑放样；不能声称全部梁已无分面。宿主放样相并失败须保留明确阶段日志，不静默短段回退。

盘梯最新：梯梁CreateDgnRuledSweep一次接收全路径截面，禁止再逐对创建短实体；钢围栏混合路径扶手和中间管使用MixedTube沿完整Path扫掠。采样分面边线仍可能可见，不能将编译通过声明为宿主无缝验证。状态栏SetBuildProgress三独立文字区域，0.5s限频、整秒耗时、相同文字不重写；文件日志固定spiral_latest.log每次覆盖，约2MB后截断早期内容，已加入覆盖/限大小测试。

盘梯宿主反馈：第一段U梁的BodyFromLoft返回Error；梯梁必须改用CreateDgnRuledSweep(new DgnRuledSweepDetail(curves,true))再DraftingElementSchema.ToElement，与Python原生直纹扫掠一致。Infrastructure/SpiralStair/SpiralStairLog记录UTF8参数/阶段/异常，自动刷新至LocalAppData/SteelSectionProbe/logs/SpiralStair；UI只提供主动“查看日志”，不得恢复自动控制台。日志和纯计算检查不代表宿主放样已实测。

2026-10-06：新增罐体盘梯 tank-spiral-stair，注册于WorkspaceView和HomeFeatureCatalog建模类，首页22个可用模块及1占位。分层Domain/Services/Tools/UI下SpiralStair；纯几何迁移当前Python布局，包括采样螺旋截面逐段放样，这是本模块迁移几何的明确约定。200×100×6是用户指定焊接U板而非轧制槽钢，不查型钢目录。内梁半径=罐半径+100+间隙，梁高向上200，平台顶面梁顶平齐无折边，踏步前下折/后上折各40，顶外梁折回开口朝出口。栏杆基准为实际顶部腿尖，复用HandrailCalculator及HandrailBuilder.BuildSteps；Build仍同步执行同一工作单元，禁止复制栏杆算法。内栏杆可选，WallGapMm>100强制。所有辅助路径只在内存中，结构按设备不写支吊架清单，栏杆确认后复用Statistics.AttachHandrail。WPF分步调度保持原生几何在宿主线程，状态栏显示阶段/百分比/用时，无Python、控制台或进度窗口；页面离开/右键/取消使revision失效并清理预览，失败保留删除失败元素的所有权。最大2000踏步/100梯段/每段4096截面。SpiralStairCheck的12组Python参考及288组栏杆组合通过，宿主几何及生命周期仍需实测。

围栏 MaxPostSpacingMm 默认2000，面板 SpacingText 允许300～2000 mm，通过 PageLastInput 保存。直线、圆弧、螺旋及混合路径均须将该参数传入 PostStations，参数快照须包含它；2000根立柱数量上限与间距参数无关。50mm模数排布保留，非模数上限使用保守分跨。

管道对齐集成：PageId=pipe-alignment，建模类，WPF UI/PipeAlignment页面复用Theme；后台46文件按原逻辑复制到各层PipeAlignment，独立命名空间SteelSectionProbe.PipeAlignment。不能引用原PipeAlign.dll或嵌入WinForms窗口。点取回调只排队ID，Dispatcher/Timer之后读EC；generation阻止旧页面回调，退出页面清理预览并解绑Undo事件，重新进入重读快照。自动预览350ms，应用不二次确认。检查链接汇总源码Development/PipeAlignmentCheck与PipeAlignmentUndoCheck；备份/清单在../迁移备份/管道对齐集成_20261004。首页新增1项后为21个可用模块及1个占位；**当前总数为 22 个可用模块 + 1 个占位卡**（此后又新增罐体盘梯 `tank-spiral-stair`），一律以 `Data/Home/HomeFeatureCatalog.cs` 清单和 `Development/HomeCheck` 的数量断言为准。

支吊架钢构件颜色统一使用 Services/SupportSteelAppearance 的 RGB 常量（当前127,163,124），仅在专用Builder的结构钢件调用。禁止修改SolidPrimitiveFactory/SteelMemberFactory默认颜色而影响人孔、围栏等模块；螺栓、螺母、垫圈、膨胀套管保持原色，管道/保温/灌浆参考体同样保留。新生成件生效，不自动重着色已有模型。

2026-10-04：围栏新增竖轴固定半径/螺距螺旋。原生 BSpline FractionToPoint 读取4097个求值点，HandrailHelixCalculator 在毫米局部坐标拟合并校验1mm误差；不可把控制点当曲线点。HandrailPiece 保留解析螺旋位置、切向与三维长度，Builder 使用三次Hermite样条扫掠和竖直截面踢脚板放样；限制圈数、半径和圈间净距。64组螺旋纯计算及用户样条归一化形状检查通过，宿主几何未实测。

2026-10-06：围栏新增混合盘梯路径支持，MixedPoints 路由空间折线计算，复杂链按原生 FractionToPoint 求值，采样盘梯折线自动识别。统一三维里程及自交检查，踢脚板竖直截面整体放样，不按采样点重复生成立柱。带坡度急转角超过 15° 拒绝；最多 2000 立柱、8192 放样截面。64 组混合路径及原有检查通过，D 盘 SDK 完整 Release 编译通过，OPM 实体需实测。

2026-10-04：普通钢结构围栏支持单根非闭合水平圆弧。HandrailArcInput 保存圆心、基向量与角度，CalculateArc 保留真实圆弧，校验水平圆形、偏移后最小 R140 及保守节点间距。离线验证在 SteelHandrailCheck，OPM 实体需实测。

它既是人类开发文档，也是后续编码 Agent 的执行规范。任何新增功能、重构或修复都应先阅读本文，再检查真实代码；不要只根据文件名或旧对话猜测当前实现。

## 1. 项目目标

### 方形人孔迁移补充（2026-10-03）

`square-manhole` 已注册到 `WorkspaceView` 和 `HomeFeatureCatalog`，位于建模类；实现分层在 `Domain/Services/Tools/UI` 的 `SquareManhole/`。尺寸及装配对应 `方形人孔/SquareManhole.py`。通过 `SolidPrimitiveFactory` 创建离线筒体、盖板、四只真圆弧把手，封装为一个普通 `SQUARE_MANHOLE` Cell；禁止将子部件单独 `AddToModel`，不要消除盖板套装间隙，此设备附件不写支吊架统计。

点取工具 Begin 幂等，保存并恢复 AccuSnap；参数编辑立即使确认失效，手动更新成功才能确认。预览会话管理一个块，重建成功后替换旧预览；取消/离开/关闭清理，确认释放所有权。使用 `PageLastInput` 保存八项输入。`Development/SquareManholeCheck` 从主工程排除，覆盖默认/矩形尺寸、间隙、套盖定位、边界与非有限输入；首页检查为 20 个可用功能加 1 个占位卡（该数字是当时的断言；**当前为 22 个可用功能 + 1 个占位卡**，以 `Development/HomeCheck` 的断言为准）。迁移前完整备份及回退脚本在仓库根目录 `迁移备份/方形人孔_20261003/`；OPM 实体及交互仍需实测。

本项目是 OpenPlant Modeler 2024 的 C# AddIn，目标是提供统一的：

- 国标型钢截面放置；
- 沿路径扫掠生成型钢实体；
- 各类管道支吊架及组合构件生成；
- 公共 ItemType、统计和清单数据写入；
- 可持续扩展的功能首页与独立功能页。

架构上的首要目标不是“用最少文件实现功能”，而是：

1. 尽量复用已有型钢数据和几何能力；
2. UI、交互工具、业务建模、领域数据和基础设施相互分离；
3. 新功能能够独立阅读、独立测试、独立维护；
4. 临时预览必须可安全取消，不得在模型中留下垃圾元素；
5. 不破坏已有 Key-in、资源名称和统计契约。

## 2. 当前技术约束

- 目标框架：`.NET Framework 4.8`；
- 平台：`x64`；
- C# 版本：`7.3`；
- 宿主：OpenPlant Modeler 2024 / Bentley MicroStation API；
- UI：WPF/XAML；顶层 Bentley 宿主仍继承 `Adapter`，通过 `ElementHost` 承载 `WorkspaceView`；
- 默认 SDK 根目录：`D:\Program Files\Bentley\OpenPlant 2024\OpenPlantModeler`（C 盘 `C:\Program Files\Bentley\OpenPlant 2024\OpenPlantModeler` 兜底，编译时可用 `/p:BentleyRoot=` 覆盖）；
- 命名空间目前统一为 `SteelSectionProbe`；
- 工程文件名为 `SteelSupportModeler.csproj`，但运行时程序集名仍为 `SteelSectionProbe`，以兼容现有 OPM 加载配置；
- 用户界面文案使用中文，内部类型与方法名优先使用清晰英文；
- 源文件使用 UTF-8，禁止引入乱码字符串。

不要使用高于 C# 7.3 的语法，例如文件级命名空间、记录类型、init-only 属性或新的模式匹配语法。

## 3. 当前目录职责

```text
型钢构件及支吊架模型生成工具_CS/
├─ App/                 AddIn 生命周期、跨功能页契约
├─ Registration/        Key-in 处理器与 commands.xml
├─ UI/                  工作区、首页、功能页和通用视觉控件
├─ Domain/              纯领域模型，不负责读文件或操作 Bentley 模型
├─ Data/                数据读取、目录查询和数据源适配
├─ Services/            可复用几何、建模和业务服务
├─ Tools/               Bentley 点取、定位、动态绘制等交互状态机
├─ OpenPlant/           管道标高对齐的 OpenPlant 版本适配层
├─ Infrastructure/      ItemType、统计、日志、导出等外部基础设施
├─ Resources/           嵌入 DLL 的运行时资源
├─ Development/         开发期数据生成、转换和验证脚本
├─ Deployment/          编译产物安装与部署脚本
├─ bin/、obj/            编译输出，不是业务源码
├─ 迁移备份/            功能迁移前的源码备份快照
├─ SteelSupportModeler.csproj
└─ README.md
```

### 3.1 依赖方向

推荐依赖方向如下：

```text
UI ───────┐
Tools ────┼──> Services ──> Domain
          ├──> Data ──────> Domain
          └──> Infrastructure

Registration ──> App / UI
```

强制规则：

- `Domain/` 不得引用 WPF/WinForms、Bentley API、文件系统或嵌入资源；
- `Data/` 不得创建模型元素，也不得弹窗；
- `Services/` 不得直接控制主窗口页面跳转；
- `Tools/` 负责 Bentley 交互状态，不应保存大量标准表数据；
- `UI/` 不得实现复杂几何算法；
- `Registration/` 只负责命令入口，不承载业务建模；
- `Infrastructure/` 不得反向依赖具体功能页。

如果一个新类同时负责读取数据、显示控件、点选元素和创建几何，说明分层失败，必须拆分。

## 4. 现有能力清单与复用优先级

开发新功能前，必须按以下顺序检查可复用能力。

### 4.1 型钢目录数据

相关文件：

- `Domain/ProfileModels.cs`
- `Data/RuntimeData.cs`
- `Resources/profiles.bin`
- `Development/export_profiles.py`
- `Development/profile_catalog/`（本工程内可编辑的型钢规格与纯轮廓生成代码）

当前领域对象：

- `FamilyData`：型钢族；
- `ProfileData`：具体规格及尺寸参数；
- `ModeData`：插入基准及闭合轮廓；
- `SegmentData`：直线或圆弧轮廓段。

新增支吊架若使用槽钢、角钢、工字钢或 H 型钢，必须优先从 `RuntimeData.Families` 查询现有规格，禁止：

- 在新功能中再次硬编码同一套型钢尺寸；
- 复制一份 `profiles.bin`；
- 为每种支吊架建立互不一致的型钢规格表；
- 直接从 UI 控件文本反向解析几何尺寸。

只有现有目录确实不存在所需数据时，才允许扩展数据管线。扩展时应修改本工程 `Development/profile_catalog/` 中对应的 `*_data.py`；轮廓或插入基准变化时修改 `*_geometry.py`。然后运行 `python -B Development/export_profiles.py` 重新生成 `Resources/profiles.bin` 并编译，不要手工编辑二进制文件，也不要再修改或读取同级 Python 插件作为本工程的数据源。

### 4.2 型钢截面和扫掠几何

相关文件：

- `Services/GenericProfile.cs`
- `Tools/ProfilePlacement.cs`
- `Tools/SweepPlacement.cs`

`GenericProfile` 当前提供：

- `Curves(...)`：创建原生 `CurveVector`；
- `Native(...)`：创建 DGN 截面元素；
- `Preview(...)`：创建 COM 动态预览轮廓；
- `SweepProfile(...)`：在路径起点构造垂直于切线的截面。

复用原则：

1. 新功能只是生成型钢杆件时，应复用 `ModeData` 和 `GenericProfile`；
2. 新功能需要多个型钢构件拼装时，应创建组合构件 Builder，不要复制截面算法；
3. 新功能需要不同交互流程时，应新建 Tool，但 Tool 仍调用公共建模服务；
4. 不要让新的支吊架功能直接调用 `SteelSectionPage`；
5. 不要为了复用而直接调用带有当前 UI 状态的 `SweepPlacement`。

`SweepPlacement` 目前同时包含交互状态和扫掠创建逻辑。若新功能也需要程序化创建型钢杆件，正确做法是：

1. 将无 UI 状态的“根据规格、坐标系和路径创建扫掠体”提取到 `Services/SteelMemberFactory.cs`；
2. 让现有 `SweepPlacement` 改为调用该服务；
3. 新支吊架 Builder 同样调用该服务；
4. 保留预览所有权和确认/取消逻辑在各自 Tool 或会话对象中。

禁止从 `SweepPlacement` 复制一份扫掠实现到新功能。

### 4.3 统计与 ItemType

相关文件：

- `Infrastructure/Statistics.cs`

现有实现写入 `PipeSupportComponents` 公共 ItemType 库。新增构件必须先检查该契约是否能够表达：

- Assembly / Component；
- 支吊架类型；
- 规格；
- 设计长度；
- 数量、单位；
- 管线或编号信息。

如果字段足够，扩展公共统计服务，不要为每个功能创建新的 ItemType 库。如果确实需要新字段，应保证：

- 对旧 DGN 文件兼容；
- 缺少字段时可增量创建；
- 已存在的数据不会被覆盖；
- ItemType 名称稳定；
- README 和本文同步记录契约变化。

## 5. 新功能应如何组织

### 5.1 推荐的跨层目录

当某个功能超过一个简单页面或包含独立建模逻辑时，在对应层下建立相同的功能子目录。例如新增“门型架”：

```text
Domain/PortalFrame/
    PortalFrameParameters.cs
    PortalFrameResult.cs

Data/PortalFrame/
    PortalFrameCatalog.cs

Services/PortalFrame/
    PortalFrameCalculator.cs
    PortalFrameBuilder.cs

Tools/PortalFrame/
    PortalFramePlacementTool.cs
    PortalFramePreviewSession.cs

UI/PortalFrame/
    PortalFramePage.xaml
    PortalFramePage.xaml.cs
    PortalFramePreviewControl.cs
```

这种组织方式保留了项目的分层结构，也能让人类快速搜索同一功能的所有组成部分。

只有真正跨多个功能复用的类，才放在层目录根部。例如：

- `Services/SteelMemberFactory.cs`
- `UI/Themes/Theme.xaml`
- `UI/WorkspaceView.xaml`
- `Infrastructure/Statistics.cs`

不要建立 `Common/Utils.cs` 一类无限膨胀的杂物文件。

### 5.2 文件命名

使用能够表达职责的名称：

- `...Parameters`：输入参数；
- `...Catalog` / `...Repository`：数据查询；
- `...Calculator`：纯数值计算；
- `...Builder` / `...Factory`：创建模型几何；
- `...Tool`：Bentley 交互命令；
- `...PreviewSession`：临时模型元素生命周期；
- `...Page`：工作区功能页；
- `...PreviewControl`：仅负责 UI 绘制的控件。

避免使用 `Helper`、`Manager`、`NewClass`、`Utils2` 等无法表达边界的名字。

## 6. 新功能接入工作流

后续开发者或 Agent 应按以下顺序实施。

### 步骤 1：盘点现有能力

先使用代码搜索确认：

- 所需型钢规格是否已在 `RuntimeData` 中；
- 所需轮廓、扫掠或坐标系是否已有服务；
- 是否已有相似 Tool；
- 是否可以复用 `PipeSupportComponents` 统计契约；
- 仓库 Python 版支吊架中是否已有经过验证的计算逻辑或标准表；型钢规格以本工程 `Development/profile_catalog/` 为唯一可编辑源。

允许参考 Python 版算法和数据，但 C# 版运行时不得依赖启动 Python。

### 步骤 2：定义纯领域输入和结果

在 `Domain/<Feature>/` 中定义参数和结果对象。单位必须写入字段名或 XML 注释，例如：

- `LengthMm`；
- `RotationDegrees`；
- `Quantity`。

领域对象不要持有：

- WPF/WinForms 控件；
- `Element`、`ElementHandle`；
- COM `Application`；
- 当前页面的静态引用。

### 步骤 3：接入数据

标准表、规格映射和默认参数放入 `Data/<Feature>/`。较大的静态数据放入 `Resources/`，并提供 `Development/` 下的生成脚本。

数据读取应做到：

- 加载一次、缓存复用；
- 缺少资源时提供明确异常；
- 校验数量、版本和必要字段；
- 不在 UI 事件里反复解析大型资源。

### 步骤 4：实现计算和几何

优先把计算拆成两部分：

1. `Calculator`：纯数学、尺寸推导、选型和校验；
2. `Builder`：把计算结果转换为 Bentley 几何。

纯计算应尽量不引用 Bentley API，以便编写普通单元测试。只有最终坐标、曲线、实体和模型写入需要进入 Bentley 边界。

如果必须创建新的建模逻辑：

- 通用型钢或通用板件逻辑放在 `Services/` 根部；
- 某一支吊架专用逻辑放在 `Services/<Feature>/`；
- 不得放进 `UI/`、`Registration/` 或 `Data/`；
- 不得把大段建模代码写在按钮点击事件中。

### 步骤 5：实现 Bentley Tool

交互点取、Locate、Dynamics、Reset 和 Cleanup 放在 `Tools/<Feature>/`。

Tool 的职责是：

- 获取用户输入；
- 管理交互状态；
- 调用 Calculator / Builder；
- 管理临时预览；
- 把状态消息交给页面或主窗口。

Tool 不应承担标准数据定义和复杂尺寸计算。

### 步骤 6：实现功能页

每个可从首页进入的模块实现 `IWorkspacePage`：

```csharp
internal sealed class ExamplePage : UserControl, IWorkspacePage
{
    public string PageId { get { return "example"; } }
    public string PageTitle { get { return "示例功能"; } }
    public string PageSubtitle { get { return "一句话说明"; } }
    public FrameworkElement View { get { return this; } }

    public void OnActivated() { }
    public void OnDeactivated() { /* 结束 Tool，清理未确认预览 */ }
    public void OnWorkspaceClosing() { /* 释放全部资源 */ }
}
```

接入页面时需要同时修改：

1. `UI/WorkspaceView.xaml.cs`：实例化功能页并 `RegisterPage(...)`（`PageId` 与清单逐字一致）；
2. `Data/Home/HomeFeatureCatalog.cs`：新增功能入口条目（含分区键与图标键），首页卡片由该清单数据驱动渲染，不要手写进 `HomePage.xaml`；
3. 必要时在 `Registration/Keyins.cs` 和 `Registration/commands.xml` 增加直接入口。

普通功能不需要额外 Key-in。只有需要脚本化调用或直接进入的核心流程才增加命令。

### 步骤 7：接入统计和确认流程

只有用户确认后，临时预览才成为正式模型元素并写入最终统计信息。不要在鼠标悬停时反复创建 ItemType。

### 步骤 8：补充文档和验证

更新：

- `README.md` 的功能和使用说明；
- 本文件中发生变化的架构或契约；
- 对应数据生成说明；
- 可运行的单元测试或验证脚本。

## 7. 预览、确认和取消的强制规则

所有会写入模型的交互功能必须明确区分：

```text
候选输入 -> 临时预览 -> 用户确认 -> 正式元素
                       -> 用户取消 -> 删除临时元素
```

强制要求：

- 每个功能只能拥有自己创建的预览元素；
- 重建时应先成功创建新预览，再删除旧预览，避免失败后什么都不剩；
- `Reset`、返回首页、关闭页面和关闭主窗口都必须清理未确认预览；
- 确认后必须解除预览所有权，防止 Cleanup 误删正式元素；
- 删除源路径、辅助线等破坏性操作只能发生在明确确认之后；
- `OnDeactivated()` 必须结束当前 Tool；
- `OnWorkspaceClosing()` 必须可重复调用而不报错；
- 点取工具的 `Begin()` 必须**幂等**：已经在点取中时只重新提示、不要"先 `End()` 再安装新实例"——那会先假发一次 `Ended`（页面据此清掉基点与预览、提示"已结束点取"），新装的实例还可能被上一个实例的延迟 `OnCleanup` 带掉，表现就是"再点一次「开始点取」后第一次点击被当成结束，得点两次才进得去"。工具需暴露 `IsActive`，页面在按钮回调里先判断：已在点取中就直接提示"可直接点取下一处，无需再点开始点取"（管夹类 `PipeClampLocateTool` / `ComponentLocateTool` / `NozzlePlacementTool` 均已按此实现）；按钮回调不要再额外手调事件处理函数（`End()` 已会触发 `Ended` 完成页面清理）；
- 不得依赖垃圾回收器删除 DGN 元素。

## 8. 坐标、单位和几何约定

### 8.1 单位

- 业务尺寸和标准表统一使用毫米；
- 重量使用 `kg/m`；
- 面积按现有目录字段约定使用 `cm²`；
- 角度在领域层使用度，并在进入三角函数前转换为弧度；
- DGN UOR 转换只在 Bentley 建模边界进行。

不要在 UI、Calculator 和 Builder 中分别重复一套单位换算。

### 8.2 坐标系

- 明确记录局部 X/Y/Z 的含义；
- 路径扫掠必须处理接近竖直的起始切线；
- 叉积结果必须校验长度，禁止静默产生 NaN；
- 圆弧应继续使用真圆弧，不要用大量短线替代正式模型几何；
- UI 中的二维轮廓预览可以采样圆弧，但不得把采样结果用于最终 DGN 建模。

### 8.3 模型写入

- 创建元素前确认活动模型存在；
- 仅三维功能必须检查 `Is3d`；
- `AddElement` / `AddToModel` 失败时提供可理解的错误；
- 不要持有已经删除或失效的 COM 元素引用；
- 从 COM ID 查找原生元素时检查空值和有效性。

### 8.4 模型文字的强制规范（2026-10-13，用户指定）

所有写入DGN模型的文字统一遵守 [Docs/模型文字规范.md](Docs/模型文字规范.md)，包括当前灭火器箱、水龙柜，以及后续消火栓箱、铭牌、构件名称等。必须复用 `Services/ModelTextFactory.cs`；模块不得另外创建原生TextBlock/TextElement、调用COM文字创建或为文字/组合添加注释比例。字高为构件实际毫米尺寸，仅转换UOR/mm，清除注释比例及持久文字样式关联，采用随构件的局部方向；不得依赖或修改活动绘图比例、文字样式、注释比例锁及放置比例。保留可编辑文字和原预览/确认生命周期。

新增或修改模型文字时运行 `Development/check_model_text.py`，再编译双版本及受影响模块回归。OPM中须检查不同注释比例生成、生成后切换比例、方向与预览清理；源码检查不代表宿主显示已验证。当前模型文字创建已全部集中到公共工厂，FireCabinetBuilder.Text仅作原位置/方向/颜色的适配。详细接口与示例见上述规范。本条是今后新增功能的默认要求；用户明确要求的不同文字行为优先。

## 9. UI 规范（当前统一v4）

当前唯一规格来源是 [`Docs/UI规范-v4.md`](Docs/UI规范-v4.md)，视觉参考是仓库资料中的v4原型。后续所有页面继续采用这套规格；文中历史560宽、240×124卡片、12宽滚动条和深色主按钮不再适用。

- 首页、12个建模、17个支吊架、3个查询及激活/作者工具页统一接入原生停靠宿主；初始400×720 DIP、最小400×560，宽高由宿主分隔条管理，400×880保留为离线视觉参考尺寸。
- 模块保留PrototypeChrome的63模块头、可滚动参数区、固定操作区、46共享底栏；32自绘窗口标题由NativePanelLayout在接入工作区时隐藏。新页面Tag为prototype-v4。Q1/Q2保留兼容标签和原专用样式。
- 建模加载ModelingTheme，支吊架加载SupportTheme，查询/工具加载PrototypeTheme；首页加载HomeTheme。不得复制新的基本主题。项目SVG和HomeIcon几何保持。
- 参数字段34高、卡片圆角6/内边距12/分区头35，长标题允许合理换行；外层滚动条6宽；主按钮蓝色。
- 状态统一调用MainWindow.SetStatus，10.5字、14行高、最多双行、全文悬停；原错误颜色和消息内容保持。
- UI改造必须保留原控件名、默认值、选择顺序/Tag、绑定、事件及按钮状态；不改业务xaml.cs、领域/目录/计算/工具/统计/授权/持久化和清理生命周期。
- 长字段名与勾选项换行，UIElement内容使用对应展示模板；所有表列保留，用横向滚动和最小列宽适配，不能删列。
- 所有现有点取、结束、更新、滑动、角度、取消、确认入口完整保留；参数变化继续由原逻辑禁用确认。不可为了套原型更改工作流。
- 改前提交并备份源码/原型/DLL/PDB和校验值；改后对照UI契约、真实XAML布局/分型/四档DPI及相关离线业务回归，编译双版本。离线检查不等同OPM宿主实测。
- 界面正文、参数名、状态及提示使用中文；DGN/EC/Excel/JSON/标准代号和原型中的辅助英文标签可保留。

## 10. Registration 与兼容性

现有稳定命令：

```text
STEELPROBE SHOW
STEELPROBE PLACE
STEELPROBE QUERY
```

除非用户明确要求，不要重命名或删除它们。

命令新增流程：

1. 在 `Registration/Keyins.cs` 添加公开静态处理器；
2. 在 `Registration/commands.xml` 添加 Keyword 和 KeyinHandler；
3. 保持 `CommandTable.xml` 嵌入逻辑名称不变；
4. 编译后在 OPM 中实测命令加载；
5. 在 README 中记录。

资源逻辑名称 `SteelSectionProbe.profiles.bin` 也是兼容契约，不应随意改变。

## 11. 构建、验证和部署

### 11.1 编译

在本目录执行：

```powershell
dotnet build SteelSupportModeler.csproj -c Release
```

基本交付要求是 0 错误。新增警告必须解释并尽量清除。

### 11.2 最低验证清单

每次功能修改至少检查：

- 首页能够进入目标功能并返回；
- `STEELPROBE SHOW` 正常；
- `STEELPROBE PLACE` 仍能直达型钢页；
- 类型、规格和插入基准联动；
- 页内轮廓预览更新；
- Bentley Dynamics 预览更新；
- 确认后元素保留；
- 取消、Reset、返回首页和关闭窗口不会留下预览；
- ItemType 写入正确；
- 三维限制和非法路径错误明确；
- 高 DPI 和最小窗口尺寸下控件不重叠；
- 窄滚动条可通过滚轮和拖动使用。

纯计算模块应另有单元测试，至少覆盖正常值、边界值和非法输入。

### 11.3 DLL

正常输出：

```text
bin/Release/net48/SteelSectionProbe.dll
```

备用部署件：

```text
bin/Release/net48_full/SteelSectionProbe.dll
```

编译后的 DLL 不是源码真相。不要只替换 DLL 而不提交对应源码和文档。若更新备用 DLL，必须确认它与本次源码编译产物的 SHA256 一致。

## 12. 禁止的实现方式

后续开发不得：

- 把新功能继续堆进 `SteelSectionPage.xaml.cs`；
- 在按钮事件里直接写数百行建模代码；
- 为支吊架复制一份型钢规格和轮廓算法；
- 让 C# 运行时启动 Python 才能完成建模；
- 把业务数据写进 `HomePage.cs`；
- 从其他功能页读取控件值作为业务输入；
- 使用全局静态变量共享大量可变参数；
- 在预览尚未确认时写入最终统计；
- 忽略 Cleanup、Reset 或页面离开事件；
- 为绕过错误吞掉所有异常且不给用户状态提示；
- 修改无关 Python 插件或仓库其他模块；
- 用生成 DLL 代替源码验证。

## 13. 当前已知边界与后续重构建议

当前代码已经完成基础分层，但仍有以下边界需要后续开发注意：

1. `GenericProfile` 同时包含原生 DGN 和 COM 轮廓创建；若继续扩大，应拆成纯轮廓服务与 Bentley 适配器；
2. `SweepPlacement` 仍同时管理预览状态和底层扫掠创建；第一个需要程序化创建型钢杆件的支吊架功能应优先提取 `SteelMemberFactory`；
3. `Statistics` 当前偏向型钢记录；扩展支吊架前应先定义稳定的 Assembly / Component 写入 API；
4. 首页已改为数据驱动（`HomeFeatureCatalog` + `HomeFeatureRanker`，见第 28 节）；`WorkspaceView` 的页面注册仍是显式代码，新增功能页时**必须同时**在 `RegisterPage` 与 `HomeFeatureCatalog` 各加一处，两处 PageId 必须逐字一致；
5. Bentley 运行时交互尚无法由普通 `dotnet test` 完整覆盖，因此编译通过不等于 OPM 实测通过。

重构这些边界时，必须先让现有型钢页改用新服务，再让新功能复用；不要保留新旧两套并行实现。

## 14. Agent 开发步骤

任何 Agent 接手任务时应执行：

1. 阅读本文件、`README.md` 和目标功能源码；
2. 检查 `git status`，保留用户已有改动；
3. 使用搜索确认是否已有可复用数据、几何或 Tool；
4. 写明将修改的层和复用点；
5. 先实现纯模型和服务，再接 Tool 和 UI；
6. 保证预览生命周期完整；
7. 编译并检查差异；
8. 若能进入 OPM，执行运行时验证；不能时明确说明未实测部分；
9. 更新文档和必要的部署 DLL；
10. 交付时列出修改文件、验证结果和剩余风险。

## 15. 完成定义

一项新功能只有同时满足以下条件才算完成：

- 放在正确目录和层级；
- 复用了已有型钢数据及几何能力，或说明为何不能复用；
- 没有把业务逻辑塞入 UI；
- 预览、确认、取消和 Cleanup 完整；
- 数据和单位约定清楚；
- 已接入首页和功能页生命周期；
- 已接入公共统计或明确说明不需要；
- `dotnet build -c Release` 通过；
- 已更新 README / 本规范；
- 已说明 OPM 实测结果或未实测原因。

如果无法满足其中一项，应把它作为明确的待办或风险写入交付说明，不得默认为“以后再说”。

## 16. 构件特性查询

`component-properties` 是只读工作区页面：首页入口位于 `UI/HomePage.xaml`，功能页位于 `UI/ComponentProperties/`，点取 Tool 位于 `Tools/ComponentProperties/`，EC 读取与几何快照位于 `Data/ComponentProperties/`，单位与管径推算位于 `Services/ComponentProperties/`。不创建 DGN 元素，也不写入 ItemType。点取使用 `DgnElementSetTool`：AccuSnap 悬停定位，单次左键 `DoLocate` 后只传元素 ID；右键 Reset 与页面按钮统一触发退出状态。EC 实例读取延后到 UI Dispatcher，并在 `FindInstances` 遍历内转为纯数据；不得把 `IDgnECInstance` 带出遍历。页面离开和关闭窗口必须终止点取。保留现有 `STEELPROBE SHOW` / `STEELPROBE PLACE` 命令。
## 17. 弯头耳轴四组合

首页唯一入口 `elbow-trunnion` 注册在 `UI/HomePage.xaml` 与 `UI/WorkspaceView.xaml.cs`。详情页在 `UI/ElbowTrunnion/`；弯头 EC 读取与 Python 表 1/Sch40 数据在 `Data/ElbowTrunnion/`；纯方向、长度和 F2/F4/F5 编号计算在 `Services/ElbowTrunnion/ElbowTrunnionCalculator.cs`；Bentley SmartSolid 鞍口、通孔、板件在 `Services/ElbowTrunnion/ElbowTrunnionBuilder.cs`；点取与预览所有权在 `Tools/ElbowTrunnion/`。四个组合分别对应原 `F2-[竖直弯头的竖直耳轴].py`、`F2-[水平弯头的竖直耳轴].py`、`F4-[竖直弯头的水平耳轴].py`、`F5-[水平弯头的水平耳轴].py`。

本功能不复用型钢目录或 `GenericProfile`：四个耳轴由钢管或圆钢、鞍口、通气孔和板件构成，原脚本的管径与壁厚来自独立的 Sch40/耳轴选型表，不是型钢轮廓。确认后使用同一个 `PipeSupportComponents` ItemType 库，在组合 Cell 上写 Assembly 与各 Component；原有属性名不变。弯头源元素保持不变。预览新元素成功写入后才删除旧预览；取消、切换方向、离开页面与关闭工作区均尝试清理预览，删除失败保留元素所有权并提示。方向区与参数区均使用双列布局。管径在页面与清单规格中统一显示 DN；组合编号默认使用公制 DN，用户可在“命名管径单位”中改用英制 NPS。F2/F4/F5 四组合共用这一编号选项，命名切换不改变建模尺寸，长度仍以 mm 计。点选弯头的首击只确定源构件；`ElbowTrunnionDragTool` 随后通过视图投影读取鼠标拉伸 H/L，动态帧只绘制临时线框；松开首击并移动鼠标后的下一次左键才固定长度。固定后创建可撤销 SmartSolid 预览，页面确认时才写入最终清单属性。拉伸阶段 Reset、离开页面或关闭窗口均结束工具；参数框可在固定长度后调整预览。


## 18. 支吊架统计

`support-statistics` 是只读页面，首页入口在 `UI/HomePage.xaml`，页面与导出按钮在 `UI/SupportStatistics/`。统计快照在 `Domain/SupportStatistics/`；`Data/SupportStatistics/SupportStatisticsReader.cs` 遍历当前 DGN 文件的模型与图形元素，读取 `PipeSupportComponents` 的 `PipeSupportAssembly_*`、`PipeSupportComponent_*` 实例并立即复制属性值；`Services/SupportStatistics/` 负责纯汇总及 Excel / JSON 文件写出。继续使用现有九个 ItemType 字段和公共库，不新增统计库，也不写入模型。Excel 保留原 Python 的“汇总 / 支吊架表 / 材料汇总表”三张表；导出前刷新数据。三个表格的横向滚动条使用页面局部样式与受限宽度，不扩大工作区；另存为建议名由活动 DGN 文件名、`_支吊架材料表_` 和 `yyyyMMddHHmmss` 时间戳组成，用户仍可修改。变更汇总口径或字段时，须同步 `Statistics.cs` 契约、README 和纯计算检查。
## 19. 罐壁人孔

首页唯一入口 `tank-manhole`，详情页在 `UI/TankManhole/`，规格表和纯计算分别在 `Data/TankManhole/`、`Services/TankManhole/TankManholeCalculator.cs`，Bentley SmartSolid 在 `Services/TankManhole/`，点取与预览所有权在 `Tools/TankManhole/`。原始来源为仓库同级 `罐壁人孔/tank_wall_manhole.py`。公称尺寸使用 DN450 / DN500 / DN600，业务几何尺寸用 mm，只有 Frame 将尺寸转换成活动 DGN 的 UOR。两种开盖形式共用基础筒节、法兰、盲盖、螺栓和把手；吊杆与铰链各由独立 Builder 路径添加。组合单元名保持 `TANK_WALL_MANHOLE`。本功能是罐体设备附件，原脚本没有支吊架 Assembly / Component 清单契约，不写入 `PipeSupportComponents`。

点取左键后才构造可撤销模型预览；参数变化重新构造时先写入新预览，再删除旧预览。右键 Reset、页面按钮、返回首页和关闭工作区均清理预览。C# 侧几何必须与 `罐壁人孔/tank_wall_manhole.py` 逐项对齐：吊杆回转支撑件的径向轮廓（双水平臂 16 厚、腹板 16 厚、背部外 R20 / 内 R10、开口端 30° 收窄到法兰厚度）其**外表面**在立柱轴线外 `D/2 + 20 + 16`——那 16 是原脚本 `BodyFromSweep` 把轮廓厚度加在扫掠路径终点之外产生的，改动支撑件时不要按脚本的长度公式（只算到路径终点）取 20；轮廓与尺寸放在 `TankManholeCalculator` 的 `DavitSupportAnchorY / DavitSupportOuterFaceY / DavitSupportChamferDistance / DavitSupportProfile`（纯计算，可在 `Development/TankManholeCheck/` 断言；`DavitSupportProfile` = 8 直线 + 4 真圆弧，`DavitSupportOutline` 把圆弧展开成 40 点仅供校验）。**圆角必须用真圆弧原语**（`CurvePrimitive.CreateArc` + `SolidPrimitiveFactory.Prism(profile, origin, extrusion)`）扫成真圆柱面；用 8 段折线近似会在圆角上留下成排分面棱（每段法向差 11.25°，OPM 里是一叠横线，而原脚本的 `BlendEdges` 是真圆角、没有这些线）。`SolidPrimitiveFactory.PolygonPrism` 只能给折线用，别拿它画圆角。吊杆的圆到扁头过渡同样按原脚本优先级：先 `Create.BodyFromLoft(profiles, guides, modelRef, periodic:false, segment:true)`（段间线性无平滑，等价原脚本的 `DgnRuledSweep`），失败才退回 24 段台阶近似（回退时轮廓反序，法向朝圆管一侧）；`BodyFromLoft` 的两个布尔量含义见 MSPy 存根 `Examples/Microstation/Intellisense/MSPyMstnPlatform.pyi`。M20 调节吊环螺栓圆环中心线半径 25（孔 Ø30）。30° 端部倒角用布尔差集；需在 OPM 核对。**铰链销轴（`HINGE_PIN_DIA` 16、伸出吊耳 20、半长 73.5）上下两端必须各有一只开口销**：吊耳站位 ±45.5、板厚 16，销轴两端都伸出吊耳，只在下端装开口销上端就是光的（销轴会往上抽出）。两只开口销的位置、直径和朝向镜像对称，销轴上的开口销孔也掏两个，都放在 `TankManholeCalculator` 的 `HingeLugZmm / HingePinHalfLength / HingeCotterStations`（纯计算，`Development/TankManholeCheck/` 断言对称性与"孔必须在吊耳外侧"）。吊杆立柱的开口销**只有下端一只**属于正常：立柱顶端与吊杆竖直段端面对接，没有自由端可锁，不要照搬到上端。OPM 运行时必须检查所有 DN / 压力组合的扫掠和布尔差集、直纹放样、普通 Cell 形成、预览取消以及吊杆连接位置。纯计算检查位于 `Development/TankManholeCheck/`。
## 20. 实体管口

`solid-nozzle` 首页入口位于 `UI/HomePage.xaml`，详情页在 `UI/Nozzle/`，纯参数和结果在 `Domain/Nozzle/`，嵌入尺寸表读取在 `Data/Nozzle/`，计算与 Bentley 建模在 `Services/Nozzle/`，点取和预览所有权在 `Tools/Nozzle/`。原始数据 `实体管口/flange_data.json` 原样复制为 `Resources/nozzle_flange_data.json` 并嵌入 DLL。新增法兰尺寸时修改原始数据并重新复制或建立数据生成脚本，不在页面硬编码尺寸。与罐壁人孔共用 `Services/SolidPrimitiveFactory.cs` 的圆柱、扫掠和布尔操作。

管口总长度包含法兰厚度，业务输入均为 mm，Bentley 构件边界统一换算 UOR。仅允许当前等级和钢管系列同时存在且外径一致的 DN。螺栓孔默认不绘制；密封面凸台只有数据表提供外径和高度时才绘制。模型是一个 SmartSolid；确认前为工具拥有的预览元素，重新点取或修改参数先创建替代预览，Reset、页面离开和关闭时删除未确认元素。原 Python 工具为可视化管口，不创建 OPM 管道组件或支吊架材料条目，因此本功能不写入 `PipeSupportComponents`。纯数据检查位于 `Development/NozzleCheck/`，OPM 运行时需验证布尔相并/差集和预览删除。

## 21. E1 不保温管导向架

`e1-guide` 首页入口在 `UI/HomePage.xaml`，详情页在 `UI/E1Guide/`。表 1 的 DN/外径与 A～E 选型数据在 `Data/E1Guide/E1GuideCatalog.cs`，纯布局计算在 `Services/E1Guide/E1GuideCalculator.cs`，Bentley 型钢和板件建模在 `Services/E1Guide/E1GuideBuilder.cs`，点取及预览所有权在 `Tools/E1Guide/`。与普通型钢路径扫掠共用 `Services/SteelMemberFactory.cs`；B～E 的轮廓从本工程的 `RuntimeData.Families` 读取，不依赖同级 Python 插件。该功能仅接受三维模型和坡度不超过 30° 的直线轴段。普通直线和多段线使用页面 DN，OpenPlant 管道优先读取 EC 管径。LineString 和仅含直线的 ComplexString 按三维点取位置选最近有效线段；其余线段不参与计算。放置点在选中线段三维投影并截断至端点。管轴取值顺序为：中心线曲线 → 元素范围（包围盒）**最长边**，与 Python `axis_from_bbox` 一致；**兜底不得限定水平** —— 竖直管道同样要靠它定位，加"必须水平"会把竖直管一律拒掉（与 Python 行为不符）。包围盒近似只给提示（`E1GuideSelection.AxisNote` → 页面预览行）不报错。各类型自己的走向限制放在各自 Calculator 里（K1 ≤ 5°、E1 ≤ 30°）。OPM 中需对斜向管道和多段线实测。

确认前预览是本功能持有的 `E1_RACK` Cell；重新点取先创建替代预览再清理旧元素，Reset、返回首页与关闭工作区均清理未确认元素。确认时才在公共 `PipeSupportComponents` 库写入 Assembly、构件A ×2 与可选薄板 ×2；源管道和多段线始终保留。“删除辅助线”仅在单根普通直线点取后可选，默认不勾选；确认时还需核对源元素仍为直线才执行删除。数据、长度和距离均使用 mm，命名仅使用 DN 档对应的 E1 子项与高度。纯计算检查位于 `Development/E1GuideCheck/`。


## 22. 混凝土锚板（G2）

`g2-anchor-plate` 首页入口位于 `UI/HomePage.xaml`，详情页在 `UI/G2Anchor/`。表 1 子项 A~D、安装面与建模常量在 `Data/G2Anchor/G2AnchorCatalog.cs`，纯参数与解析结果在 `Domain/G2Anchor/G2AnchorModels.cs`，校验与尺寸解析在 `Services/G2Anchor/G2AnchorCalculator.cs`，局部坐标在 `G2AnchorFrame`，Bentley 建模在 `G2AnchorBuilder`，点取与预览所有权在 `Tools/G2Anchor/`。原始来源为仓库同级 `管道支吊架/G2-[混凝土锚板（膨胀螺栓）].py` 与 `管道支吊架/模块/公共/混凝土锚板.py`。

局部坐标系原点为板背面中心（贴混凝土面的那一点），**局部 +X 恒为混凝土外法向**（锚栓露出的那一侧），混凝土在 −X 侧。三种安装面只改变三个局部轴的世界方向：`wall` 在水平面内绕 Z 旋转；`floor` 取 +X = 世界 +Z（锚板水平、螺栓朝下插入楼板）；`ceiling` 取 +X = 世界 −Z（螺栓朝上）。轴方向定义集中在 `G2AnchorCalculator.Axes`（纯计算），`G2AnchorFrame` 与 `Development/G2AnchorCheck/` 必须共用这一份，**不要在 Frame 里另写一套**。

锚板为正方形，边长 = S + 100（边距 50）、厚 T、四角 4 个 φG 孔。锚栓总长 L 保持不变，螺杆外端超出螺母外端面 5 mm（露出的丝头），故有效埋深 = L − (板厚 T + 垫圈厚 + 螺母高 + 5)，须不小于表 1 的 h_ef；不满足时抛中文错误（数据自检）。埋入端膨胀套管外径取 `1.7 × d`、长度取有效埋深的 0.55。每根锚栓由埋入端膨胀套管、螺杆、垫圈与六角螺母四段简单拉伸 / 圆柱构成，**不做布尔融合**（允许实体重合）——这是原脚本的既有行为，不要为了“更干净”改成相并。

预览为 `CONCRETE_ANCHOR_PLATE` 普通 Cell，由 `G2AnchorPreviewSession` 持有：重建时先写入新版、成功后再删除旧版，删除失败则回滚新版。**确认时才写 `PipeSupportComponents`**（1 条 Assembly + 锚板 ×1 + 膨胀锚栓 ×4），预览阶段只出几何。`Statistics.AttachG2Anchor` 的属性值必须与 `模块/公共/支吊架公共库.py` 的契约一致：`SupportType` 存**中文类型名**（`G2-[混凝土锚板（膨胀螺栓）]`），Assembly 记录的 `ComponentName` 固定为“支吊架”，构件记录用构件名（锚板 / 膨胀锚栓）。右键、结束点取、取消预览、离开页面与关闭工作区均清理未确认预览；子项 / 间距 / 朝向 / 安装面跨会话记住（`%LOCALAPPDATA%\SteelSectionProbe\g2_anchor_last.json`）。

纯计算检查位于 `Development/G2AnchorCheck/`：`dotnet run --project Development/G2AnchorCheck/G2AnchorCheck.csproj -c Release`。OPM 运行时需实测点取、普通 Cell 写入与删除、ItemType 附加，以及三种安装面下的锚板朝向与锚栓伸入方向。

## 23. 清单属性契约（所有写入 PipeSupportComponents 的功能共用）

`Infrastructure/Statistics.cs` 的每个 `AttachXxx` 都必须与 `管道支吊架/模块/公共/支吊架公共库.py` 的九字段契约一致——这是 Python 与 C# 两侧写入的记录能被同一套统计聚合的前提：

| 字段 | Assembly 记录 | Component 记录 |
| --- | --- | --- |
| `RecordKind` | `Assembly` | `Component` |
| `SupportType` | **中文类型名**（`E1-[不保温管导向架]` / `G2-[混凝土锚板（膨胀螺栓）]` / `F2-[竖直弯头的竖直耳轴]` …） | 与左列相同 |
| `AssemblyTag` | 支吊架编号 | 同一编号 |
| `ComponentName` | 固定为 `支吊架` | 构件名（构件A / 不锈钢薄板 / 锚板 / 膨胀锚栓 …） |
| `Specification` | 整组规格 | 构件规格 |
| `DesignLengthMm` / `Quantity` / `Unit` / `PipeNumber` | 0 / 1 / 套 / 管道号 | 设计长度 / 数量 / 件·块·套 / 管道号 |

**ASCII 代号只用于 ItemType 命名**（`PipeSupportAssembly_<代号>_<哈希>`），绝不写进属性值：写进去会让统计页的“按类型套数”显示英文代号，并与 Python 写入的同类记录分裂成两组。中文类型名一律由 `Data/<功能>/` 的常量或映射方法提供（`E1GuideCatalog.SupportType`、`ElbowTrunnionCatalog.SupportType`、`G2AnchorCatalog.SupportType`），不要在 `Statistics.cs` 里另写一份字面量。新增功能时必须同时在该功能的 `Development/<功能>Check/` 里断言这张映射，防止两边再次漂移。

⚠️ **不要把尺寸编进 ItemType 名，值要写进 EC 实例**。旧写法把型材族/长度/编号编进类型名（`..._STEEL_SECTION_<族>_L<长度>`），值只存在于**类型默认值**里，于是每出现一个新规格就要新建一个 ItemType —— 而每次新建都要付一次 `library.Write()` 全库写盘，这就是“点确认很慢”的根因。写盘成本实测为 **约 数十 ms + 2 ms × 库内类型数**（537 个类型时 1.16~1.32 秒，空库时仅 ~63 ms）——注意**不是**“固定 1.17 秒”，537→547 的样本不足以区分固定与线性，别再沿用那个结论。`FindByName` 同规律但系数小约 500 倍（537 类型 2 ms/次），因此**缓存 ItemType 或去掉二次 `FindByName` 的收益≈0，不值得做**。正确写法：`Ensure()` 用**固定类型名**，再用 `ApplyRecord()`（内部 `CustomItemHost.ApplyCustomItem(type)` 返回 `IDgnECInstance` → 写 `instance["属性"].StringValue/IntValue/DoubleValue` → `instance.WriteChanges()`）把本条记录的差异写进**元素上的实例**。这样同一 DGN 内类型数量恒定，首次之后每次确认都命中、不再写盘。型钢实测 **1447.6 ms → 1.2 ms**；用日志里的“回读长度”验证过值确随记录变化（2439.742 → 2115.817），说明确实落在实例上而不是类型默认值里。约束：固定名**必须保留 `PipeSupportAssembly_` / `PipeSupportComponent_` 前缀**（`SupportStatisticsReader` 靠它分类）；一个元素上需要多条 Component 记录时按构件角色加后缀（`_A`/`_B`/`_PLATE`/…）而不是加尺寸。统计侧不需要改：读的本来就是实例属性值，且材料表按 `SupportType+ComponentName+Specification+Unit` 分组、与类型名无关；历史 DGN 里的旧类型照旧可读，新旧可共存。**全部 `AttachXxx` 已按此改造，编写新功能时照抄 `Statistics.Attach` 的写法**：在方法内拼好 `List<KeyValuePair<string,object[]>>`（用 `AddEntry` 辅助方法），最后一次性 `WriteRecords(element,entries)` —— 它会合并成**一次** `EnsureBatch`（最多一次写盘）、再逐条 `ApplyCustomItem` + 写实例值。`WriteRecords` 内置**同名守卫**：同一元素上若两条记录的类型名相同会抛中文异常（否则后一条静默覆盖前一条），因此不要试图绕过它：撞名必须改角色后缀，而不是放宽校验。需要多条 Component 记录时用常量角色后缀区分（`_A` / `_B` / `_PLATE` / `_BOLT` / `_EAR` / `_TRUNNION` …）；角色码来自**数据表**（如 T4 的 `T4ShoeCalculator.ComponentItems`）时，必须在对应 `Development/<功能>Check/` 里断言其唯一性（`PipeClampCheck` 已加）。
这一版的固定类型名清单（保持 `PipeSupportAssembly_` / `PipeSupportComponent_` 前缀）：`STEEL_SECTION`；`<feature>` + `_TRUNNION`/`_PLATE`/`_LINER`（弯头耳轴）；`E1` + `_MEMBER`/`_LINER`；`G2` + `_PLATE`/`_BOLT`；`A2` + `_BODY`/`_BOLT`；`K1` + `_BLOCK`/`_PLATE`；`T4` + `<item[0]>`；`VP_EAR_PLATE`/`VP_TRUNNION` + `_EAR`/`_BASE`/`_BOLT`/`_TRUNNION`/`_END`/`_PAD`；`N8` + `_PLATE`/`_BOLT`；`<N3|N4 code>` + `_A`/`_B`/`_C`/`_PLATE`/`_BOLT`/`_STIFFENER`。
写入 API（`ApplyCustomItem` 返回 `IDgnECInstance` → 写 `StringValue/IntValue/DoubleValue` → `WriteChanges()`）均已用 net8 只读元数据确认过签名，**不要因为“以前不用 WriteChanges 也能读出来”就省略它**：不写这条，值会留在类型默认值里（第一次的值），后续记录全部读到同一个数。

## 24. 放置管夹（A1 / A2 / A22 / A24 / E1 / K1 / T4 / L2 合并入口）

首页只有 `pipe-clamp` 一个入口（`UI/PipeClamp/PipeClampPage.xaml`），页面顶部下拉切换八种管夹，参数区按类型切换可见性。**不要为管夹类功能再新增首页入口** —— 新管夹作为下拉里的一个 `PipeClampKind` 加进来即可（同步 `PipeClampCatalog`、`PipeClampLastChoice` 的记忆字段、`Development/PipeClampCheck` 的断言与 README 的类型表）。

八种管夹共用 `Tools/PipeClamp/PipeClampLocateTool.cs`（点选管道 / 直线 / 多段线，只上报元素 ID 与点击点）与 `PipeClampPreviewSession.cs`（预览生命周期 + 按种类分派清单写入）。A1 在定位后使用 `A1ClampOrientationTool` 显示随光标旋转的临时模型，第二次左键锁定开口方向。`Data/PipeClamp/PipeClampReader.cs` 复用 `E1GuideReader` 的轴线与管道判定，再补公称直径、外径与保温厚度（EC 属性 `INSULATION_THICKNESS`；值落在 (0,1) 时按米计、乘 1000 转毫米）。

**点取 → 方向工具的交接**：同一次调用里"先 `End()` 再 `InstallTool()` 装另一个工具"是禁用的 —— `ExitTool()` 挂起的"退出当前工具"会在下一个原生事件结算，那时当前工具已经是新装的实例，会被误杀并触发一次伪 `Ended`（页面据此提示"已取消方向调整"）。交接一律用 `PipeClampLocateTool.RetireForHandoff()`（只清静态 active + 恢复 AccuSnap，不调 ExitTool、不发 Ended），旧实例由新工具 `InstallTool` 的工具切换收尾；`Begin()` 里也不要再写 `End()` 再装。

**精确绘图（AccuDraw）**：`DgnPrimitiveTool` 不会自动接管罗盘，不显式激活时罗盘灰色、键盘焦点不在罗盘上，回车会被 MicroStation 当成打开 Key-in 对话框。`A1ClampOrientationTool.OnPostInstall` 在 `BeginDynamics()` 之后调用 `ActivateCompass()`：`AccuDraw.Active=true` → 旋转模式改 `AccuDraw.RotationMode.Context`（**顺序：先改模式再写矩阵**，反了新矩阵会被模式切换冲掉）→ `SetContext(SetOrigin|FixedOrigin|SetRMatrix, 管心, 径向基矩阵)` → `AccuDraw.Rotation` 兜底再写一次 → `SetContext(SetFocus)` 把焦点交给罗盘。罗盘三轴由 `A1ClampCalculator.CompassFrame` 调用 `RadialFrame` 得到：X=开口角 0°、Y=角度增大方向、Z=管轴。罗盘平面垂直于管轴，法线沿管轴；这是用户指定的当前表现。开口角定义保持不变，勿改公共 AccuDraw 设置。矩阵三轴按**列**存（`FromColumns` 的 `ColumnX` 即传入的 X 轴，已实测），退出时还原激活状态与旋转模式。

- **A1**（`A1ClampCatalog` / `A1ClampCalculator` / `A1ClampBuilder`）：弯弧圆心在管轴，真实半圆与两条 D 长度直腿相切。每腿两颗螺母，顶板既不建模也不计入清单。开口基准为水平管 +Z，近竖直管 +X；光标在径向平面内投影并按右手角度旋转。ItemType 名固定为 `PipeSupportAssembly_A1`、`PipeSupportComponent_A1_U_BOLT`、`PipeSupportComponent_A1_NUT`，尺寸和角度只能写入属性值。
- **A2**（`A2ClampCatalog` / `A2ClampCalculator` / `A2ClampBuilder`）：表 1 只按**公称直径数值**匹配（与脚本 `_match_table_dn` 一致，不拿外径比）；保温时内孔 A′ = A + 2B，且孔心距 B 必须同步外移 B，否则孔会落进放大后的孔洞区域被剪掉、螺栓随之错位。绕轴角度由 `PipeClampFrame.Axes` 自动给出（局部 Z 竖直向上），不给用户旋转角入口。
- **A22**（`A22ClampCatalog` / `A22ClampCalculator` / `A22ClampBuilder`）：`A = OD + 2×(承重板厚 + 保冷厚) + 10`，按 A 查表 1，`B=A/2+E`，`G=螺栓直径+3`；E 对应 A2 的 D。表 2 的承重板厚按 DN 分档。两片承重环在局部 Z 方向对开，各有左右法兰板；两套螺栓、螺母与四只垫圈独立成形。过渡圆角 `T≤15` 时 `R_MIN=T`，`T>15` 时 `R_MIN=2.5T`，以与承重环外圆和法兰平面相切的圆弧剖面拉伸建模；大圆角邻近螺栓处整平垫圈座面。
- **A24**（`A24ClampCatalog` + A22 共用计算与实体剖面）：表 1 的 C/E/T/W/螺栓直径与 A22 同档，新增 F；四孔中心在 `±B`、`±(B+F)`，法兰两侧各延长 F。四套紧固件和八只垫圈独立建模、记入独立 A24 清单。A24 表 1 没有允许荷载，不能从 A22 借用。
- **K1**（`K1LimitCatalog` / `K1LimitCalculator` / `K1LimitBuilder`）：只接受与水平面夹角 ≤ 5° 的管轴。子项 A 的半片 T 形截面在本地自建（8 点、无圆弧）；子项 B/C 的 H 型钢取 `geometric_center` 轮廓。**H 型钢轮廓的 2D x 是翼缘宽 B、y 是截面高 H**（见 `型钢截面生成器/steel_sections/steel_hbeam_geometry.py` 的顶点定义），换轴时别弄反，否则“腹板水平、两翼缘竖直”会变成另一种姿态。
- **T4**（`T4ShoeCatalog` / `T4ShoeCalculator` / `T4ShoeBuilder`）：H 只能由隔热层厚度 B 查表得到，面板只读显示，**不要给用户直输 H 的入口**。布尔顺序固定为：外圆柱 − 内圆柱 − 45° 矩形贯穿体 → 每块耳板开孔后并入 → 底板与支撑并入。DN50 及以下按详图 B 只用矩形底板和中央纵向腹板，不生成横向弧顶支撑；DN80 及以上另加弧顶横向支撑（减圆柱成形、必要时再减对开间隙）。切口方向一律用 `T4ShoeCalculator.CutFrame` 的 (c, s) 做 (x, a, b) 映射，不要自己推坐标。
- **L2**（`L2ShoeCatalog` / `L2ShoeCalculator` + T4 共用布尔布局与实体 Builder）：表 1 的 L/F/E 分别为 DN15~150 的 150/80/35、DN200~600 的 300/150/75 mm；耳板与横向支撑端距由 layout 传递，不能套用 T4 固定 75 mm。H 按 L2 保冷厚度表（≤25→100，至 275→350）取值。L2 薄保冷层时耳板根部按内圆外径退让，防止穿入保冷层。LGEN2 注 8 的梯宽 C 未给尺寸，暂复用 T4 底板宽度表和耳板尺寸。L2 荷载、密度和位移取自己的表；不套用 T4 荷载。
- **E1**：面板并入本页，数据 / 计算 / 建模仍在 `Data/E1Guide/`、`Domain/E1Guide/`、`Services/E1Guide/`。“确认后删除辅助线”只对单根普通直线有效，删除前要核对源元素仍是直线，且管道与多段线始终保留。

型钢轮廓的三连查找统一走 `Data/ProfileLookup.cs`（纯查表，接受 `FamilyData[]`，因此纯计算检查工程也能链接），不要在功能里另写一套。新增管夹时若需要新增型钢规格，仍走 `Development/profile_catalog/` + `export_profiles.py` 的既有流程。

## 25. 点选元素的功能必须传递元素所属的模型（参考文件支持）

参考文件（reference）里的元素，其 ElementId 属于**它自己那个文件的 ID 空间**，按 ID 去活动模型里查是查不到的。因此所有"点选元素"的工具都必须上报 `LocatedElement`，读取器必须接受并透传 `DgnModelRef`：

- **工具**：在定位回调内 `LocatedElement.From(element)` 取 `element.DgnModelRef` 与 `ElementId`（不要把 Bentley 的 `Element` 对象带出回调），点击点放进 `ClickX/Y/Z`；
- **读取器**：签名统一为 `Read(DgnModelRef modelRef, ulong id, …)`，并保留 `Read(id, …)` 作为"活动模型"的快捷转发；内部用 `ComponentPropertyReader.ResolveModel(modelRef)` 拿到正确的模型；
- **几何**：**活动模型走原 COM 路径，参考元素走 .NET 曲线查询**（`CurvePathQuery.ElementToCurveVector` + `CurveVector.GetRange / GetStartEnd`）。COM 的 `ActiveModelReference` 只认活动模型，**绝不能用它读参考元素** —— 这是"点不到参考文件里的管道"的根因；
- **单位**：COM 坐标是 master 单位（`× UorPerMaster / uorPerMm`），.NET 几何坐标是 UOR（`/ uorPerMm`），两者换算不同，不要混用；
- **定位策略**：MicroStation **默认不把参考元素交给 `DgnElementSetTool`**，点上去会报"元素位于只读参考文件之中" —— 这道关卡与 ElementId 无关、也与参考附件的类型/设置无关（参考文件在 MicroStation 里永远不可编辑）。凡是只需要**读取**的定位工具，都必须覆写 `protected override RefLocateOption GetReferenceLocateOptions()` 并返回 `RefLocateOption.TreatAsElement`（枚举是标志位：`Normal=0 / SelfAttachment=1 / Editable=2 / TreatAsElement=4`），再加一层 `OnPostLocate` 兜底（基类拒绝且元素来自参考文件时返回 true）。**`SetRefLocateOption` 在 C# 侧不存在**，别照 Python/C++ 的写法找。

补充：`Element` 没有 `ElementRange` / `ModelRef` 属性，但**有 `DgnModelRef` 与 `DgnModel`**；`HitPath` 也没有 `GetHeadElementRef`。需要查 Bentley API 真实签名时，用 `_apidump` 那类"只读元数据"的办法（`PEReader` + `MetadataReader`，可打印完整签名）—— 注意 **`DgnElementSetTool` 在 `Bentley.DgnDisplayNet.dll` 里，不在 `Bentley.DgnPlatformNET.dll`**，按类型名找 DLL 时先 `grep -a` 一下。**不要用 PowerShell 的 `Reflection.Assembly.LoadFrom`**（被安全策略拦截），也不要用"故意编译报错"的探针去猜不存在的成员：编译器的函数体分析会被声明级错误压制，可能给出"看起来没报错"的假象。

破坏性操作（删除辅助线等）必须排除参考元素：参考元素的 ID 在活动模型里删不掉，应提前禁用选项并说明原因。

## 26. 点选参考文件元素时的"临时辅助线"流程（放置管夹）

点选**参考文件（reference）**里的管道时，放置管夹不直接拿参考元素去生成，而是：

1. 用 `PipeClampReader.Read(modelRef, id, …)` 读出参考管道的**管轴**（起终点）与管道属性（公称直径 / 保温 / 管道号）；
2. 用 `Services/PipeClamp/TempAxisLine.cs` 在**活动文件**里按这段轴线建一条普通 `LineElement`；
3. 用**已验证的按线路径**（`PipeClampReader.Read(lineId, clickUor…)`）重新读一遍这条线；
4. 把参考元素读到的管道属性**并到这条线的选择结果上**（`IsPipe` / `NominalMm` / `InsulationMm` / `PipeNumber` / `IsFromReference=true`，并把 `IsAuxiliaryLine` 置 false —— 临时线由插件自己清理，不交给用户勾选的"删除辅助线"）；
5. 确认 / 取消 / 结束点取 / 切换类型 / 离开页面时调用 `TempAxisLine.Delete(id)` 删掉它。

**为什么这样做**：把"参考元素"的影响面收敛成**一次轴线读取**，生成那一段完全走活动文件里已经跑通的路径，避免"参考元素写不进 / 删不掉 / 几何读不稳"整类问题。新增管夹类型时，只要把选择结果喂进各自 Calculator 即可，无需再为参考元素写第二套生成逻辑。

实现约束：临时线 id 存在 `PipeClampPage.tempAxisLineId`，**每次点选前先删旧的**（`ReadSelection` 开头）；建线失败要**退回直接读取的结果**而不是抛错（不能因为辅助线失败挡住生成）；删除失败只发状态栏提示，不影响已确认的管夹。异常退出（宿主崩溃）时可能残留一条普通直线 —— 这一点已在 README 里向用户说明。

## 27. 立管耳轴（F6 / F7 / F10）

首页唯一入口为 `vertical-pipe-support`。页面顶部先选类型，再点取立管或竖直辅助线；F6/F7 共用参数区，F10 使用独立参数区。纯数据与计算在 `Data/VerticalPipeSupport/`、`Services/VerticalPipeSupport/VerticalPipeSupportCalculator.cs`，实体在 `VerticalPipeSupportBuilder.cs`，预览生命周期在 `Tools/VerticalPipeSupport/`。点选复用只读的 `PipeClampLocateTool` 与 `PipeClampReader`，支持参考元素的模型引用。源元素保持不变。轴线偏离竖直超过 5° 时拒绝建模。`Statistics.AttachVerticalPipeSupport` 只在确认时写入公共清单；F6/F7 的 `SupportType` 必须是 Python 原值 `F6_F7-[立管的耳轴]`，F10 必须是 `F10-[小管径立管耳板]`。

## 28. 首页排序与星标

首页卡片的数据来自 `Data/Home/HomeFeatureCatalog.cs`（`FeatureDescriptor` 清单，**唯一来源**），顺序由 `Services/Home/HomeFeatureRanker.cs` 计算，分区定义在 `Data/Home/HomeCategories.cs`，相对时间在 `Services/Home/HomeRelativeTime.cs`，偏好存储与使用统计在 `UI/Home/HomePreferences.cs`，卡片视图模型在 `UI/Home/HomeCardItem.cs`，渲染在 `UI/HomePage.xaml(.cs)`。**不要在 `HomePage.xaml` 里再手写卡片** —— 新增功能页只在清单里加一项（含分区与图标键）。

首页结构按v4：32标题栏→159品牌/统计头部→131搜索/分类/排序工具区→最近与模块列表→46底栏。HomePage自带首页标题；全部功能页由PrototypeChrome或Q1专用模块头显示，WorkspaceView旧HeaderRow隐藏。

2026-09-28 分区口径：「HGT21629 支吊架」收纳全部支吊架类功能（弯头耳轴、立管耳轴、放置管夹、混凝土锚板、N3/N4/N8）；建模类只保留通用建模（型钢、罐壁人孔、实体管口）。

排序是**一个全序比较器**，关键字从高到低：置顶区（星级 ≥ `HomeFeatureRanker.PinThreshold` = 3）→ 星级降序 → 使用频率降序 → 出厂顺序（`DefaultOrder`）升序 → `PageId` 字典序。最后一级不能省：`List.Sort` 是**不稳定**排序，缺它会让同键卡片每次渲染顺序漂移。

- `HomeFeatureRanker` 是**纯计算**：不引用 WPF / 文件系统，**也不读系统时钟** —— 当前时间由调用方以 `utcNow` 传入，否则不可重现、写不了断言。它必须能被 `Development/HomeCheck` 链接。
- 使用频率是**衰减计数**（按月分桶 `yyyy-MM`、半衰期 1 个月、保留 12 个月），**不要改成累计总次数**：累计会让半年前的高频功能永久霸榜（本月 12 次应当压过上月 20 次，这才是“最近常用”）。
- 冷启动（无偏好数据）全部落回出厂顺序，新用户看到的首页与改造前完全一致。
- **评分后立即重排**（2026-09-28 用户改的口径，推翻早期的"不立即重排"）：`SetStars_Click` 先就地刷新星标字形，再 `Dispatcher.BeginInvoke(Refresh, DispatcherPriority.Background)` 重建顺序。**不要改成直接 `Refresh()`** —— 此刻还处在 ContextMenu 菜单项的 Click 里，重建 `ItemsSource` 会把菜单的 `PlacementTarget` 从可视树上摘掉；Background 优先级排在"本帧输入处理完（菜单关完）"之后，视觉上仍是点完即变。回到首页时的 `WorkspaceView.ShowHome()` → `Refresh()` 保留作为兜底。
- 使用统计的**唯一埋点**是 `WorkspaceView.OpenPage(id)`（命令行入口 `STEELPROBE PLACE` 也走它），且**同一次会话内同一功能只记一次**（`SessionCounted`）—— 首页表达的是“多常需要这个功能”，不是“点了多少下按钮”。
- **分区与归类**：`FeatureDescriptor.Category` 存分区键，键/中文名/显示顺序的唯一来源是 `Data/Home/HomeCategories.cs`；`FeatureDescriptor.Icon` 存图标键，几何在 `HomePage.xaml` 的 `HomeIcon_<key>` 资源里，由 `HomePage.ResolveIcon` 注入 `HomeCardItem.IconGeometry`。新增功能必须同时给分区与图标键，否则 `Development/HomeCheck` 会报错。
- **搜索与排序**：搜索即时过滤并隐藏最近区；默认/频次/最近/名称四个排序按钮与分类、详细/简约切换均按当前HomePage展示代码；原五级评分、≥3置顶、偏好与调用统计保持。
- ⚠️ **两档显式排序（最近使用 / 常用优先）必须先过 `HomeFeatureRanker.CompareStarTier`**（置顶区 → 星级降序），同级才比最近时间 / 使用频率。少了这一级就会出现"标了 5 星、但『常用优先』时被高频低星功能压到后面"——星标是用户的显式意图，不能被排序模式覆盖。该比较器放在纯计算层就是为了能被 `Development/HomeCheck.CheckStarTierPriority` 断言（含"高频 0 星不得压过低频 5 星"的回归用例）。
- ⚠️ **星标按钮必须是卡片 Button 的兄弟节点，不能放进卡片内容里**：`FeatureCardTemplate` 的结构是「外层 Grid → 卡片 `Button` + 星标 `Button`（`HorizontalAlignment=Right` / `VerticalAlignment=Bottom` / `Margin=0,0,16,13` 叠在右下角）」。卡片整体是入口按钮，若把星标放进它的内容里，嵌套按钮虽通常能先拿到按下事件，仍会出现"点星标却进了功能页"。兄弟节点与卡片没有父子关系、不共享事件路由，从结构上杜绝；卡片底部留一个 `46×26` 的透明占位 Border 保证时间文字不被星标压住、且卡片纵向预算不变。
- **最近使用**：只取 `IsReady` 且 `LastUsedUtc` 可解析的功能，按时间降序最多 4 项；相对时间文案由纯计算 `HomeRelativeTime` 生成（`刚刚 / N 分钟前 / N 小时前 / 昨天 / N 天前 / yyyy-MM-dd`）。同一功能会同时出现在「最近使用」与所属分区，因此 `HomePage` 用 `itemsByPageId` 把同 PageId 的多个 `HomeCardItem` 一起刷新（评分时两处同步）。
- 占位卡（`IsReady = false`）没有 PageId、不参与评分与统计，固定落在「规划中」分区；用独立的 `PlannedCardTemplate`（灰化 + 「即将上线」角标 + 不可点击），可用卡用 `FeatureCardTemplate`，**不要为单个功能另写模板**。
- **首页卡片**：详细78高、最近/简约47高，两列间距6；单击选中，双击/箭头/Enter进入。星标按钮独立操作，不得误触进入；品牌及17个HomeIcon几何保持。
- **滚动条统一样式**：当前页面加载HomeTheme中的6 DIP模板，模板内显式使用HomeScrollBarStyle并清零MinWidth/MinHeight；旧Theme的12 DIP模板仅为兼容资源，不作为新增UI规格。
- **窗口固定尺寸**：所有已注册工作区页400×880 DIP，不再通过卡片测量自动扩大；ApplyHomeWidth只保留兼容接口。
- **DPI换算**：统一由MainWindow.ToDevicePixels/SetHomeLayout完成；400×880 DIP在150%为600×1320设备像素，不得在各页另设ClientSize或重复缩放。
- 存储 `%LOCALAPPDATA%\SteelSectionProbe\home_preferences.json` 只存 `PageId → {Stars, TotalUseCount, LastUsedUtc, MonthlyUse}`，**不存顺序**：增删功能、调权重都不需要迁移数据，也不会留下“存了顺序但功能已改名”的脏数据。读写失败一律静默回落（与各页 `LastChoice` 一致），绝不能挡住首页。
- ⚠️ `HomeFeatureCatalog` 的 PageId 与页面 `PageId` 不一致时，`OpenPage` 会命中“未注册的功能模块”分支 —— 这一支**故意不静默返回**，就是为了让配置漂移可见。
- 新增检查工程要照例在主 `SteelSupportModeler.csproj` 里加 `Compile Remove`（`Development\HomeCheck\**\*.cs`）。

纯计算检查：`dotnet run --project Development/HomeCheck/HomeCheck.csproj -c Release`（清单一致性、分区归类与图标、五级关键字、≥3 星置顶、衰减频率、相对时间文案、脏数据容错、使用情况文案）。

## 29. 型钢生成的截面参数显示

型钢页「03 当前截面参数」显示哪些行、每行中文名和单位是什么，**唯一来源是 `Data/SteelSection/SteelSectionCatalog.cs`**，它与 Python 原版 `型钢截面生成器/steel_sections/steel_registry.py` 每个家族的 `fields` 逐项一致（原版只显示这份精选字段，C# 曾经把 `profiles.bin` 里的全部原始键直接铺出来，于是界面出现 `mass` / `area` / `surface_area` / `Ix` … 且行数多一倍）。`SteelSectionPage.SelectProfile` 只遍历这张表，**没有登记的键一律不显示** —— 宁可少显示，也不要把英文键漏到界面上。

新增型钢类型或字段时：改 `Development/profile_catalog/` 的数据与 `export_profiles.py`，重新生成 `Resources/profiles.bin`，同时在 `SteelSectionCatalog` 补中文名与单位，并更新 `Development/SteelSectionCheck` 里的期望字段表（那里逐字比对字段顺序）。

纯计算检查：`dotnet run --project Development/SteelSectionCheck/SteelSectionCheck.csproj -c Release`。该工程自带一份 `profiles.bin` 嵌入资源（`LogicalName` 与主工程一致），所以能读真实数据并断言：7 个类型的字段顺序与 Python 注册表一致、每个字段在每个规格里都存在、中文名含汉字、单位在允许列表内、未登记类型返回空表。

程序集内其它用户可见英文（`Statistics` 的 ItemType 写入失败、`RuntimeData` 的数据损坏、耳轴/管口的 `SmartSolid` 字样）也已统一为中文；新增功能时按第 9 节的文案规则办。

## 30. D5 / D6 / G12 / D19 三角架

首页使用 `triangle-bracket`，名称“三角架”，描述含 `D5_D6_G12_D19`。功能分层在各层的 `TriangleBracket/`；点选水平辅助线复用 `BracketLocateTool` 与 `PipeClampReader`，型钢实体复用 `SteelMemberFactory` 和 `profiles.bin`，G2 端板及锚栓复用 `G2AnchorBuilder`。D5 为 H 型钢与角钢且可选 G2 端板；D6、G12 为单片槽钢，G12 另有四根锚栓；D19 为双槽钢和端部连接板。确认前只有可取消的预览，确认后才写清单。

`Statistics.AttachTriangleBracket` 一次性批量写入 `PipeSupportComponents`。四个架型保留 Python 中文 `SupportType`；ItemType 名使用固定组合代号加角色后缀（`A`、`B`、`C`、`PLATE_A`、`PLATE_B`、`BOLT_A`、`BOLT_B`），不含尺寸或哈希。不得改变 `PipeSupportAssembly_` / `PipeSupportComponent_` 前缀，统计页依赖它们分类。纯计算检查在 `Development/TriangleBracketCheck/`。

## 31. D8 / D13 / G5 / G6 / D16 门型架

首页只有 `portal-frame` 一个入口，进入后选 D8、D13、G5、G6 及各自子项。点取整组中心竖直辅助线，线长为 H；平面方向角由页面输入。D8 输入立柱净距 B，D13/G5 输入横担全长 L，G6 输入两柱外缘间距 L。D8 类型 1～4 覆盖正门、倒门及端焊、侧焊；D13 类型 1～2 覆盖正门、倒门；G5/G6 地面生根每柱一套锚板、四根膨胀锚栓、螺母和灌浆梯台。

实现分层在各层 `PortalFrame/`。型钢规格与截面从 `profiles.bin` 查询，荷载表与地脚参数记录在 `PortalFrameCatalog`。预览可以更新或取消；`Statistics.AttachPortalFrame` 仅在确认时批量写入固定名称的 Assembly / Post / Arm / AnchorPlate / AnchorBolt / Nut / GroundGrout 角色，无实例哈希。纯计算检查在 `Development/PortalFrameCheck/`。

G5/G6 及复用此地脚的 G4，现场灌浆梯台采用方体减四侧楔体。OPM 的 `Create.BodyFromLoft` 对此处两张方形截面返回 `Error`，不要重新改回无回退的放样调用。

## 32. D12 / G4 / D15 T 型架

2026-10-15 G4 底板中心修正：BuildVertical 的立杆沿 PostVOffsetMm 定位，地脚整组须使用同一局部 v 偏移转换后的世界毫米 XY，地面 Z 保持辅助线低端。底板/锚栓/螺母/灌浆继续共用 PortalFrameBuilder.BuildGround；角钢中心为 geometric_center 外接正方形中心，不是角点或截面重心。不要再直接传辅助线原点 f.X/f.Y。7 子项×8 方位×3 单位×2 线向共336组真实Builder/API记录替身检查及原T架回归通过；OPM实体仍需试放，旧件重新生成。改前源码、DLL/PDB及SHA256在仓库迁移备份/G4底板中心修正_20261015。

首页只有 `t-frame` 一个入口，页面顶部选择 D12、G4、D15。D12/G4 点取竖直辅助线，D15 点取水平辅助线。D12 支持正 T / 倒 T，G4 为地面生根正 T，D15 支持对称 / 偏心与接点焊接形式。D15 筋板尺寸只进入编号，不生成筋板实体。型钢来自 `profiles.bin`，G4 地脚几何复用 `PortalFrameBuilder.BuildGround`。确认预览时由 `Statistics.AttachTFrame` 一次写入固定的组合代号与构件角色 ItemType，不使用哈希或尺寸作为类型名。纯计算检查在 `Development/TFrameCheck/`。

D15 截面姿态集中在 `TFrameSectionAxes`，对应 Python `水平T形架_几何.member_axes` 的负角旋转约定。槽钢构件 B 的截面 X 轴为 `-u`、Y 轴为 `+w`；槽钢构件 A 的截面 X 轴为 `+v`、Y 轴为 `+w`。不要把正 90° 误当成数学上的正向旋转，否则槽钢开口会反向。

T 型架参数页的 H/L 或 L1/L2 上限与 `TFrameCalculator.Calculate` 的校验共用 `TFrameCalculator.Limits`，切换子项、类型、输入值及点选辅助线后更新“当前值 / 标准上限”。D15 的辅助线标准上限为 `L1 上限 + 构件 B 腹板厚 tb`。校验允许 1 mm 测量容差；超限错误必须写明当前值和标准上限，不要只提示“超出上限”。

## 33. Y2 弧形垫板 / 弯头垫板

首页只有 `pad-plate` 一个入口，页面顶部选 Y2 或弯头垫板。Y2 点取水平管道、HVAC 圆形直风管或直线；普通管道按 DN 查外径与板厚，HVAC 圆形直风管按 EC 实际外径贴合，不落到备用 DN。弯头垫板点取 90° 管道或 HVAC 圆风管弯头，读取 EC 矩阵、外径和弯曲半径；截面沿弯头中心线圆弧扫掠。风管护板厚度由实际外径决定：≤2000 mm 为 6 mm，>2000 mm 为 10 mm。Y2 风管编号的尺寸段采用 `D450` 这类实际外径文字，ItemType 名仍固定。两类垫板都用真圆弧截面和可选 Ø6 通气孔。

预览可更新或取消；确认时 `Statistics.AttachPadPlate` 一次写入 Assembly 与 Pad 构件。ItemType 名固定为 `PipeSupportAssembly_Y2_ARC_PAD` / `PipeSupportComponent_Y2_ARC_PAD_PAD` 或 `PipeSupportAssembly_ELBOW_PAD` / `PipeSupportComponent_ELBOW_PAD_PAD`，尺寸、材料和编号只写实例属性。纯计算检查在 `Development/PadPlateCheck/`。Bentley 扫掠、气孔布尔与 EC 点取需要在 OPM 中实测。

## 34. D7 L 型架

首页 `l-bracket` 对应 Python `D7-[L形_倒L形架].py`。点取开放的两段 L 形辅助折线，竖直段为立杆轴线、水平段为横担顶面；类型 1/2 立杆在下，3/4 立杆在上。子项 A～D 可选四类，E/F 的 H 型钢仅允许类型 1/3。截面使用 `profiles.bin` 与 `SteelMemberFactory`，清单仅确认时由 `Statistics.AttachLBracket` 批量写入。ItemType 名固定为 `PipeSupportAssembly_L_PIPE_RACK`、`PipeSupportComponent_L_PIPE_RACK_Post` 和 `PipeSupportComponent_L_PIPE_RACK_Arm`，不得附加编号、尺寸或哈希。H 和 B 的标准上限及当前值在参数区展示，详细失败原因放预览文字，底部状态栏保持简短。纯计算检查在 `Development/LBracketCheck/`；折线点取与 Bentley 扫掠仍需 OPM 实测。


## 35. L7 / L8 保冷立管导向架

`cold-riser-guide` 先选 L7/L8，再选类型。保留原 L7 类名及重载以兼容已有实现；`L7GuidePlan.Series` 区分系列，`HasMember` 区分 L7 类型 2（A24，无构件 A）与其余类型（A22，有构件 A）。L8 类型 1 按用户要求复用 L7 类型 1 几何与截面；L8 类型 2 按附图表 1 用角钢/[12.6/[14a 和 N8 类型 1/2，复用 N8Builder，不复制板件或螺栓几何。连接板面在 L1 处，厚度从构件实长中扣除。G2AnchorFrame 新增显式三轴构造，调用方传入正交单位轴。

L8 表数据与材料代码位于 L7GuideCatalog，L8 编号次序为类型、管径、保冷厚度、沿轴夹板长 L、材料代码、管心至端部 L1。固定 ItemType 名为 L8_TYPE1/L8_TYPE2 及对应角色，不带实例尺寸。沿用可取消预览与确认后统计流程。新增检查纳入 Development/PipeClampCheck，覆盖复用一致性、选型分段、N8 厚度扣除、编号与荷载/位移数据。


## 36. 普通钢结构围栏

首页 `steel-handrail` 位于 **建模类**，图标键 `handrail`，注册在 WorkspaceView。对应各层 `SteelHandrail/`。HandrailCalculator 不引用 Bentley；单位毫米，原脚本横向偏移 -34.2 mm、水平转角 R140、柱距上限 2000 mm 和 50 mm 模数排柱规则均保留。坡段保持竖柱，纯变坡节点强制设柱；同点转向且有坡度明确拒绝。连接类型 1 椭圆压扁端采用真椭圆放样与内腔扣除，类型 2 下弯 R76，类型 3 底板保持水平，类型 4 为原版预留无节点。立柱最大间距 `MaxPostSpacingMm` 默认 2000、面板可调 300～2000 mm，直线 / 圆弧 / 螺旋 / 混合路径都必须把该参数传入 `PostStations`，参数快照必须包含它（2000 根立柱的上限与间距参数无关）。

路径形式分四条独立分支：直线与折线（`BuildPath`，转角真圆弧 R140、纯变坡点强制设柱）、单根非闭合水平圆弧（`CalculateArc`，保留真圆弧，偏移后半径不得小于 R140）、固定半径/固定螺距的竖轴螺旋（`HandrailHelixCalculator`，原生曲线求值 4097 点、1 mm 拟合容差、扫角 30°～20 圈、整圈升高 ≥1200 mm），以及由直线、水平圆弧与螺旋混合组成的非闭合复杂链（`HandrailArcInput.MixedPoints` → `Calculate(..., spatial:true)`，原生 `FractionToPoint` 采样、统一三维里程与自交检查、`HandrailSmoothPath` 按变坡/真圆弧/急转分 run 后 C1 光滑，带坡度急转角 >15° 拒绝，立柱 ≤2000、放样截面 ≤8192）。单弧分支之外的“混合链”不再是拒绝项，旧记录里的“混合复杂链仍拒绝”已作废。

HandrailBuilder 复用 SolidPrimitiveFactory；踢脚板为完整偏移路径一次扫掠，不能改为短板拼接。新预览成功后才能删除旧预览；参数修改禁用确认，150 ms 延迟重建，失败保留旧几何；Reset、页面退出和关闭清理会话拥有的预览。确认后由 Statistics.AttachHandrail 一次写入公共库固定 STEEL_HANDRAIL 及构件角色，不把长度写入类型名。导出 JSON 复用公共统计服务并筛选普通钢结构围栏；旧 Python 库不自动导入。顶/中横杆按每道围栏累计长保存，踢脚板用实际偏移长，压扁端/下弯段用原版水平代表值。

纯计算检查在 Development/SteelHandrailCheck：28 组从原 Python 提取的路径、排柱、偏移及节点基准，每组校验四种连接形式，并验证所有闭合方式、非法路径和清单；参考数据生成器仅用于开发期。主工程排除检查工程源码。更新首页时同步 HomeCheck 的条目数量、顺序与建模类断言。

### D16 水平门型架补充

D16 合并于 portal-frame，点取水平辅助线，其起点为生根端、线长为 L1。类型 1 仅输入 L2；类型 2 另输入 L3/L4，外侧 B 在 L1+L3，内侧 B 在 L1−L4；L4=0 无内侧 B，L4=L3 编号省略 L4。L2 按图为 A 内侧净距，A 轴距为 L2 加 A 截面宽 B；角钢/槽钢 A 对应的 B 实长为 L2；H 型钢 A 对应的 B 两端延伸到腹板内侧面。A/B 使用 geometric_center，同一水平面，A 比外侧 B 的站位延长 50 mm。接点焊接型式 ABCD 现阶段仅参数与编号，无焊缝/筋板几何。固定 ItemType 使用 D16_HORIZONTAL_PORTAL_FRAME 及 MemberA/MemberB 角色。尺寸、完整荷载表、编号与边界回归纳入 PortalFrameCheck，原竖直四种架型保持回归。

D16 截面方向：两侧 A 镜像，角钢水平肢在上、竖直肢在内侧且背靠背；槽钢腹板背靠背、开口向外。角钢 B 水平肢在上、竖肢朝框架外侧（内侧 B 朝根部）。H 型钢 A 的 B 实长为 L2 + A 翼缘宽 − A 腹板厚，两端延伸至腹板内侧面，清单使用实际长度。

D16 尺寸定位修正：类型 1 的 L1 到 B 竖肢/腹板外侧平面，B 中心站位 L1−B宽/2，A 总长 L1+50。类型 2 两根 B 背靠背，外侧中心为 L1+L3+B宽/2，内侧中心为 L1−L4−B宽/2，A 总长 L1+L3+B宽+50；两类 A 均比 B 最外边缘伸出 50 mm。B 宽度读取截面目录 B 参数。此处替代此前以 B 中心定位的说明。

## D20 门型架

D20 合并于 portal-frame。子项 A～D 的 H 型钢立杆、双槽钢横担及腹板间净距 S 复用 G6 规格与背靠背几何，不生成地脚。竖直辅助线 H 为立杆底面到横担顶面，立杆实长 H+50。按附图 L 为两立杆中心间距，横担实长 L−立杆截面高度。H 上限分别 1000/2000/3000/3000 mm；允许垂直荷载按 L≤500/1000/1500/2000 表查，空栏不推算。编号 D20-子项-H-L；ItemType 固定 D20_PORTAL_FRAME 及 Post/Arm 角色，实例尺寸不进入类型名。PortalFrameCheck 覆盖尺寸、编号、荷载表和上限。

D16 可勾选起始端附加 G2 混凝土锚板，每根 A 一套，共两块板、八根膨胀锚栓。子项 A～D 与外移量沿用 D5 端焊三角架；孔距取 G2 最小孔距与大于 A 截面最大尺寸的下一档 25 mm 模数中的较大值。A 起点为外移量+板厚，实长扣除该值，B 定位与 A 外端保持不变。锚板方向随辅助线方位转动；预览统一管理，确认时固定 G2Plate/G2Bolt 角色写入清单。参数随页面持久化；拒绝锚板重叠及过大外移。

2026-10-09：管道标高对齐支持单根水平 LineElement 作为只读基准。直线端点转换到活动模型毫米坐标，按水平容差校验，直线标高为端点 Z 平均值；管底/中心/管顶及裸管/保温模式下基准标高均为该直线标高，表面偏移只作用于目标管。直线不读 EC、不探测修改接口、不进入移动计划，目标校验明确拒绝；应用/Undo 后重读端点，失效后要求重新选择。参考附件逐层转换端点。新增 L01～L03 检查覆盖三种模式、保温、非水平/零长度拒绝和锁 Z 路由。59 项离线检查通过；OPM 点取与实际写回仍须宿主验证。
2026-10-09 乙字弯锁 Z 试验：修改前回退提交 314f89097e4d525c159e456679776d72d9da4b64，包含水平直线基准。ZAxisRoutePlanner.Offset 支持选中水平管—移动弯头—斜管—固定弯头—平行固定水平管；保持斜管方向和弯头角度，斜管移动端水平位移为 ΔZ*(dx/dz,dy/dz)，选中水平管升降并调整连接端位置，另一端 XY 保持原值、Z 同步升降。斜管另一端与固定侧全链保持不变。选中管另一端必须无连接；分支、非平行、空间投影不沿管轴、短管/翻转、未知拓扑、端点歧义拒绝。批量冲突沿用固定/移动范围冲突保护。直管用 SetLinearPoints 写回；弯头单独用 Transform3d 等量 XYZ 平移及 Serialize，不改变角度、不使用图形兜底。每项验证完整目标端点，直管同时验证 EC 长度；固定侧全链复核位置、EC 与连接，失败整批事务回退。UI 展示直管调整与弯头 ΔX/ΔY。67 项纯计算（O01 含 108 组角度/朝向/端点/位移组合）、4 项撤销模拟和完整 Release 编译通过；OPM 乙字弯点取、弯头持久化与真实撤销仍待宿主实测。

### 预览更新按钮提示（2026-10-10，所有现有及新增功能必须遵守）

凡功能页提供“更新预览”按钮，参数改变导致预览待更新时必须显示“更新预览 ●”，通过 UI/PreviewUpdateHint.Set 统一设置。成功生成与当前参数一致的预览后清除黑点；更新失败保留黑点。取消、确认、结束操作、切换类型清空定位及离开页面后清除提示；尚未点取时不因恢复配置或初始化显示黑点。自动更新功能保留自动更新机制，在等待更新及更新失败期间显示提示，成功后清除。拖动定位中的动态原型参数更新遵循原工具生命周期。新增功能交付必须检查参数变化、成功、失败、取消和重新进入页面的提示状态。


2026-10-10 弯头耳轴：新增“固定长度耳轴”，复用 H/L 输入并通过 PageLastInput 保存勾选状态。固定模式点选后直接生成可取消预览，不进入拉伸，不自动修正非法 H/L；取消固定模式清理预览并要求重新点选。拉伸模式 AccuDraw 原点采用 H/L 几何基准，局部 X 对齐耳轴、Y/Z 锁零，矩形罗盘输入与 ev.Point 模型坐标计算统一；不再读取 RawPoint 或计算屏幕投影，不再通过事件来源字符串猜测捕捉。底平水平耳轴罗盘原点同步下移。修改 H/L 立即使确认失效，更新失败保留黑点；成功后清除。离开/取消恢复原罗盘模式、方向、原点和启用状态。离线坐标测试和 Release 编译不能代替 OPM 轴测捕捉、键盘输入及罗盘锁轴实测。


2026-10-10 N1 单悬臂架：新增 `n1-cantilever`，首页当前为 23 个可用功能 + 1 个占位卡（以 HomeFeatureCatalog 和 HomeCheck 为准）。分层位于 Domain/Data/Services/Tools/UI 的 N1Cantilever；类型 1/2、子项 A～E，类型 3 缺结构图未开放。辅助线设备中心→立管中心，标高为 A 顶面，反向选项仅反转局部坐标，不修改辅助线；参考线只读转换复用 PipeClampReader。a=L−R 查图纸表1，不能用 L1 或扣除 D 后的距离代替；A 的 a>500 空白档拒绝，a>750 一律拒绝。类型1 L1=L−R−D+末端余量（默认/最小150），编号省略 L2；类型2 L1=L−R−D，L2默认300、上限600，A端按B-B的10mm缩进。截面取 profiles.bin，复用 SteelMemberFactory/N8Builder，不复制轮廓；已有设备/预焊件不生成或统计。预览单Cell、A/B相并，失败保留旧预览且禁确认，替换回收失败的新Cell持续持有所有权；右键/取消/离开清理，参数更改黑点提示，确认才 AttachN1Cantilever 一次 WriteRecords。固定 ItemType 名 PipeSupportAssembly_N1_CANTILEVER/PipeSupportComponent_N1_CANTILEVER_<角色>；禁止尺寸入定义名。使用 PageLastInput 保存输入，辅助线保留。97项离线检查和HomeCheck通过；OPM相并、N8方向和生命周期必须宿主实测，不能把编译等同实测。详细转录表、尺寸定义及边界见README的N1章节。


2026-10-10 N1 用户修正（替代前述类型1定位规则）：类型1辅助线直接是悬臂L1，起点为连接板框架侧外表面，Root=0，构件A长=线长；不读设备/管道外径，不减D，不加150，不读取原EndMargin偏好。类型1未知载荷位置，不计算允许荷载，不借用L1伪造a；类型2保留中心距L→L1及a查表。类型切换必须取消旧预览、使延迟回调revision失效并要求重新点取，禁止按新类型重解释旧线。两种类型都有ShowPreweld勾选，透明度0.75、向设备侧伸出、与N4相同的配对N8参考板+Φ100×4占位管，D>2T；占位不是NGEN1制造件，不能计入BOM。类型1仅勾选时读取D，类型2始终读取D；ShowPreweld与D纳入PageLastInput，参数改动黑点/确认失效，参考占位随预览生命周期且确认后保留。测试覆盖类型1对隐藏无效外径/D的独立性、占位校验和类型2几何基准。详细规则以README最新N1章节为准。


2026-10-10 N1 类型2搭接修正：辅助线仍为构件A上翼缘外侧顶面；构件B上翼缘内侧下表面贴合该面，B外侧顶面高出辅助线一个B自身翼缘厚度。角钢读profiles.bin的t，槽钢读tf，不读翼缘宽度B，也不误用构件A厚度。A～E抬高量分别6、7、10、10、11mm；定位使用计划BTopOffsetMm，L1/L2、A缩进10mm及N8生根基准保持原定义。离线检查覆盖五种子项接触面高差，实际贴面相并仍需OPM验证。


2026-10-10 N1类型2截面定位补充（替代槽钢按翼缘厚度抬高的旧规则）：角钢A～C保留B上翼缘内侧搭在A顶面，抬高6/7/10mm；槽钢D/E必须截面中心标高对齐，B顶面相对辅助线为(HB−HA)/2，分别17/20mm。槽钢A末端贴B腹板内侧，ACut=L1−B.tw（D为L1−6.5，E为L1−7），不沿用角钢10mm缩进造成悬空；编号L1/L2定义不变。N1CantileverCheck覆盖中心标高和端面接触，实体相并仍需OPM实测。


2026-10-10 N2 双悬臂架：新增 n2-cantilever，首页当前 24 可用+1占位，以 HomeCheck 为准。仅类型1/2、子项A～D；Domain/Data/Services/Tools/UI/N2Cantilever 分层。辅助线设备中心→立管中心，A/B 顶面同线标高；L2 遵循 N4 的双 A 轴间距，最小310（A/B/C）或390（D）、最大1000。生根 √(R²−L2²/4)+D；类型1 L1=L−生根−S（S=管半径+管托高），类型2 L1=L−生根。类型1 B面在生根+L1，A长L1+50；类型2 B面在L+L3及L−L4，两B背靠背向外开口，A长L1+L3+B宽+50；L4=0取消内B、相等省略L4。两A镜像向外开口，B实长L2−A宽；A/B一律顶平，禁止套用N1角钢搭接抬高或槽钢中心对齐。a=L−R查表，禁止空档外推。复用profiles.bin、SteelMemberFactory、N8Builder与只读辅助线转换；可选75%透明双预焊件占位，非制造件、不进清单。单Cell预览，参数黑点/确认失效、失败保留所有权、revision防旧回调、取消/离开清理；确认才AttachN2Cantilever批写公共库，总成1、A2、B1/2、N8板2及对应双份螺栓，定义名固定N2_DOUBLE_CANTILEVER与角色。Development/N2CantileverCheck主工程排除，详细转录表与尺寸定义见README；宿主布尔相并和交互仍须实测。


2026-10-11 沿轴定位：原 TrunnionSlideTool 替换为共享 Tools/AxisPlacement/AxisSlideTool，耳轴及八种管夹使用同一轴向状态机。Services/AxisPlacement/AxisPlacementCalculator 纯计算统一轴向正负号/偏移/范围，数值超界拒绝、动态端点截断；新测试 AxisPlacementCheck 主工程排除。罗盘 X 沿轴、Y/Z 零锁，捕捉强制开启后恢复；保存原点/旋转/模式/启用及原可表达锁状态，SDK Locked 只读须用 SetContext 恢复。基点十字/轴线/投影连线仅 TempDraw，不写模型。页面显示基点含义、XYZ、本次和累计偏移；偏移输入脏状态禁确认/黑点，应用或更新预览才生效，输入不持久化。A1 辅助线点击点横向偏差保持，平行移动轴经过原点，管道及其他类型按轴线定位；滑动保留 A1 方向与参数，E1 计划中心同步。管夹动态原型复用现有 Builder/预览计划，不复制建模代码；每帧仅平移。右键恢复原位，取消/换型/退出使 revision 失效，确认仍只在原 Attach 方法写清单；详见 README。AccuSnap 提示、键盘锁定和退出恢复须 OPM 宿主验证。


2026-10-11：全部模型生成/修改入口统一使用 `Services/WriteDuration` 计时。支吊架及围栏等在确认时计量 `PreviewSession.Confirm` 的清单属性写入，N1/N2 同样在页面说明和底部状态显示具体耗时；不包含建模、辅助线清理及 UI 等待。管口/方形人孔在预览 AddToModel 时计量模型写入，确认时显示最新成功预览的写入耗时；罐壁人孔/型钢截面计量 AddToModel，型钢扫掠计量 Statistics.Attach，管道对齐计量 Apply。小于 100 ms 用 ms，达到 100 ms 用 s，保留至三位小数，正值小于 0.001 ms 显示 <0.001 ms。以后新增写入功能必须复用该计时器并显示结果。离线验证：Development/WriteDurationCheck。

放置管夹的“沿轴滑动”按钮位于“更新预览”右侧；生成预览后使用，基点坐标和累计偏移在其下方显示。发布时需同步 bin/Release/net48_full 与常规 net48 DLL；宿主占用常规 DLL 时先退出 OPM，再运行 Deployment/install_new_version.ps1 更新，重新启动 OPM 加载。


2026-10-11：放置管夹界面精简为当前 DN、保温/保冷厚度及预览编号；不默认展示查表、几何细节或长规格说明。轴线识别说明转为预览悬停提示，轴偏移规则转为基点悬停提示；基点 XYZ 保留。点取与预览 PlacementPanel 固定在 Grid 底部 Auto 行，仅中间参数行滚动，预览文本限制高度避免挤占参数区。仅调整展示，建模计算及清单写入不变。


2026-10-11：T4 参数区将常用尺寸（DN、隔热 B、管托 L）与编号设置分组。编号设置 Expander 默认收起，前缀/温度/材料/F 各有独立标签；控件名称、输入保存与参数更新事件保持不变。附加模型勾选同行排列。摘要展示实际 DN、隔热厚度、长度，并按 T4ShoeCatalog.MatchDn 与保温属性是否存在明确标注来源；不改变自动读取与输入兜底逻辑。参数区独立滚动，底部定位操作保持固定。


2026-10-11：T4 温度代码下拉 A～E（默认 A），材料代码下拉 C1/C2/A1/A2/S（默认 C1），F 下拉“不带 F”/“带 F”（默认不带）。ComboBoxItem.Tag 为写入编号的代码，标签温度范围不进入编号。保持有效上次选择，旧空白/无效温度与材料回落到新默认；无效 F 回落为空。选择变化沿用参数更新/预览与保存流程，不自动改隔热厚度。


## D2 端焊悬臂架（2026-10-11）

首页 `d2-cantilever`，支吊架类。分层在 Domain/Data/Services/Tools/UI 的 D2Cantilever；九子项 A/B/C/D/E/F/G/H/J，无 I。按用户确认本次不带 D1 筋板、不实现 D3。对应型钢依次 ∠50×6、∠75×7、∠100×10、[12.6、[16a、H125×125×6.5×9、H150×150×7×10、H200×200×8×12、H250×250×9×14。真实轮廓与截面尺寸取 profiles.bin，经 ProfileLookup / SteelMemberFactory 建模，钢构件使用 SupportSteelAppearance。

水平辅助线起点为生根端，终点为悬臂末端，长度为 L，标高为承载顶面；反向仅交换建模基准，不改源线。辅助线允许两端高差 ≤1 mm。B 为生根面至荷载中心的距离，独立输入，要求 0<B≤1000 且 L−B≥150 mm。荷载按 B≤250/500/750/1000 分档，水平=垂直×0.3，空档显示未给出荷载，禁止外推。编号 D2-子项-L，无筋板时省略 h×w。

起点可附加一套 G2 端板及四根膨胀锚栓，复用三角架 G2AnchorCalculator/Builder，子项 A～D、外移量可调，孔距按截面最大尺寸下一档 25 mm 模数及 G2 下限确定。端板朝向随辅助线；构件 A 起点为外移+板厚，实长 L−起点，末端保持 L；拒绝端板占用荷载点。

预览为一个 Cell，取消/右键/离开清理，失败删除的新 Cell 持续保存所有权；参数变化禁确认并显示更新黑点，成功更新清除。确认时 `Statistics.AttachD2Cantilever` 才一次写入公共清单，固定 Assembly/MemberA/G2Plate/G2Bolt ItemType 名，实例编号、L/B、实长不进入类型定义名。确认显示统一写入耗时；参考线只读且不能删除，活动模型线默认保留。输入由 PageLastInput 保存，底部操作区固定。

首页更新为 25 个可用功能、1 个占位卡，支吊架入口 16 个；标准编号覆盖从 37 增至 38，另有未单独编号的弯头垫板。离线检查 Development/D2CantileverCheck 覆盖九子项真实轮廓、全部荷载边界/空档、端板扣长及非法输入；HomeCheck 验证入口与顺序。OPM 实体、参考线定位、取消与清单仍需宿主实测。


### D3 侧焊悬臂架合并（2026-10-11）

首页入口改名“悬臂架”，保留 PageId=d2-cantilever 及既有 D2 保存参数；页内选 D2 端焊或 D3 侧焊。D3 实现类型 1/2、子项 A～G：角钢 ∠50×6/∠75×7/∠100×10，槽钢 [12.6/[16a/[20a/[25a。D3 F/G 荷载分别 31/15/8.8/5 与 40/20/12/6.8 kN，不能沿用 D2 的 H 型钢及其荷载。水平荷载仍为垂直×0.3。

D3 整条辅助线是完整构件长度 L，起点直接定位截面外角；角钢 outer_corner、槽钢 lower_left 轮廓沿 -Z 定向，转换后为上翼缘腹板外侧角点。横向偏移为 0，不能像 D2 一样再减半个截面宽。D2 原居中横向定位不变。D3 类型 1 生根站位为起点，余量 L−B≥150；类型 2 既有钢结构中心为辅助线中点，余量 L/2−B≥150，构件整段连续、实长 L。既有钢结构不生成。反向交换辅助线端点并翻转局部轴。

D3 不附加起点端板；D2 的 G2 端板选项仅在 D2 显示。编号 D3-类型-子项-L。复用同一计算器、Builder、预览会话及确认流程，D3 使用独立固定 Assembly/MemberA ItemType 名和 D3 Cell 名，不覆盖旧 D2 统计。切换架型取消旧预览并清空定位，重置可用子项/类型与默认名称；参数更新黑点和写入耗时规则保持。D1 筋板仍未实现。

新增 D3 后首页入口数不变（25 个可用，支吊架入口 16 个），编号覆盖增至 39 种，另有未编号弯头垫板。Development/D2CantileverCheck 同时覆盖 D2 回归、D3 两类型七子项、荷载边界、真实截面角点、双侧余量与编号；OPM 模型效果、侧焊角点与生命周期须宿主实测。


### G11 混凝土上生根的悬臂架（2026-10-11）

“悬臂架”页内新增 G11，支持类型 1～5、子项 A～D，沿用 PageId=d2-cantilever。独立 Domain/Data/Services/G11Cantilever 负责表格、纯计算和几何，复用现有页面、点取、预览会话及确认流程。新增代码采用清晰命名、四空格缩进、独立行大括号及 XML 文档注释，兼容 C# 7.3。

辅助线起点为悬臂起点，长度为完整 L，标高统一为构件顶面；反向交换两端。类型 1 腹板侧面两根锚栓，沿轴站位 75、75+S。类型 2/3 增加同规格竖向连接段，长度 S+150，分别位于横担顶面以上/底面以下，锚栓距连接段端部 75，墙面外法向沿悬臂。类型 4 角钢翼缘在底部，锚栓向下入楼板；类型 5 翼缘在顶部，锚栓向上入楼板。槽钢复用真实轧制轮廓。既有混凝土不生成，C 为表给混凝土边距，须按实际结构核对，不根据辅助线推测混凝土边界。

A/B/C/D 分别 ∠50×6、∠75×7、∠100×10、[16a；膨胀锚栓 M8×80、M12×120、M16×140、M20×180，各两根；S=75/100/125/150，C=75/100/150/200 mm。锚栓复用 G12 的 G2AnchorCalculator / BuildSingleBolt；板厚参数换成实际腹板或翼缘厚度，校验有效埋深并重算套管长度。G11 不附加 G2 端板。

B 独立输入，0<B≤1000 且 B≤L；类型 1/4/5 校验第二根锚栓及垫圈不超出横担。G11 图中没有给出末端 150 mm 限制及水平荷载系数，禁止沿用 D2/D3。荷载按 B≤500/750/1000 查询：A=0.5/0.2/空，B=2/1/空，C=空/4/2，D=空/6/3 kN；空档只提示，不外推。

编号 G11-类型-子项-L。确认时公共清单写入独立固定 G11 Assembly、MemberA、MemberAConnection（仅类型 2/3）、MemberB ItemType；竖向段计实际长度，两根锚栓计总长和数量。预览不写清单，取消/切换/离开清理，参数修改禁确认并显示更新黑点。写入耗时继续使用 WriteDuration，低于 0.1 s 显示 ms，其余显示 s。

首页仍为 25 个可用入口加 1 个占位，支吊架入口 16 个；标准编号覆盖增至 40 种，另有未编号弯头垫板。Development/D2CantileverCheck 共 4231 项检查通过（含原 D2/D3 的 1817 项回归及 G11 五类型全部表格、荷载边界、方向、埋深、截面顶面、非法输入与稳定编号）。HomeCheck 通过，完整 Release 编译为 0 警告、0 错误。OPM 中的原生实体、墙/楼板贴合、交互取消及清单写入仍需宿主实测。


### G11 连接段朝向及下置角钢贴合修正（2026-10-11）

根据宿主试放反馈修正类型 2/3：槽钢连接段绕竖轴转 90°，截面宽轴沿横向正方向、高轴沿悬臂反方向，以 lower_left 和 X=截面高度定位；开口与横担相同，腹板外侧共面。墙面锚栓穿过连接段翼缘，以 tf 而非 tw 重算露出长度、有效埋深和套管长度，仍为两根且 S 不变。

类型 3 角钢连接段上端定位于 Z=−t（横担水平肢下表面），侧面定位于 Y=−B/2+t（横担竖直肢内表面）；不再定位到横担最低点 Z=−B。锚栓横向位置随连接段平移 t，竖向站位仍距连接段端部 75、75+S。类型 2 角钢及类型 1/4/5 保持原定位。Domain 保存连接段三向插入点，Calculator 推导贴合位置，Builder 消费该定位；清单长度、编号、荷载及数量不变。

D2CantileverCheck 现为 4501 项通过，新增检查直接使用真实轮廓核对开口、翼缘受夹厚度及两个贴合面；保留全部 D2/D3 回归。OPM 实际贴合、轧制圆角焊接区域及原生实体仍需重新试放。


### 灭火器箱 C# 迁移（2026-10-11）

首页新增“灭火器箱”（PageId=fire-cabinet），含“生成箱体”和“统计与导出”两个页签。迁移来源为 `灭火器箱/灭火器箱（带灭火器模型）.py`，原脚本保留；运行时不依赖 Python。支持 XMDDG12/22/32 三种箱型、干粉/二氧化碳/水基/洁净气体类型及原容量范围，保留最小合格箱型和内置模型的就近容量、空间校验规则。点取基点为箱底前侧中心，可设置平面角度；构造圆角空心箱体、箱盖、提手、正面/顶部文字和两具灭火器外观。内置外观使用原华海 MF/ABCE 干粉模型配方，并非各实际类型的独立外形；界面显示配置规格和外观规格，不能混作实物型号。

新增代码按 Domain/Data/Services/Infrastructure/Tools/UI 分层，采用四空格缩进、独立行大括号、清晰命名及 XML 文档注释，兼容项目 C# 7.3。`Resources/fire_extinguisher_recipes.json` 嵌入五种容量的原外观配方；仅开发时运行 `Development/export_fire_recipes.py` 从原脚本 AST 白名单提取，无需加载 Bentley Python 模块。JSON 必须保持无 BOM UTF-8。

预览创建原生 Bentley 元素和嵌套 Cell，确认才写入 ItemTypes；更新失败保留可清理的旧预览，参数变化禁用确认，取消/离开清理预览。两具内置模型须同时建成才加入箱体；若内置建模失败，明确提示空箱，实际模型数量记 0，配置灭火器数量仍记 2。确认写入耗时使用 WriteDuration，低于 100 ms 显示 ms，其余显示 s。

统计使用独立 `FireProtectionComponents` 库及固定 `FireExtinguisherBoxWithModel_CSHARP` 类型，不并入支吊架清单。写入原 31 个字段并增加 ActualInteriorModelQuantity。扫描当前 DGN 的全部模型，兼容原带模型脚本的 `FireExtinguisherBoxWithModel_` 类型前缀；不读取另一普通空箱脚本的不同前缀。汇总箱体数量、配置灭火器数量、实际内置模型数量，支持 Excel（汇总/明细）和 JSON。旧数据没有实际数量字段时，仅依据已存 InteriorModelCell 推断，并在界面说明，不能核实旧模型是否实际生成成功。

首页为 26 个可用入口加 1 个占位，支吊架标准数量不变。FireCabinetCheck 的 604 项离线检查覆盖原 Python 29 组选型对照、几何配方、数量和旧数据汇总、Excel/JSON 导出；HomeCheck 和既有 SupportStatisticsCheck 回归通过。OPM 原生几何、文字朝向、点取/取消和 EC 读写仍需宿主试放确认。


### 轻便消防水龙柜迁移与细节建模（2026-10-11）

首页新增“轻便消防水龙柜”（PageId=hose-cabinet），包含“生成柜体”和“统计与导出”。独立 Domain/Services/Infrastructure/Tools/UI 的 HoseCabinet 模块迁移 `轻便消防水龙柜/轻便消防水龙柜.py`，原脚本保留，运行时不依赖 Python。默认 550×160×1200 mm、隔板高 550 mm、MFZ/ABC4 两具；支持修改尺寸、型号、数量、内部设备开关及绕竖轴角度。点取基点为柜底前侧中心，局部 X=宽/Y=进深/Z=高，正面朝 −Y。

柜体采用开口钢壳、隔板、双观察窗柜门、圆柱拉手及两处正面标识。灭火器复用既有嵌入华海 MF/ABCE 外观配方及 Builder，按原型号容量解析、就近映射、成组居中与软管外伸净距规则选型；实际配置型号与外观规格分别保存。P380 卷盘增加八孔侧板、真圆环轮缘、轴盖与紧固件、背部支架和七层六圈连续三次样条卷绕软管；DN25 给水接口增加真实内孔、六角接头、密封圈、连续螺旋螺纹、快接套筒和锁紧环，阀门手轮改为轮缘与辐条，喷枪设空心 φ6 喷口。新增卷绕和接口属于展示细节，不能作为制造详图或将外观路径长度当作 30m 产品的精确长度。

新增非有限输入、最大尺寸/数量及观察窗、把手、标识和 P380 的实际包络校验；原脚本仅比较卷盘直径，遗漏了固定中心、柜壁、盘宽和轴盖突出。内部设备任一建模失败会明确报错并阻止确认，不静默改为圆柱或留下部分内件。预览更新先创建后替换，取消/右键/离开清理，确认才写清单；WriteDuration 统计确认写入耗时，低于 100ms 用 ms，其余用 s。

消防库仍为 FireProtectionComponents，固定 ItemType 为 LightHoseCabinet_CSHARP；读写边界提取为 FireComponentStore，由灭火器箱和水龙柜共同使用，各自保留独立前缀和数量契约。统计扫描当前 DGN 的全部模型，兼容原 LightHoseCabinet 前缀。保留原 29 个属性并增加 ActualExtinguisherQuantity、ActualReelQuantity、WithEquipment、HeadingDegrees、GeometryVersion。BomJson 仍按 Python 小写字段写入，C# 属性使用 PascalCase 并显式映射。器材清单保存原八项配套器材及可选第九项灭火器，数量按 CabinetQuantity 倍数汇总；关闭内部设备时清单保留配置，实际数量为 0。旧记录未保存实际数量时，界面和 Excel 标记未记录，不从型号推断生成成功。

统计页提供柜型/灭火器汇总，Excel 导出柜型汇总、配置器材、柜体明细三表，JSON 包含逐元素元数据及器材合计。缺失、损坏或格式不匹配的旧 BomJson 按已存尺寸和灭火器配置重建。开发脚本 Development/export_hose_reference.py 通过 AST 白名单生成 98 组原 Python 对照，逐值核对五种共用灭火器配方。HoseCabinetCheck 的 719 项检查覆盖选型、数量、空间边界、螺旋半径误差及 C1 连续性、旧清单自定义数量、空柜、跨模型汇总与 Excel/JSON。

首页增加至 27 个可用入口加 1 个占位，支吊架编号种类不变。代码按清晰职责、四空格缩进、Allman 大括号及 XML 文档注释组织，兼容 C# 7.3。OPM 原生布尔、样条扫掠、文字朝向、点取及 EC 读写仍需宿主试放验证。


### 水龙柜软管放样简化（2026-10-11）

根据宿主放置卡顿反馈，替代原七层共42圈软管及层间连接：仅生成一条单层五圈螺旋线，半径145 mm、轴向90 mm、管径16 mm，每圈八段三次样条，圆截面一次放样。螺距18 mm大于管径，避免邻圈接触；控制点从七层合计2023个降低到121个。接口九圈螺旋螺纹替换为三道真圆环外观示意，水龙柜不再执行该细螺纹扫掠。保留柜体、卷盘侧板、接口、统计属性及器材配置；新生成预览生效，不自动修改已有单元。

HoseCabinetCheck 改为验证实际使用的单层路径包络、C1连续、半径误差小于0.2 mm、控制点数量及螺距安全间隙。原选型与清单回归保留。代码减少了扫掠次数与路径复杂度，宿主实际耗时仍须重新试放测量，不能仅依据编译声明不卡顿。

## 离线授权维护约定（2026-10-11）

- Domain/Licensing 只定义签名载荷；Services/Licensing 校验格式、签名和授权范围；Infrastructure/Licensing 负责机器身份、公钥资源、本地文件及工作区单例；UI/Licensing 只管理激活表单。
- ProductId=SteelSectionProbe、SSP1 编码、公钥和 JSON 字段名称必须稳定，插件升级不能自动生成新密钥。永久授权不检查系统时间或到期日。
- Development/LicenseIssuer 为独立作者工具，必须从主工程 Compile 排除。任何签发、私钥生成或私钥内容不得编译/嵌入客户端 DLL。私钥必须保持 Git 忽略，不得随发行包分发。公开资源 Resources/license_public_key.xml 可以进入 Git。
- activation 是工作区工具页，不是业务模块，不加入 HomeFeatureCatalog，不计入业务使用次数或首页功能总数。所有业务页统一经 WorkspaceView.OpenPage 授权检查；新增独立 Key-in 或绕过工作区的业务入口必须自行检查授权，不能只靠禁用按钮。
- LicenseRegistration.Activate 必须先校验、后原子保存、最后更新缓存。无效文件保持未激活并提示，失败激活保留原授权。不得把验签放在鼠标动态回调中。
- 机器码采用 Windows MachineGuid 的 SHA-256 派生值（128 位十六进制展示），同一安装稳定，重装/克隆限制必须如实说明。纯离线永久方案不宣称可远程撤销或不可破解。
- 检查工程 LicenseCheck/LicenseUiCheck 都从主工程排除，不依赖 Bentley。SDK 编译和 WPF 离线布局通过不等于 OPM 完整交互验证。

## 作者页与通用试用维护约定（2026-10-11）

本节替代前文“只有永久授权”“授权有效状态只按非空判断”和“版本升级修改首页 Text/ToolTip”的旧约定。

- App/ProductInfo.cs 统一作者名称、邮箱和程序集信息版本。版本唯一来源仍是 App/AssemblyInfo.cs，首页与作者页自动显示，不能重新写死 XAML 版本文字。
- about 与 activation 都是无授权即可进入的工作区工具页，不加入 HomeFeatureCatalog 或业务使用统计。AboutPage 只允许用户主动复制邮箱或打开 mailto 草稿，不能自动发送邮件。
- 旧永久码 Version=1 / FullPermanent / machineCode=本机码 / 无 expiresUtc；新试用码 Version=2 / FullTrial / machineCode=* / expiresUtc=issuedUtc.AddMonths(1)。SSP1 外层格式不变，验签必须在解析之前，不能因新增字段更换公钥或私钥。
- LicenseValidity 对永久授权不检查日期，对试用使用 [issuedUtc, expiresUtc)；一个月是自然月，覆盖月底、闰年、跨年。试用无需机器码，不能把机器身份读取设为所有授权的前置条件。
- LicenseRegistration 的缓存保存已验签载荷，IsActivated 每次判断当前有效期，不能缓存试用的永久 true 状态。Activate 先验证签名与日期，后保存，最后更新载荷；禁止用试用覆盖永久授权。注入时钟仅用于可重复离线检查。
- WorkspaceView 用 1s DispatcherTimer 检查试用，过期通过 OpenPage 切至激活页，复用 OnDeactivated 清理；关闭工作区停止并解绑 Timer。不要直接删除其他模块的正式模型元素。同步建模阻塞 UI 时，计时回调需等宿主恢复调度，不能宣称可强制中断同步 native 调用。
- 纯离线校验依赖系统时钟，无可信服务器或防回拨高水位；可被调回有效期内，不宣称完整防时钟攻击。未使用服务器、账号、到期后台网络任务或机器绑定试用码。

2026-10-11：首页版本按钮放大为 176×42 DIP，复用 PrimaryButtonStyle 深色底，金色版本与箭头、白色作者文字。内部 Grid 和各项均居中，版本/作者统一 18 DIP 行高，移除箭头负边距，保持 About_Click 导航。520/640/840 DIP 离线布局及 Release 编译通过，已更新加载目录 DLL。

2026-10-11：按用户反馈替换首页版本按钮深色填充：白色卡片底、主题黄色 1.5 DIP 边框，悬停/按下保持黄色边框；版本和作者文字统一 13 DIP、20 DIP 行高并居中，按钮仍为 176×42 DIP。此记录替代上条深色底说明。

2026-10-11：N4 的“设备与跨距尺寸”区域改为等宽双列（间隔 12 DIP）；左列 L2/L3/L4，右列设备外径/预焊件长度/预焊件参照开关。只调整共用 BracketPage.xaml 的 DoublePanel 布局，保留所有控件名称和参数事件，N3 隐藏该区域的行为及建模、编号、统计逻辑不变。
2026-10-12：按用户明确要求新增独立模块“大管支撑小管” `q1-small-pipe-support`，作为第 28 个可用首页功能（另有 1 个占位），不加入管夹下拉。分层位于 `Domain/Data/Services/Tools/UI/Q1Support`，复用 `PipeClampLocateTool`、`PipeClampReader`、`AxisSlideTool`、`A1ClampBuilder` 和 `SteelMemberFactory`。此处是用户指定独立入口的例外，不改变其他新增管夹共用入口的规定。A1 Builder 第二颗螺母上界使用 `NutLow2Mm + NutHeightMm`，原 A1 数值不变，Q1 可留角钢厚度间隙。

Q1 类型1/2为小管在下/上、两管垂直，类型3/4为小管在上/下、两管平行并带现场垫板。小管DN15～100按所附表选A/B/C角钢及0.6/1.6/3kN荷载；H为图示径向中心标高差，最大1000mm，角钢长度从最外侧管卡腿中心各延长50mm。类型3/4垫板尺寸未标注，按实际管至角钢净空取厚度、边长取小管螺杆直径两倍，属于建模约定，不应声称为图纸规定尺寸。固定统计角色名为Q1的MEMBER_A/BIG_U_BOLT/BIG_NUT/SMALL_U_BOLT/SMALL_NUT/PAD，确认时一次WriteRecords，不在动态预览写统计。预览会话保留全部删除失败元素所有权，延迟点取回调用revision、滑动锁定回调用slideRevision阻止跨页面和过期参数回调。PageLastInput保存类型、小管DN、H及镜像；参数编辑立即禁止确认。

2026-10-12 Q1 宿主反馈修正：类型1/2小管卡开口改为局部+X，中心同时移动到对应角钢翼的−X侧，不能仅翻开口而不改中心，否则螺杆与孔错位。取消整组自由旋转，按类型固定上下方向；镜像仅反转局部Z（大管横向侧），保留大管轴X和高度Y。点取后直接生成预览，页面按统一管夹点取区提供沿轴滑动、数值偏移与应用偏移。共享AxisSlideTool只平移动态原型，锁定后重建可取消Cell；右键恢复本次移动前位置。数值编辑立即禁止确认，越界和非有限偏移拒绝。Q1 674项纯计算及6种WPF尺寸验证通过；首次构建因OPM占用旧DLL而输出至net48_full；用户关闭OPM后已重新编译正常net48 DLL并同步备用件，SHA256一致，授权及无授权版零警告零错误。宿主内实际镜像、管卡朝向和滑动仍需用户验证。

2026-10-12 Q1 贴管优化：原角钢定位沿用A1标准螺母站位，造成管壁净隙偏大。改为管外半径+2mm定位角钢近侧面，2mm为图纸未注明时的建模净隙约定；类型3/4垫板厚度同步为2mm。Q1螺母夹住角钢厚度，直腿末端留max(3mm,螺杆直径/2)丝头，StraightLegMm只覆盖Q1的A1构建计划，不能修改共享A1ClampRow或独立A1标准D。Q1清单U型螺栓记录实际直腿D和中心线展开长度。已有模型需重新生成。

2026-10-12：在“大管支撑小管”模块内新增Q2系列，沿用q1-small-pipe-support PageId，不新增首页卡片。Domain/Data/Services/Q2Support独立定义四类型、角钢及荷载表，Q1SupportPage和预览会话根据系列分派，切换系列清理旧预览并终止定位/滑动。Q2小管DN15～150，Q1保持DN15～100；页面恢复选型通过领域DN数组映射，不从界面标签反向解析尺寸。A子项L>500、全部L>1000拒绝；类型1/2自由端距150，类型2根端和类型3/4两端距从外侧管卡腿各50。类型3/4增加立管承重块，按用户表DN15～65为50×30×10、DN80～150为100×50×10，解释为沿立管焊接长边×径向短边×切向厚度，底面落在角钢顶面，管侧真圆柱差集贴合。固定A每腿双螺母同在外侧，导向G每腿一内一外并保持U弧至管壁3mm；A1ClampPlan.LegSpacingMm只覆盖Q2导向计划，A1 Builder据其统一绘制弯弧/腿/螺母孔，公共A1表不变。Q2固定统计角色MEMBER_A/BIG_U_BOLT/BIG_NUT/SMALL_U_BOLT/SMALL_NUT/SMALL_BLOCK。类型3/4只给被支撑小立管加承重块，主管不建块、不写BIG_BLOCK清单，不按承重块表限制主管DN；DN300等主管应正常接受。宿主实体及EC仍须实测。

2026-10-12 Q2主管承重块纠正：用户明确主管立管不加承重块。删除BigBlockMm领域字段、主管块生成与BIG_BLOCK统计记录，同时移除主管按承重块DN15～150表拒绝的逻辑；该表仅用于被支撑小立管。截图组合类型4/B/DN300主管/DN80小管/L500通过回归；各A1主管管径及A/G、镜像组合按合理L验证，共16706项计算检查通过。已有错误生成件需重新生成，不批量修改历史模型。

2026-10-12 Q2承重块方向修正：用户明确长边焊在管道上。50×30×10对应沿立管高50、径向伸出30、切向厚10；100×50×10对应沿立管高100、径向伸出50、切向厚10。块底仍落在角钢顶面，长边管侧保持真圆柱贴合；清单DesignLengthMm同步使用沿管长边。只生成小立管承重块，主管不加块。

2026-10-12 Q2类型4按用户要求恢复绕主管立管旋转选角：点取后静默RetireForHandoff交接A1ClampOrientationTool，不调ExitTool再立即安装新工具。使用规范化朝上的主管轴作为角度罗盘法线，Q2SupportCalculator.Axes按AngleDeg旋转径向X/Y，Builder所有构件共用该坐标架。角度只用于Q2类型4；Q1及Q2类型1～3保留固定方向。页面“调整角度”可再次进入，锁定后可沿轴滑动；角度写入总成实例Specification。参数编辑、右键、切换系列/类型、离开页面及关闭均结束本页面持有的方向工具，revision使过期回调失效。

2026-10-12 首页UI原型v4：用户明确只改主页UI、不改功能，改前已提交77bac1e。首页窗口固定400×880 DIP，MainWindow仅首页使用无原生外框与WPF32标题栏，模块页恢复原Sizable、560宽和此前模块高度，不能将未改模块强压到400宽。HomePage内159头部/47统计/131工具/46共享底栏，详细78、最近与简约47、两列间距6、滚动条6、圆角6；头部网格14与副标题字距1.2取自原型。UI/Home/HomeTheme.xaml隔离于全局Theme，HomePresentation仅显示代号，HomeTrackedText仅绘字距，所有Domain/Data/Services/Tools/Infrastructure/Registration/Resources/App文件保持基线内容。SVG品牌及17个HomeIcon几何不替换。模块与数字来自真实HomeFeatureCatalog/偏好，禁止把原型18项和示例调用数写入业务数据。

主页交互按原型单击选中、双击/箭头/Enter打开；继续FeatureRequested→OpenPage，不另开业务入口。原五级星标、≥3置顶、授权守卫、偏好JSON和使用统计均保留。重置图标默认清展示筛选，右键仍提供原统计/星标重置及确认。进入模块后原PageHost外边距14,4,10,10及36底栏恢复。HomeUiCheck以真实页面+隔离夹具覆盖33项UI检查并渲染1/1.25/1.5/2倍DPI；不得用截图代替OPM宿主拖动/最小化/切页实测。后续模块UI改造另行授权，勿扩大本阶段范围。


2026-10-13 Q1/Q2模块页UI原型v4：改前提交已确认的首页35c0192。仅q1-small-pipe-support使用与首页相同的400×880 DIP固定外框；原型32标题栏、63模块头、34输入框、98结果卡、302 Q1底部操作区与46共享底栏。Q2增加的系列/子项/立管选项置于参数滚动区，类型4保留独立角度按钮，操作区增加40 DIP且仍固定在底部。其他模块恢复原560宽、原外边距与36底栏。QSupportTheme局部加载；新增Presentation partial只做窗口导航与数值步进，步进写回原TextBox并经过原TextChanged；二维示意不参与建模。原Q1SupportPage.xaml.cs、领域、目录、计算、工具、统计和持久化均保持35c0192内容，原控件名、参数事件与业务按钮处理函数已逐项对照，品牌SVG路径一致。37项WPF展示/滚动/DPI检查、33项首页回归及16976项Q1/Q2真实计算检查通过；离线展示夹具不运行Bentley工具，不代表OPM点取/旋转/滑动/生成及窗口切换已实测。


2026-10-13 查询与授权工具页UI：改前提交Q1/Q2界面82a7771。构件特性查询、支吊架统计、软件激活、联系作者四页标记prototype-v4，沿用400×880固定窗口、32标题栏、63网格模块头、35卡片头、34控件和46底栏。共用UI/Prototype/PrototypeChrome与PrototypeTheme，仅已改页加载；当前原型仅有Q1示例，四页是沿用其规格的扩展。查询表格保留所有列、绑定及横向滚动；Excel/JSON导出、连续点取、单位选择、完整EC、复制结果、授权校验与作者联系方式逻辑不变。四页原xaml.cs以及全部Domain/Data/Services/Tools/Infrastructure保持改前内容；原控件、业务按钮事件和数据列已对照。共用状态栏改为10.5字、14行高、最多两行，长内容末尾省略并提供全文悬停提示，错误颜色与消息来源不变；其他未改模块36底栏仍保留。ToolPagesUiCheck通过52项真实XAML展示/布局/DPI检查（查询使用展示夹具，作者/激活链接原逻辑及隔离服务），首页33项和Q1/Q2界面37项回归通过，构件特性纯计算、支吊架汇总/JSON/三表Excel与111项授权回归通过。授权/无授权Release零警告零错误，常规net48已同步net48_full；宿主实际操作与原生外框切换仍需OPM验证。


2026-10-13 九个建模页UI：改前提交114e0d9。型钢、普通围栏、罐体盘梯、管道标高对齐、罐壁人孔、实体管口、方形人孔、灭火器箱、轻便消防水龙柜九页使用prototype-v4与400×880固定窗口，沿用32标题栏、63网格头、35卡片头、34输入、6外层滚动条和46双行状态底栏。ModelingTheme仅九页加载；蓝色建模图标由PrototypeChrome的展示配色属性实现，原SVG与其他工具页默认紫色不变。参数可滚动，原操作区固定底部；型钢/罐壁人孔/管口的原创建或点取卡从整页滚动移至底部，型钢卡片展示序号按参数→截面参数→创建方式重排。消防生成/统计两页签、所有表列及绑定保留，表列最小显示宽度允许横向滚动而非挤掉内容。九页原xaml.cs、所有Domain/Data/Services/Tools/Infrastructure/App均保持114e0d9内容，原具名控件、默认值、隐藏范围、选项及业务事件已对照；不修改点取、建模、统计、持久化或授权逻辑。ModelingUiCheck使用真实XAML和原截面预览控件，以空回调和隔离数据通过100项布局/固定操作/DPI/消防页签及横向列宽检查，四个查询/授权工具页52项回归通过。围栏、盘梯、管道对齐及模拟Undo、人孔、管口、方形人孔、灭火器箱604项、水龙柜689项原业务离线回归通过。实际OPM交互、模型写入和窗口切换仍须宿主验证。


2026-10-13 支吊架全部统一UI：改前提交4a79280，并在仓库迁移备份/UI支吊架改造_20261013_4a79280保存源码ZIP、原型、授权/无授权DLL/PDB与SHA256。新增15份物理XAML改造，N3/N4共用页加现有Q1/Q2一起覆盖17入口；全部固定400×880，参数滚动、操作区固定、类别图标青色，现有SVG与17个HomeIcon几何保持。SupportTheme复用通用控件并保留嵌套TextBlock勾选项；SupportPageTitleConverter只读显示N3/N4标题，业务xaml.cs全部保持基线。SupportUiCheck通过202项布局/分型/固定操作/DPI检查，管夹八面板、立管两组、Q2类型4角度入口、N3/N4标题均验证；原PipeClamp含L7/L8、Q1/Q2 16976项、弯头、G2、立管、E1、N1 120项、N2 199项、N3/N4/N8、D2 4501项、三角/L/门/T/垫板等业务离线检查通过。当前所有UI正式规则集中到Docs/UI规范-v4.md，README、AGENTS第9节及旧首页规则、原型实现说明和UI检查文档同步更新；历史560宽/240×124/12滚动条/深色按钮不再适用。后续所有UI按v4继续，不得改业务工作流或数据。OPM实际操作和原生实体仍需宿主验证。


### U3 带承重块的 U形螺栓（2026-10-13）

在“放置管夹”类型列表末尾新增 U3（DN15～150，1/2"～6"），保留原八项索引。点取不保温立管或竖直辅助线，沿用 A1 罗盘选向、沿轴滑动、偏移、预览取消及确认；确认才写入 U3 Assembly、U形螺栓1、螺母4、承重块1和可选 EPDM1 清单记录。不重复生成已有钢构、管道及另配 Y1/Y2。

- A 承重/固定：每腿两螺母在钢构外侧；G 承重/导向：每腿一内一外，弯弧内面与接触面净间隙3 mm。S1接触面指 EPDM 外表面。标准 A1 目录不修改，仅 U3 计划覆盖中心距、螺母位置和必要的腿长。
- DN15～65承重块50×30×10；DN80～150为100×50×10。长边沿世界竖直焊在管壁上，短边径向伸出，厚度沿切向；贴管面以圆柱相减，块底在输入的钢构顶面。管轴反向不翻转承重块。
- C1：螺栓/螺母Q235B或20、块Q235B；S：均06Cr19Ni10，钢构接触处另配不锈钢Y1/Y2；S1：螺栓/螺母Q235B或20、块06Cr19Ni10、EPDM（≤120°C）。EPDM建模为管卡位置的短环衬垫，不生成保温。
- 手动输入已有钢构厚度、管卡中心至钢构顶面的竖直高度、管壁厚度及S1衬垫厚度。默认10、25、6、3 mm是可编辑建模安装值，并非图纸规定。焊高min(6,管壁厚度)，作为规格标注，不生成焊缝实体。材料代码由用户选取，管壁厚度由用户输入，温度限制为选型提示。
- 编号U3-A/G-DNxx-C1/S/S1。 UI 使用现行 v4 400×880，参数区可滚动，点取与确认区固定。原始资料为用户本次附件，新增纯计算验证并复跑旧管夹检查；原生实体和 OPM 交互需宿主验证。


2026-10-13：STEELPROBE PLACE 仅打开型钢生成页面，不自动启动截面放置；新增 STEELPROBE QUERY 仅打开构件特性查询页面，不自动开始点取。两者沿用 WorkspaceView.OpenPage 的授权拦截、页面生命周期和使用统计。


2026-10-13：修复 A1 等管架在 XY 平面斜管上的定位偏移。E1GuideReader 的共用管轴读取在只有 COM 包围盒时复用 PipeAlignment.PipeGeometryReader 显示几何管轴通道；单条真实曲线不再被忽略。识别为管道且取不到真实轴线时拒绝按包围盒猜方向，提示使用直管中心辅助线。纯选择/投影回归覆盖11个水平角度，原生显示几何和宿主点取仍需实测。

### N3 设备预焊件占位（2026-10-13）

用户授权 N3 开放设备预焊件占位。BracketPage 中仅 N3 显示独立 SinglePreweldPanel，默认关闭、D默认100mm；N3ShowPreweld/N3Preweld在BracketLastChoice独立保存，旧JSON默认不启用。辅助线起点为设备壳、终点为横担末端；反向先交换两端。勾选时D含占位端板，L=线长-D，横担实长=L-T，RootOffsetMm=D。Builder从生根端外移D后创建支架，横担末端不变；两处透明占位分别接横担和斜撑，覆盖原起点至D，复用N8端板和N4空心管参照，不进材料清单。D须有限、大于端板厚度且小于线长；E按扣长后横担减H校验，150mm边界保留。N4的L1推导、预焊件开关与几何布局保留。

参数编辑仍更新E、标记更新预览并禁止确认；占位放在同一个预览Cell中，确认、取消和离开生命周期沿用BracketPreviewSession。此次为用户授权功能变更，N3/N4共用页面源码不再冻结在此前UI-only基线；契约只更新BracketPage及新增字段，保留其他控件约束。92项EquipmentSupportCheck和209项SupportUiCheck通过，授权/无授权Release零警告零错误；OPM原生实体、实际点取、取消及EC写入需宿主试放，不能把离线检查作为宿主验证。

### N3 的 H 为两板中心距（2026-10-13，用户原图纠正）

本条纠正此前N3的错误H定义：H是横担板中心到斜撑板中心的竖直距离，非横担顶面到斜撑板中心。辅助线标高仍为横担顶面；zA=-hA/2，N3类型1的zB=zA-H，类型2的zB=zA+H。纯Calculator输出BeamCenterZMm/BracePlateCenterZMm/BraceContactZMm，Builder及预焊件占位统一消费，禁止另算一次zB。45°斜撑投影为H-hA/2，清单长度随BraceRun更新，筋板位置随交点移动；N8选型、最小H、辅助线终点、D扣长和原E输入约束保留。N3所有子项在最小H的板边净距为20mm，不能通过加大H或减小N8掩盖原基准错误。N4无本次原图，暂保留既有顶面基准及投影，不将N3图直接套用到N4。

改前备份在仓库迁移备份/N3板中心距修正_20261013，含用户原图与源码/DLL。145项设备支架参数检查、211项页面检查及UI契约通过；授权/无授权Release零警告零错误，OPM实体显示、EC及交互尚需宿主试放。旧N3模型需重新生成，不批量修改已有DGN元素。

### N3/N4 斜撑两端剪切延长量修正（2026-10-13）

用户截图反馈斜撑设备端和横担端留斜口。N3/N4共用BracketBuilder，每端固定overrun=50mm对较大截面不足，[10/H100亦无穿越余量。现从本工程型钢目录读取斜撑实际H，调用纯BracketCalculator.BraceCutOverrunMm：hB/2*max(|vz/vr|,|vr/vz|)+10mm。geometric_center轮廓在高度方向居中；整个原端面必须越过相应剪切面，两次原生差集之后仅保留平切面。禁止重新改为固定50或100mm，禁止增加清单长度来补剪切；横担、连接板位置和斜撑设计中心线长度保持本次输入的定义，N4也使用该修复。

改前源码、DLL和用户截图备份于迁移备份/N3N4斜撑剪切修正_20261013。EquipmentSupportCheck新增链接profiles.bin及真实型钢领域/目录，1951项检查通过：六种真实轮廓、N3/N4上下两型、原端面完全处于待删除半空间、完整剪切边界站位、不同坡度延长及非法截面。授权/无授权Release零警告零错误；参数解析和数学切口验证不能代替OPM原生布尔与显示实测，旧模型需重新生成。

### N4 的 H 中心距及四板防碰撞（2026-10-13）

用户要求核实N4的MIN.H是否同步防止N8碰撞。此前N4只修改斜撑剪切，仍保留横担顶面基准；现修正为与N3一致的两板中心距，替代上方所有“N4暂保留原定位/等待原图”的维护约定。共用Calculator的braceCenter=beamCenter±H；45°斜撑投影=H-hA/2，既有Builder字段同时控制斜撑、筋板和预焊占位，清单B长度随BraceRun更新。两页H文案统一，不再有isDouble条件。

MIN.H与MIN.L2的A～F数值390/480/390/480/500/590保持，分别为对应N8外形370/460/370/460/480/570加20。新增ValidateN8PlateSpacing对H和N4的L2按实际板宽/高检查20mm最小净距，不能只依赖静态最小值表。L1、设备外径、D与横担总长推导保留。2394项参数检查包含上下两型、六子项、占位开关和反向的四板两两分离，以及此前斜撑剪切；211项UI检查及契约通过，双版本Release零警告零错误。改前备份在迁移备份/N4板中心距修正_20261013。OPM原生实体/EC/交互须重新试放，旧N4不自动修改。

### 消防柜文字比例隔离（2026-10-13）

用户反馈灭火器箱文字受全局绘图比例影响。Services/FireCabinet/FireCabinetBuilder.Text保留原生文字，构造前显式清除TextBlockProperties的文字样式及注释比例关联，IsViewIndependent=false；RunProperties清除持久样式后最后设置实际毫米字高×UOR/mm。创建后AnnotationHandler.GetAsAnnotationHandler/HasAnnotationScale检查意外残留，失败报错，不静默生成比例异常的标识。实际C#签名已通过ApiDump读取本机Bentley.DgnPlatformNET.dll元数据确认（ClearAnnotationScale、RemoveTextStyle、FontSize、AnnotationHandler）。不改模型比例/全局文字样式，不以除当前比例的逆缩放掩盖关联，也不把文字改为栅格图。

共享的HoseCabinetBuilder两处标识同步受益；预览、确认和普通Cell流程不变。修改前源码、DLL和校验在迁移备份/消防柜文字比例修正_20261013。604项灭火器箱及689项水龙柜计算/统计回归通过，授权/无授权完整编译零警告零错误；这些离线检查不验证Bentley文字布局，宿主需在不同注释比例下生成和切换验证。旧模型及同级Python插件不自动更新，默认TrueType缺字问题未在此次解决。

### 水箱爬梯 C# 迁移（2026-10-13）

新增tank-ladder，首页建模类注册于HomeFeatureCatalog/WorkspaceView；当前29可用+1占位，10建模/17支吊架/2查询。磁翻板液位计仍只有同级Python版本，不属于本次迁移。水箱爬梯分层为Domain/Data/Services/Tools/UI/TankLadder，运行时不读Python。默认水箱2000、顶部角钢净距420、加强撑间距900、角度0，原点为箱顶横向底角钢直角棱线中点；箱底z=原点z-H。∠50x5角钢高600；60x10梯腿顶部外廓340、R150真圆弧、竖向落差H+480、底端距箱底40；梯腿净距为输入宽度减20。φ18踏步长W+10，箱底上300起每300，数量floor(H/300)；60x10支撑长250，箱底上100起按输入间距、左右镜像。保留原布置而不擅改为护笼直梯。

复用profiles.bin的equal_angle/L50x50x5/outer_corner，含真实轧制圆角，禁止复制尖角轮廓。统一UorPerMeter/1000。Builder所有构件均离线；相并顺序底角钢→立杆→梯腿→加强撑→踏步，避免先并两个不接触的立杆。默认相并后封装普通TANK_LADDER Cell，关闭相并也封装单Cell，不散写DGN；此设备附件不写PipeSupportComponents。保护限制H≤50000、20<W≤5000、最大500构件，不声称为设计规范。

页面使用v4的400x880、ModelingTheme、参数滚动及固定操作区，PageLastInput记忆五项。工具Begin幂等并恢复AccuSnap；点取回调只排队坐标，用revision阻止取消/结束/退出后的旧回调。参数变化Invalidate、确认失效与黑点；更新成功才清除。TankLadderPreviewSession保持全部未确认元素所有权，旧删除/新回收失败不丢所有权，可重试清理；确认解除所有权。时间复用WriteDuration格式，不另开进度窗口。以后增加模型文字必须走ModelTextFactory。

改前备份在迁移备份/水箱爬梯CSharp_20261013。AST白名单生成12组原Python布局参考，1208项纯计算/真实会话(API替身)回归通过；首页回归通过，ModelingUiCheck链接真实爬梯Page/Calculator/PreviewSession与隔离模型API，十页121项布局/状态/DPI检查通过，含延迟回调取消和重复关闭。授权/无授权Release零警告零错误；编译及替身不代表OPM实际扫掠/相并、单位、AccuSnap和Undo实测，宿主仍须试放。

### 墙面爬梯 C# 迁移（2026-10-14）

用户要求先提交再迁移，基线7367cca；源码ZIP、原Python、v4原型、授权DLL/PDB及无授权DLL与SHA256备份于迁移备份/墙面爬梯CSharp_20261014_7367cca。新增wall-ladder，Domain/Data/Services/Tools/UI分层，无运行时Python；HomeFeatureCatalog/WorkspaceView同时注册，当前30可用+1占位，11建模/17支吊架/2查询。磁翻板液位计仍未迁移。

竖直辅助线为墙面和爬梯中心投影；低端是地面，高端是平台，水平偏差≤5mm，反向取低端。参考附件逐级GetTransformToParent后换算活动UOR/mm，只读原线。立柱75×12/16/20分别对应线高≤4500/5500/6000，中间拉结不改变选型跨度；延长1200不设横担。默认梯宽中心距400、距墙220、首横担400、中间支架1500、方向0°(+X)、护笼开；通过PageLastInput保存。φ24横担长W+立柱厚+20，最高中心H−50；支架75×10配100×100×10墙板，复用目录L75x75x10/outer_corner的真实圆角，取代原Python两矩形L但保留外形基准。

用户明确全部圆弧须用真实曲线扫掠：墙面爬梯禁止以多段线、短块、弦线近似圆弧，包括任何失败回退。普通护笼10段和顶部倒L组合8段的整条CurveVector均含两段R355真圆弧，使用TryCircularArcFromStartMiddleEnd/CreateArc和BodyFromSweep整体扫掠；只可反向真实路径和换参考方向重试，失败显示构件阶段，不允许假成功。立柱截面/角钢圆角也保留真曲线。护笼50×5，环中心吸附踏步−37，环间距≤1500，顶环顶H+1200；外圈按真实弧长均布11根30×5竖杆。

Builder只返回离线WALL_LADDER/WALL_LADDER_CAGE普通Cell，关闭护笼返回一个Cell。PreviewSession集中写入完整组，第二块写入失败回收第一块；任何删除失败仍保留未确认所有权，确认要求整组有效且解除所有权。参数失效、更新黑点、右键/结束/取消/离开/关闭、revision队列保护及AccuSnap幂等恢复沿用现有规则。不写PipeSupportComponents；未来文字按ModelTextFactory。

护笼120<W<830且距墙>105防端头退化/交叉；W/距墙≤5000、支架间距≤6000、最大500构件是建模保护而非标准。16组原Python布局参考、12372项真实Calculator/Builder API记录/预览会话检查、十一页144项布局/DPI/真实爬梯页面状态及首页检查通过。双版本Release零警告零错误，正常/备用DLL同步。离线API替身只记录调用，不证明内核实体；OPM顶部空间扫掠、截面方向、参考坐标、捕捉、预览/确认与Undo仍须宿主试放。

### 磁翻板液位计 C# 迁移（2026-10-14）

新增magnetic-level-gauge，Domain/Data/Services/Tools/UI/MagneticGauge分层，首页及WorkspaceView同时注册；当前31可用+1占位，12建模/17支吊架/2查询。替代上方“磁翻板未迁移”的历史状态。原Python不修改，C#运行时不读取或启动Python。原Python/README、原DLL/PDB、v4原型及SHA256备份在迁移备份/磁翻板CSharp_20261014。

L1=350～6000，默认1400；原点是下接口标高的筒体轴心，0°接管−X/显示面−Y，绕Z旋转。完整保留原layout构件尺寸/顺序/四种RGB：φ60筒体、上下法兰及螺栓、两侧同向接管和截止阀、真圆环手轮及轮辐、显示框、翻片、刻度、卡箍和排污阀；不擅改成制造规格、不注册智能仪表。翻片偶数2*max(10,ceil(L1/24))，50%红白分界；刻度10mm，50mm长线，无数字。默认365构件/118翻片/141刻度。

圆柱及板件复用SolidPrimitiveFactory，手轮CreateDgnTorusPipe完整真圆环（圆截面沿真圆路径扫掠），禁止折线/分段块回退。所有子构件离线，单位UOR/mm只在Builder转换；单Cell名称MAGNETIC_LEVEL_GAUGE_L1_...，整台预览写入，不散写，不进PipeSupportComponents。原版无模型文字，保持无数字刻度；今后文字强制ModelTextFactory及模型文字规范，不能受全局绘图比例影响。

原Python直接放置改为C#统一的预览/更新/确认。PageLastInput保存L1/角度；Begin幂等、恢复原捕捉/定位，active实例守卫和revision阻止取消/退出后的旧回调。参数失效与更新黑点，失败留旧块且禁止确认；确认解除所有权，关闭/Reset/取消仅删未确认，删除失败保留所有权可重试。模块不更改既有正式模型。

11组AST白名单Python参考、67447项真实Calculator/Builder(API记录替身)/预览所有权检查通过，十二页166项布局/DPI/实际页面状态及HomeCheck/模型文字守卫通过。授权/无授权Release零警告零错误，正常/备用DLL同步。API替身与编译不代表OPM原生圆环、颜色、单位、实际交互和Undo实测，宿主需试放。
