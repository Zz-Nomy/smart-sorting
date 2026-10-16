# 交付证据索引与结论边界

冻结日期：2026-10-17。代码供草稿PR #1审阅，不代表整机现场验收；书面方案与带权重演示包保留本地，未上传学校平台。

## 已有证据

| 证据 | 位置 | 能支持的结论 | 不能支持的结论 |
| --- | --- | --- | --- |
| 43项自动软件检查 | tests；本地work/rules_audit/software_tests.txt | 分区契约11、视觉6、评估6、训练封存2、人工核验10、显示状态8 | 独立分类准确率、硬件联调 |
| 训练元数据 | vision/dualview/reports/training_summary.json | 既有视频原型训练及权重记录 | 真实同步双视图训练、新实物泛化 |
| 377对内部检查 | vision/dualview/reports/internal_evaluation_v2.json | 颜色＋形状均正确377/377，限既有相关素材且假定输入配对正确 | 独立测试100%、现场成功率、配对准确率 |
| 24对轻微扰动 | vision/dualview/reports/perturbation_check.json | 八对示例的派生变化检查 | 新增24个独立物理样本 |
| 边界与失败 | vision/dualview/reports/boundary_checks.json | 51项受控检查修复后满足各自预期；另24对错配中22对仍给候选 | 自动实例配对或未知形状可靠拒识 |
| 人工审计回调 | vision/dualview/reports/gui_callback_check.json | 实际模型的隐藏窗口Tk状态/记录/更正检查 | 整窗人工视觉验收、独立实物实验 |
| v3解压复现 | vision/dualview/reports/package_validation_v3.json | 工作区外解压CPU八对旧样例正确；29固定文件校验、篡改检测 | 新电脑依赖重装、免安装EXE、独立样本准确率 |
| 数据契约 | vision/dualview/reports/data_contract_checks.json；dataset_contract.py | 形式上防实物/批次/父图/路径跨区，test不参与训练提特征 | 元数据真实性、当前已获新实拍 |
| 赛项约束 | docs/rules-interface-audit.md | 对已收到两份原PDF的具体页码核对 | 未提供的校赛完整更新已核实 |

原视频、832张真实帧、绿底和增强图均本地保留。5131张训练/验证图包含派生增强，不能称5131张独立实拍。377对按类别组合，非同步采集，不是跨视图实例对应真值。

## 本地交付物

本机根目录为 `C:/27工创`：

- `output/校赛提交材料/智能分拣_项目书面方案.pdf`：11页，包含进度计划、具体方案、佐证。最新逐页渲染查看已完成；身份资料未编造，最终文件命名待补。
- `output/校赛提交材料/双视图识别演示包_v3_20261017.zip`：现有推荐视觉包；不含显示模块。旧v1/v2保留但不再推荐。
- `output/校赛提交材料/演示验证_v3/`：对应包的实际验证日志。
- 最终汇总包另含版本化源码快照、证据文件、运行说明与SHA256清单。它是归档交付，不代表增加了新实验。

v3 ZIP SHA256：`79bcc91baf0ea472fc26de6e4ad261ba694ebe9aaf6627c2f88ef7a7d7034fea`。

模型SHA256：`93915e90123e791027ac3b5b29140eb5c364900e217de7bce0793e5d4e157e4e`，约3.9 MB，当前权重未改。v3包的7个模块文件与冻结源码按内容摘要核对，版本号不同不意味着模型改变。

## 使用与后续验收

1. 提交主体为本地PDF；身份证明仅待最终文件命名，不把演示包当正式匿名任务命题模板。原通知允许至多20个文件，现有交付无需拆成大量小文件；最终上传由用户操作。
2. 解压演示包后按包内说明在兼容Python3.10环境运行verify_files.py、demo.py或evaluate.py。包内不含解释器及完整依赖；全新环境安装未验收，只加载可信权重。
3. 后续真实采集使用training/capture_pairs.example.csv字段模板，独立实物和批次分区；模板无真实图像，不可直接当训练集。用真实已填写清单运行training/train_dualview.py，封存test，再独立评估。
4. 当前仅红蓝、四种宽形状，模型分数未校准；多目标定位、跨视图实例对应、附加信息、机械标定、入盒反馈及显示完成ACK待验收。automatic_sorting_allowed保持false。
5. 无新增独立实拍时不重跑无变化内部准确率、不制造虚拟实物ID、不无目的追加版本。用户补充新数据后再开相应实测工作包。
