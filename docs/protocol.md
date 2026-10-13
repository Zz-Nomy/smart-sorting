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

控制端需记忆当前和近期完成任务，重复 ID 查询或返回已有状态，不重复动作。重启后不得盲目重发动作，先确认物料和设备状态。超时、未知盒号、执行故障进入暂停与人工恢复流程。
