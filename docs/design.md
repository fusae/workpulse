# WorkPulse Design

## Overview

WorkPulse 是一个本地优先的个人工作效率助手。它通过定时采样当前前台应用、窗口标题和空闲状态，生成可复盘的时间分配数据，并输出日报或周报。

当前项目定位是一个轻量 CLI 工具，优先解决这些问题：

- 一天结束后不知道时间花在哪里
- 很难按项目或工作类型复盘时间分配
- 手动记录日报成本高
- 想为后续 AI 分析和自动日报生成保留数据基础

## Product Goals

- 零操作基础追踪：启动后自动后台记录，不要求用户手动切换计时器
- 本地优先：活动数据默认只保存在本地
- Windows 优先：Windows 是主战场，macOS 保持兼容
- 低资源占用：采用简单轮询，不引入常驻重型组件
- 可扩展：为后续 AI 分析、自动日报、打包分发预留空间

## Scope

### MVP

- 每 30 秒采样一次前台应用和窗口标题
- 检测空闲状态
- 将活动数据保存到本地 SQLite
- 基于 YAML 规则自动分类
- 生成 `today` / `yesterday` / `week` 报告
- 生成启发式工作分析
- 提供 `start` / `stop` / `status` / `report` / `prune` CLI
- 提供开机自启动管理

### Out of Scope

- 云同步
- 多人协作后台
- 浏览器扩展或编辑器扩展
- 自动日报生成
- 高质量 LLM 驱动的优化建议

## Architecture

系统分成四层：

1. CLI 层
   - 负责参数解析和命令分发
2. Tracker 层
   - 定时采样、空闲判断、SQLite 写入、守护进程管理
3. Classifier / Reporter 层
   - 将活动分类并生成聚合报告
4. Platform 层
   - 封装 Windows / macOS 获取前台窗口和 idle 时间的系统差异

```text
CLI
  -> Tracker
     -> Platform
     -> SQLite
     -> Classifier
  -> Reporter
     -> SQLite
```

## Key Design Decisions

### 1. Polling over event-driven hooks

当前采用 30 秒轮询，而不是系统事件驱动方案。

原因：

- 复杂度低，易于跨平台实现
- 对日报/周报级别的统计足够
- 便于调试和维护

代价：

- 快速切换窗口的行为会丢失
- 精度上限受采样频率限制

### 2. Local SQLite storage

活动数据保存在 `~/.workpulse/activity.db`。

原因：

- 不依赖服务端
- 查询和聚合成本低
- 易于备份、迁移和调试

### 3. Rule-based classification first

分类引擎基于应用名和窗口标题的字符串匹配，不在 MVP 中引入模型推断。

原因：

- 可解释、可调整
- 没有外部依赖
- 对多数办公 / 编码 / 浏览器场景足够

### 4. Windows-first process management

Windows 是主要目标平台，因此守护进程和进程状态检查优先按 Windows 行为设计。

当前实现中：

- Windows 通过 `subprocess.Popen` 启动后台进程
- Windows 通过 `psutil` 检查 PID 是否存在并终止进程
- macOS / Unix 使用 `fork + setsid`

## Data Flow

一次采样流程如下：

1. 获取当前前台窗口
2. 获取用户空闲时长
3. 判断是否超过空闲阈值
4. 根据应用名和窗口标题进行分类
5. 生成一条 UTC 时间戳记录
6. 写入 SQLite

生成报告时：

1. 根据本地时区计算 `today` / `yesterday` / `week` 的时间范围
2. 转换为 UTC 区间查询 SQLite
3. 聚合分类、应用和窗口标题
4. 输出表格或 Markdown

## Data Model

当前核心表：

```sql
CREATE TABLE activities (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    app_name TEXT NOT NULL,
    window_title TEXT,
    category TEXT,
    is_idle BOOLEAN DEFAULT FALSE,
    platform TEXT NOT NULL
);
```

字段说明：

- `timestamp`: UTC ISO 8601 时间
- `app_name`: 应用名
- `window_title`: 窗口标题
- `category`: 分类结果
- `is_idle`: 是否为空闲样本
- `platform`: `windows` 或 `macos`

当前只建立了 `timestamp` 索引，优先服务于时间区间报告查询。

## Configuration

用户配置位于 `~/.workpulse/rules.yaml`，首次运行时从包内默认规则生成。

关键配置项：

- `idle_threshold_minutes`
- `default_category`
- `rules`

规则按顺序匹配，先命中先返回。

## Platform Strategy

### Windows

平台实现位于 [src/workpulse/platform/windows.py](/Users/jamesyu/Projects/workpulse/src/workpulse/platform/windows.py)。

能力：

- `win32gui` / `win32process` 获取前台窗口和进程
- `psutil` 获取进程名
- `ctypes` 调用 `GetLastInputInfo` 获取 idle 时间

Windows 是当前主战场，安装路径和进程管理优先围绕它设计。

### macOS

平台实现位于 [src/workpulse/platform/macos.py](/Users/jamesyu/Projects/workpulse/src/workpulse/platform/macos.py)。

能力：

- `NSWorkspace` 获取前台应用
- `Quartz` 读取窗口标题
- `Quartz` 获取 idle 时间

注意：

- macOS 需要额外的系统权限支持
- 标题读取依赖系统可见窗口信息

## Error Handling

设计原则：

- 尽量不中断追踪主循环
- 失败优先写日志
- 能缓存的写入失败先缓存，再重试

当前策略：

- 平台读取失败时返回 `None` 或 `0.0`
- SQLite 写入失败时写入内存缓冲区
- 平台层首次错误会记 warning，避免刷屏

## Reporting Semantics

报告包含：

- 活跃时间
- 空闲时间
- 分类统计
- 应用统计
- 活动详情 Top 10

注意点：

- 报告时间范围按用户本地时区定义，再转换到 UTC 查询
- 应用如果跨多个分类，报告里会标记为 `多种(主分类)`
- 当前时间计算仍然基于样本数乘以 `POLL_INTERVAL`

## Current Gaps

与早期设计稿相比，当前还没有实现：

- 基于外部模型的 AI 分析
- 自动日报生成
- 完整的 Windows / macOS 安装器分发

## Roadmap

### Phase 1

- 完善 Windows 端到端验证
- 增加更多测试覆盖
- 优化安装和发布说明

### Phase 2

- 将启发式分析升级为可选 LLM 分析
- 生成自然语言日报
- 提供更面向最终用户的发布包和安装器

### Phase 3

- 支持更细粒度的项目识别
- 评估事件驱动采集方案
- 评估图形化报告界面
