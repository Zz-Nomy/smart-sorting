# 智能分拣屏幕端

这套页面按 800×480 设计，适配 Raspberry Pi + Waveshare 4.3 英寸 DSI 屏。页面固定显示当前物料图片、名称、分类、目标料盒、物料编号、累计成功数量和运行状态。屏幕不需要触摸，现场运行时由控制器通过串口发送 JSON。

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

每行一个 UTF-8 JSON，换行符结束。只有 `drop_ok` 为 `true` 的消息会计入成功数：

```json
{"event":"DISPLAY_COMMIT","item_id":"202610140001","key":"red_cylinder","name":"红色圆柱","category":"按颜色：红色","box_id":1,"image":"assets/red_cylinder.png","count":8,"drop_ok":true}
```

`item_id` 是一次分拣的唯一编号。串口重发同一编号时，页面会显示“重复消息，未重复计数”，不会重复累加。建议控制器在“料门动作完成且入盒传感器确认”后再发送这条消息。

## 替换货物图片

把实际拍摄的图片放入 `assets/`，建议 4:3 或 1:1 比例，文件名与 `items.json` 中的 `image` 一致；PNG/JPG 都可以。仓库里的 PPM 是演示用色块，替换成实际货物照片即可。没有图片时页面会显示占位框，不影响数据接收。

## 自检

不打开窗口即可验证 JSON 协议、成功计数和去重逻辑：

```bash
python3 display_app.py --self-test
```
