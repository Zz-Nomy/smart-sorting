# 双视图颜色＋形状分类原型

下一阶段的数据采集、独立验证、多目标配对和验收标准见[严谨实施方案](../../docs/rigorous-vision-plan.md)。该方案中的目标指标尚未实现或验收，不改变本页原型的能力边界。

输入同一物体的顶视、侧视照片各一张，输出例如“红色圆锥”。颜色与形状都一致才视为同一类。当前支持红/蓝 × 立方体、圆柱、圆锥、多棱柱，共八类。多棱柱未细分棱数。

## 已完成

- 官方预训练 MobileNetV3-small 冻结主干，两视图灰度目标特征拼接，训练四类形状分类头；HSV 单独判断颜色。权重约 3.9 MB。
- 目标按颜色定位，不要求居中；检测到两个显著目标时提示先裁出同一物体。多目标检测与跨视图身份匹配待实现。
- 演示界面显示中文名称、模型分数、需复核原因。人工选择真值后记录成功/失败及本次累计成功率。颜色/形状任一错误、需复核或报错均计为未成功。
- CSV 评估输出八类混淆记录、成功率、复核/错误率和耗时；拒绝重复图片对计数。没有真值时不能计算实际成功率。

## 安装、训练、推理

建议 Python 3.10，在独立环境安装 `pip install -r vision/dualview/requirements.txt`。本机使用工作区 work/vision_runtime 中隔离的 NumPy 1.26.4，不改变全局依赖；其他机器没有该目录时使用正常安装环境。

从仓库根目录运行：

```powershell
python training/train_dualview.py --pairs CAPTURE_PAIRS.csv --shapes training/shapes.example.json --output runs/paired_run --cache CACHE_DIR
python training/train_dualview.py --data DATASET --legacy-temporal --output runs/legacy_check --cache CACHE_DIR
python vision/dualview/demo.py
python vision/dualview/vision_model.py --top TOP.jpg --side SIDE.jpg --checkpoint vision/dualview/model.pt --json result.json
python vision/dualview/evaluate.py --csv YOUR_PAIRS.csv --checkpoint vision/dualview/model.pt --output evaluation.json
python -m unittest discover -s tests -p test_dualview.py -v
```

DATASET 在本机是 `C:/27工创/output/视觉识别素材库_v1`；CACHE_DIR 可用 `C:/27工创/work/torch_cache`。正式采集 CSV 字段见 `training/capture_pairs.example.csv`，两类形状示例配置见 `training/shapes.example.json`；使用八类现有物料时可省略 `--shapes`，默认四种形状。示例清单是字段模板，不是可用照片数据。推理使用新模型需传 `--checkpoint runs/paired_run/model.pt`。启动演示.cmd 默认使用模块旁的本地模型。首次训练下载官方预训练权重。权重和原图按仓库约定不提交 Git；只加载可信来源文件。

旧素材路径需包含 originals_manifest.jsonl、source_videos.json 及对应 originals 图片，且必须显式使用 `--legacy-temporal`，输出强制标为相关内部检查。正式采集使用 `--pairs`：清单须含 pair_id、physical_object_id、session_id、split、top、side、color、shape、source_kind、top_parent_id、side_parent_id。物理实物、批次、原图父 ID 和图片路径分别检查跨区，不只检查实物与批次的组合；缺图、标签冲突、重复图对会报错，验证/测试只接受 source_kind=real。元数据检查不能证明 ID 填写真实或实物确实独立。

训练只提取 train/val 图像特征，不读取封存 test 图片；test 仅做清单完整性与分区检查，最终评估另执行。`--shapes` 可配置有样本的新形状，顺序保存到权重，推理从权重读取并校验头维度；不自动获得未知形状能力，颜色定位仍只支持红蓝。输出模型已存在时默认拒绝覆盖，需换目录或显式 `--overwrite`。训练记录种子、清单摘要、源码摘要、Git 提交与脏状态、模型摘要。评估 CSV 示例仍见 training/pairs.example.csv，颜色与形状真值均必需。

## 当前评估的边界

832 张真实帧中，495 张用于训练；每视频前 60% 训练，中间 15% 留空，末 25% 共 214 张帧用于内部时间留出检查。双视图来自按类别组合的不同视频，不是同步拍摄。1600 个训练组合、400 个验证组合，验证去重后 377 对；组合数不等于独立实物数。

377 对的内部端到端颜色＋形状成功率为 100%。但训练/验证来自相同视频、实物、背景，高度相关，不能表述为独立测试准确率或现场成功率。独立实物测试尚未完成；须按实物 ID、采集批次隔离新数据。见 reports/internal_evaluation.json。不要将这里的组合重新命名为测试集。

## 使用边界

当前仅八类，不保证识别未知形状、其他颜色、材质与尺寸。40 mm 是用户给定约束，程序未测量或验证尺寸。定位依赖颜色分离；同色背景、遮挡、强反光可能失败。轻微透视仅做初步扰动检查，不保证任意角度。颜色一致不能证明两张图是同一实物。

模型分数是未校准 softmax，不是正确概率。低分、颜色冲突、目标触边会提示复核，但不能保证所有未知物体都被拒识。拒识仅用于视觉复核，不对应已获比赛许可的机械路线。

## 评估结果的分母与计时

`evaluate.py` 每行表示一个已标注的单目标任务，不验证跨视图实物身份，不计算多目标检测或整场景成功率。缺失图片、解码失败和复核任务保留在总分母中；错误的 CSV 字段或重复图对（包括路径别名、交换视图）会拒绝整次评估，避免静默丢样本。缺图是输入失败，空的真值是评估清单错误，两者区别处理。

- `success_rate`：正确接受数 / 全部任务数；颜色与形状都必须正确。
- `accepted_precision`：正确接受数 / 全部接受输出；没有接受输出时为 `null`，不是 100%。
- `acceptance_coverage`：接受任务数 / 全部任务数。
- 每类单独统计，包含颜色错误、形状错误、复核和输入错误；颜色/形状错误可同时发生，原因计数不一定互斥。
- 真值出现当前模型不支持的颜色或形状时，仍保留任务；未知错误接受率另报。未知被拒绝不等于成功识别其颜色与形状，不计入完整正确数；已知类别成功率另外报告。当前八类内部清单不含未知样本，未知指标为 `null`，不能声称未知拒识能力通过。
- 没有足够独立实物/批次证据时，不输出伪精确的成功率置信区间。可填写 physical_object_id/session_id，报告其数量，但字段本身不证明独立性。

`--scope internal_temporal` 标记旧视频检查，`--scope derived_stress` 标记派生扰动，默认 `external_unverified` 也不等于独立测试通过。`--warmup 3` 可显式设置预热次数；报告分列模型加载、首次预热预测和评估段平均/P50/P95。预热不计入样本或成功率；GPU 同步后计时，包含图像读取、预处理和推理，不包含拍照与机械动作。首次预热或加载不能混入稳定时延后仍标成纯推理性能。

后续优先补拍成对真实图，变化实物、位置、光照、视距及角度；保留物料 ID、批次、目标框和跨视图对应关系。合成素材可补充训练，独立实拍数据负责验证稳定性。

模型来源：[PyTorch MobileNetV3-small](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html)。

## 本地交付包验证

`training/package_dualview.py` 可将当前源码、已有可信权重与成对样例打成本地 ZIP，保留摘要校验和运行说明。它不把原图或模型加入 Git，不含 Python 解释器或全套依赖。已有包不会覆盖，须指定新文件名。

已从工作区以外临时目录解压，在现有兼容环境中 CPU 运行八对旧视频样例并检查文件 SHA256，八对均正确，改动文件能被校验器检测。见 `reports/package_validation.json`；测试使用已安装 Python/PyTorch/OpenCV 等及隔离 NumPy 1.26.4，不代表在全新机器上验证过一键安装，也不是独立样件评估或 GUI 交互验收。

## 边界检查与配对失败证据

`training/check_boundaries.py` 在既有样例上生成可追溯派生检查，不能当作新实拍测试。空场、黄色重着色、触边、明显多目标、局部遮挡、缺视图及颜色冲突等51项受控检查中，最初7项失败均为同图重复输入；增加按解码像素检查后51项满足各自预期（拒绝或正确，不是51次全部成功识别）。原图不修改。

另将同色不同形状的顶/侧视故意错配，24对中22对仍给出候选。这一问题未解决，不能宣称自动实例对应。`candidate`只表示在输入对应正确这一前提下的分类候选；结果明确返回 `pairing_status=provided_pair_identity_unverified`、`automatic_sorting_allowed=false` 及警告，不能直接发机械指令。重复图像拦截只能排除完全相同像素，不能识别同色不同实物或重复物体。见 reports/boundary_checks.json。

## 人工核验审计

界面使用 manual_session.py 管理状态：工作期间禁用换图与记录，后台线程只向队列发消息，主线程应用当前任务结果；过期回调丢弃。输入文件在识别期间或识别后改变时，旧结果不再当作当前图片的正确标签。

人工核验以文件内容摘要组成无序图片对键，重复重跑、改名副本和交换视图不会增加分母。该去重不等于近重复或物理实物独立性检查。人工真值需明确确认，显式更正只修改当前唯一图片对的统计值，并在 manual_evaluation.jsonl 追加审计事件，保留旧值。读写失败不能伪称记录成功。每条事件附模型权重摘要，不同权重的统计不混合；旧CSV保留但不自动导入。界面显示当前权重累计唯一图片对，不称独立实物成功率。

已通过隐藏窗口的程序化 Tk 回调检查（真实模型、现有样例、工作状态、重复记录、更正），未宣称整窗人工视觉验收。证据见 reports/gui_callback_check.json。
