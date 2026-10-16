# 训练模块

训练入口：`python training/train_dualview.py --data DATASET --output vision/dualview`。

数据格式、环境安装、模型结构和评估限制见 [双视图原型说明](../vision/dualview/README.md)。本机已训练出权重，按仓库约定不提交权重或原始图像。图片对评估 CSV 格式见 [pairs.example.csv](pairs.example.csv)，成功必须颜色与形状同时正确，需复核/异常计为未成功。
