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

后续优先补拍成对真实图，变化实物、位置、光照、视距及角度；保留物料 ID、批次、目标框和跨视图对应关系。合成素材可补充训练，独立实拍数据负责验证稳定性。

模型来源：[PyTorch MobileNetV3-small](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html)。
