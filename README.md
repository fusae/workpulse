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

Windows 推荐使用 Python 3.10 或 3.11，并优先在 PowerShell 中安装：

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install ".[windows]"
```

如果要给没有 Python 环境的 Windows 用户分发，可使用 PyInstaller 构建：

```powershell
.\scripts\build_windows.ps1 -Clean
```

构建后会得到：

- `dist\workpulse.exe`
- `dist\artifacts\workpulse-windows-amd64.zip`
- `dist\artifacts\workpulse-windows-amd64.sha256`

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
workpulse report week --format html --with-analysis --output report.html
workpulse report --from-date 2026-03-01 --to-date 2026-03-07
```

生成工作分析：

```bash
workpulse analyze
workpulse analyze week --format json
workpulse analyze --from-date 2026-03-01 --to-date 2026-03-07
workpulse analyze --provider llm
```

生成日报摘要：

```bash
workpulse brief
workpulse brief week --format json
workpulse brief --from-date 2026-03-01 --to-date 2026-03-07
workpulse brief --provider llm
```

停止追踪：

```bash
workpulse stop
```

管理开机自启动：

```bash
workpulse autostart status
workpulse autostart enable
workpulse autostart disable
```

查看当前配置：

```bash
workpulse config show
```

检查运行环境：

```bash
workpulse doctor
workpulse doctor --format json
```

导出活动明细：

```bash
workpulse export --format csv --source active --output activities.csv
workpulse export --format json --source all --from-date 2026-03-01 --to-date 2026-03-07
```

生成结构化日报：

```bash
workpulse daily-report
workpulse daily-report --provider llm
workpulse daily-report --from-date 2026-03-01 --to-date 2026-03-07 --output daily-report.md
```

清理旧数据：

```bash
workpulse prune --before 2026-01-01
```

## Windows 使用建议

首次在 Windows 上使用时，建议先确认以下几点：

- 使用普通桌面会话，不要在远程受限环境里测试前台窗口采集
- PowerShell 或终端不要以会频繁被关闭的临时窗口运行
- 某些安全软件可能会拦截窗口访问或后台进程创建
- 如果你使用的是公司设备，可能会受到系统策略限制

建议先手动验证一遍主流程：

```powershell
workpulse start
workpulse status
workpulse report
workpulse stop
```

如果 `status` 显示已运行，但没有数据，优先检查：

- 是否确实在桌面前台切换过应用
- 当前 Python 环境里是否安装了 `psutil` 和 `pywin32`
- 杀毒软件或企业安全策略是否拦截了后台采集

检查 Windows 扩展依赖：

```powershell
python -c "import psutil, win32gui, win32process; print('ok')"
```

## 数据位置

WorkPulse 默认把数据存放在用户目录下：

- 数据库：`~/.workpulse/activity.db`
- 规则文件：`~/.workpulse/rules.yaml`
- 配置文件：`~/.workpulse/settings.yaml`
- 日志文件：`~/.workpulse/workpulse.log`
- PID 文件：`~/.workpulse/workpulse.pid`

## LLM 分析

默认使用启发式分析。若要启用外部模型分析，可在环境变量中提供 API key，并将 `settings.yaml` 的 `analysis_provider` 设为 `llm` 或命令行传 `--provider llm`。

默认兼容 OpenAI 风格接口，关键配置：

- `analysis_provider`
- `llm_endpoint`
- `llm_model`
- `llm_api_key_env`
- `llm_timeout_seconds`

例如：

```bash
export OPENAI_API_KEY=your_key
workpulse analyze --provider llm
```

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

设计文档：

- [docs/design.md](/Users/jamesyu/Projects/workpulse/docs/design.md)
- [docs/windows-release.md](/Users/jamesyu/Projects/workpulse/docs/windows-release.md)

## 当前限制

- 这是一个本地优先的轻量工具，暂不包含云同步
- 分类准确度依赖用户规则配置
- 浏览器类应用可能覆盖多种活动场景，报告会尽量标记为多分类
- 当前分析模块是启发式分析，还没有接入真实 LLM
- 当前提供的是打包工作流和构建脚本，不是完整安装器

## License

MIT
