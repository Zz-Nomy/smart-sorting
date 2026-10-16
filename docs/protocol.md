# 串口协议草案

尚未与 ESP32 程序约定，不代表现有接口。建议 UTF-8 JSON Lines，每行一条消息，以换行作为边界。接收方需限制单行长度并拒绝格式错误消息。

任务示例：

```json
{"type":"ITEM","item_id":"session-001","category":"example-shape_example-color","box":1,"mapping_version":1}
```

反馈示例：

```json
{"type":"ACK","item_id":"session-001"}
{"type":"POSITION-DONE","item_id":"session-001"}
{"type":"DISPLAY-DONE","item_id":"session-001"}
{"type":"ITEM-DONE","item_id":"session-001"}
```

ITEM-ID 在首次采集前生成，同件重拍、重发沿用同 ID。ACK 只代表接收，DISPLAY-DONE 只代表显示完成；必须在所需物理动作完成后才允许前进。

控制端需记忆当前和近期完成任务，重复 ID 查询或返回已有状态，不重复动作。重启后不得盲目重发动作，先确认物料和设备状态。超时、未知盒号、执行故障应阻止后续动作；恢复方式须符合赛场规则，不默认允许参赛队员人工干预。

## 已实现显示事件与草案的区别

`display/display_app.py` 接收的是 `event: DISPLAY_COMMIT`，并非上述 `type` 消息；当前没有已联调适配器。详见 `display/README.md`。`drop_ok=true` 是控制器对入盒的声明，显示端不能验证传感器或正确分类。

显示端按唯一字符串 `item_id` 去重，一条合格事件只加一；提供 `count` 时必须恰好等于当前数量加一，否则拒绝。未知目录键、缺失显示资料或非法盒号也拒绝。其进程内状态未持久化，重启恢复未实现。

计划的控制顺序：建立任务 → 配对及类别/盒号确认 → 单件机构动作 → 完全入盒证据 → DISPLAY_COMMIT → 图像解码、绘制刷新后 DISPLAY-DONE → 后续任务。当前显示端没有发送刷新完成反馈，因此还不能验收此闭环。既有视觉模型始终返回 `automatic_sorting_allowed=false`，不能直接作为 ITEM 命令发送。
