# WorkPulse

个人工作效率助手。WorkPulse 会定时记录当前前台应用、窗口标题和空闲状态，并按分类生成本地日报/周报。

## 功能

- 每 30 秒采样一次当前前台应用和窗口标题
- 记录用户空闲状态并区分活跃时间 / 空闲时间
- 基于 YAML 规则将活动分类为编码、文档、沟通、设计、浏览、娱乐等
- 使用本地 SQLite 存储数据
- 支持生成表格或 Markdown 格式报告
- 支持清理历史数据

## 适用平台

- macOS
- Windows

## 安装

基础依赖：

```bash
pip install .
```

macOS:

```bash
pip install ".[macos]"
```

Windows:

```bash
pip install ".[windows]"
```

## 权限说明

在 macOS 上，首次使用通常需要为终端或 Python 进程授予以下权限：

- `辅助功能`
- `屏幕录制`

否则可能无法读取前台窗口标题或获取准确的活动信息。

## 使用方式

查看帮助：

```bash
workpulse --help
```

启动后台追踪：

```bash
workpulse start
```

查看状态：

```bash
workpulse status
```

生成报告：

```bash
workpulse report
workpulse report yesterday
workpulse report week --format markdown
```

停止追踪：

```bash
workpulse stop
```

清理旧数据：

```bash
workpulse prune --before 2026-01-01
```

## 数据位置

WorkPulse 默认把数据存放在用户目录下：

- 数据库：`~/.workpulse/activity.db`
- 规则文件：`~/.workpulse/rules.yaml`
- 日志文件：`~/.workpulse/workpulse.log`
- PID 文件：`~/.workpulse/workpulse.pid`

## 分类规则

首次运行时会自动生成 `~/.workpulse/rules.yaml`。你可以自行编辑规则，例如：

```yaml
idle_threshold_minutes: 5
default_category: "其他"
rules:
  - app_contains: "Code"
    category: "编码"
  - app_contains: "WeChat"
    category: "沟通"
  - title_contains: "YouTube"
    category: "娱乐"
```

规则按顺序匹配，命中后立即返回对应分类。

## 报告说明

当前支持的时间范围：

- `today`
- `yesterday`
- `week`

报告内容包括：

- 活跃时间与空闲时间
- 分类统计
- 应用统计
- 活动详情 Top 10

## 开发

运行测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

本地直接运行：

```bash
PYTHONPATH=src python3 -m workpulse --help
```

## 当前限制

- 这是一个本地优先的轻量工具，暂不包含云同步
- 分类准确度依赖用户规则配置
- 浏览器类应用可能覆盖多种活动场景，报告会尽量标记为多分类
- `ai_analyzer` 仍是预留模块，尚未接入实际模型分析

## License

MIT
