# Daimiao PNG VTuber

`daimiao_png_vtuber` 是一个独立的 PNG VTuber 前端小程序，用于在 Windows PC 上显示呆喵 PNG 角色，并被抖音直播助手通过“窗口采集 + 绿幕抠图”捕捉。

它不接入原 `AI_assistant` 项目，不做 TTS、Gemini、语音识别、Live2D、OBS 或透明窗口。

## 功能

- 固定 800x600 pygame 窗口
- 纯绿色背景 `#00FF00`
- 默认显示 `assets/neutral_closed.png`
- 收到 `speak` WebSocket 事件后切换 `closed/open` 两张图模拟张嘴
- 根据 `mood` 字段切换不同情绪图组
- 同一情绪的 `open` 图会自动对齐 `closed` 图的角色边界，避免说话时视觉缩放
- 说话时显示白底黑边对话气泡，最多 2 行
- 待机时有轻微上下浮动
- 新 `speak` 消息会覆盖当前说话内容，不排队

## macOS 开发运行

建议使用 Python 3.12：

```bash
cd daimiao_png_vtuber
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

也可以显式指定监听地址和端口：

```bash
python main.py --host 0.0.0.0 --port 8765
```

另开一个终端发送测试消息：

```bash
cd daimiao_png_vtuber
source .venv/bin/activate
python tools/send_test_message.py
```

看到角色张嘴、字幕出现，并在 `duration` 后回到待机状态，即为正常。

## Windows 运行

把整个 `daimiao_png_vtuber` 文件夹拷贝到 Windows PC。

在 PowerShell 中运行：

```powershell
cd daimiao_png_vtuber
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

如果 PowerShell 阻止激活脚本，可改用：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

如需改端口：

```powershell
.\.venv\Scripts\python.exe main.py --host 0.0.0.0 --port 8765
```

## 替换 / 新增 PNG 图片

每个情绪图组使用一对文件：

- `assets/<mood>_closed.png`：闭嘴/待机图
- `assets/<mood>_open.png`：张嘴图

当前内置情绪图组：

- `neutral`
- `happy`
- `annoyed`
- `surprised`
- `thinking`

程序启动时会自动加载 `assets/*_closed.png` 和对应的 `assets/*_open.png`。如果收到的 `mood` 匹配不到现有图组，会回退到 `neutral`；如果没有 `neutral`，会尝试旧版 `daimiao` 图组。

建议使用透明背景 PNG。若图片是绿底 PNG，程序会在加载时把接近纯绿的背景转为透明，再叠到窗口的纯绿色背景上，方便抖音直播助手统一抠图。

## 抖音直播助手使用方式

1. 在 Windows PC 上运行 `python main.py`。
2. 打开抖音直播助手。
3. 添加“窗口采集”。
4. 选择窗口 `Daimiao PNG VTuber`。
5. 对该窗口开启绿幕抠图 / 色度键。
6. 抠图颜色选择纯绿色 `#00FF00`。
7. 根据实际效果微调相似度、平滑、边缘参数。

## 从 Mac 的 AI_assistant 发送消息到 Windows

注意：`AI_assistant` 已经实现 PNG VTuber WebSocket sender。发送端代码在 `AI_assistant/vtuber_ws_client.py`，并由 `daimiao_master_v9_env_ready.py` 的 `enqueue_text(text)` 调用；不要把 sender 当作 PNG 前端仓库的待办。

PNG VTuber 默认在 Windows PC 上监听：

```text
ws://0.0.0.0:8765
```

Mac 发送时需要使用 Windows PC 的局域网 IP，例如：

```text
ws://192.168.1.23:8765
```

可以先在 Windows 上查看 IP：

```powershell
ipconfig
```

Mac 侧发送 JSON 示例：

```json
{
  "type": "speak",
  "text": "老大，这波居然没猫车，算你有点本事喵。",
  "mood": "嘴硬夸奖",
  "duration": 4.2
}
```

也可以用本项目测试脚本从 Mac 发送到 Windows：

```bash
python tools/send_test_message.py --host 192.168.1.23 --port 8765 --text "老大，醒醒，该开播了喵。" --duration 3.5
```

测试指定情绪图组：

```bash
python tools/send_test_message.py --host 192.168.1.23 --port 8765 --mood happy --text "老大，这波还算有点样子喵。" --duration 3.5
```

推荐先用连接自检脚本确认 TCP 和 WebSocket 都通：

```bash
python tools/check_connection.py --host 192.168.1.23 --port 8765 --text "Mac 到 Windows 测试到了喵。" --duration 4
```

成功输出类似：

```text
[OK] TCP 192.168.1.23:8765: 8.0 ms
[OK] WebSocket ws://192.168.1.23:8765: sent speak message in 20.0 ms
```

## WebSocket 协议

第一版只处理 `type=speak`：

```json
{
  "type": "speak",
  "text": "老大，这波居然没猫车，算你有点本事喵。",
  "mood": "happy",
  "duration": 4.2
}
```

`mood` 可以直接使用图组名，例如 `neutral`、`happy`、`annoyed`、`surprised`、`thinking`。程序也内置了部分中文 mood 映射，例如 `嘴硬夸奖` 会映射到 `happy`，`毒舌` 会映射到 `annoyed`。

无效 JSON 或非法字段只会打印错误，不会导致程序崩溃。

## 常见问题

### 防火墙阻止端口

如果 Mac 无法连接 Windows 的 `8765` 端口，请检查 Windows Defender 防火墙。允许 Python 通过专用网络，或手动放行 TCP 端口 `8765`。

### 找不到图片

确认每个图组都是成对存在，例如：

- `assets/neutral_closed.png`
- `assets/neutral_open.png`

运行命令时请在 `daimiao_png_vtuber` 项目目录内执行 `python main.py`。

### 对话气泡文字太长

对话气泡最多显示 2 行。过长文本会自动缩小字号并截断。建议从 AI_assistant 侧控制单次吐槽长度，让直播画面更干净。

### 绿幕抠图边缘异常

建议 PNG 角色边缘不要自带绿色半透明像素。抖音直播助手中可以微调色度键的相似度、平滑和边缘参数；如果角色边缘被吃掉，降低相似度或减少边缘平滑。

## 检查语法

```bash
python -m py_compile main.py tools/send_test_message.py tools/check_connection.py
```
