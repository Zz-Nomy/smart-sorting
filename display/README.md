# 智能分拣屏幕端

这套页面按 800×480 设计，面向 Raspberry Pi + Waveshare 4.3 英寸 DSI 屏。页面显示当前物料图片、名称、颜色＋形状分类、目标料盒、本件序号、累计数量和状态。物料任务 ID 保留在状态数据中，用于去重。硬件适配与现场联调尚未验收；当前为显示端软件。

## 安装与启动

在 Raspberry Pi OS 上执行：

```bash
sudo apt update
sudo apt install -y python3-pygame fonts-noto-cjk
python3 -m pip install pyserial
cd ~/smart-sorting/display
python3 display_app.py --serial /dev/ttyUSB0
```

演示页面（不接控制器）:

```bash
python3 display_app.py --demo
```

Windows 调试时可以安装 `pygame` 和 `pyserial`，将串口参数改为 `COM3`。按 `Esc` 退出窗口；比赛现场可使用 `--fullscreen`。

## 控制器发送格式

每行一个 UTF-8 JSON，换行符结束。只有 `drop_ok` 为布尔 `true` 的消息才可能计数：

```json
{"event":"DISPLAY_COMMIT","item_id":"202610140001","key":"red_cylinder","name":"红色圆柱","category":"红色＋圆柱","box_id":1,"image":"assets/red_cylinder.ppm","count":1,"drop_ok":true}
```

`item_id` 必须是非空字符串；同一任务重发沿用相同 ID，重复消息不会累加。`count` 可省略；若提供，必须为严格整数且等于本进程已接受数量加一，跳号、旧数、布尔值、字符串均拒绝，不能借此恢复历史总数。未知 `key`、空白显示资料、无效盒号（须整数 1..6）和不存在的图片也拒绝；拒绝不消耗 ID，允许修正后重发。

`items.json` 是展示样例目录，盒号是示例映射；黄色三角件并不表示当前视觉模型支持该类别。目录图片仍为色块占位，不能作为实际货物照片佐证。八个已训练类别不能默认固定对应六个盒，须按本轮实际类别建立受规则允许的映射。

这里的计数仅表示收到控制器声称的入盒确认，不是显示程序独立验证的物理成功或正确分类。控制端必须核实完全入盒；动作到位、识别高分均不能替代。图片存在检查不保证可解码、正确货物或真正显示成功。

## 接口和恢复边界

`docs/protocol.md` 的 `type: ITEM` 等为控制链路草案，本程序实际只接收 `event: DISPLAY_COMMIT`。尚无两者间的已联调适配器，也未发送渲染完成 ACK。`commit()` 返回真只证明状态接受，不能当作显示刷新完成；控制端不得据此认为符合“本次信息显示后才能分拣下一件”。需在真正渲染并完成显示确认后再推进后续任务，协议与硬件验收均待完成。

计数和去重集合只保存在内存。重启后默认零，不会恢复任务，不具备断电幂等性；不可在同一轮物理运行中直接重启并继续动作。后续须增加持久化及控制端状态对账流程，再做丢 ACK、重传、重启与传感器故障测试。软件拒绝/复核不授权赛场人工干预。

## 替换货物图片

把实际拍摄的图片放入 `assets/`，建议 4:3 或 1:1 比例，文件名与 `items.json` 中的 `image` 一致；PNG/JPG 都可以。仓库里的 PPM 是演示用色块，替换成实际货物照片即可。没有图片时页面会显示占位框，不影响数据接收。

## 自检

不打开窗口即可验证 JSON 协议、成功计数和去重逻辑：

```bash
python3 display_app.py --self-test
```
