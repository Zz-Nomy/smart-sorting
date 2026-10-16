# 训练模块

正式采集入口：`python training/train_dualview.py --pairs CAPTURE_PAIRS.csv --output runs/paired_run`。字段模板见 `capture_pairs.example.csv`。形状配置用 `--shapes shapes.example.json`；默认四种形状。

旧素材相关检查必须显式选择：`python training/train_dualview.py --data DATASET --legacy-temporal --output runs/legacy_check`。该结果不是独立测试。正式训练清单的物理实物、批次、原图父 ID、路径不能跨分区，缺图与标签冲突会报错；训练不读取封存 test 图像。

数据格式、环境安装、模型结构和评估限制见 [双视图原型说明](../vision/dualview/README.md)。本机已训练出权重，按仓库约定不提交权重或原始图像。图片对评估 CSV 格式见 [pairs.example.csv](pairs.example.csv)，成功必须颜色与形状同时正确，需复核/异常计为未成功。
