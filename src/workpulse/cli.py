"""WorkPulse CLI 入口"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="workpulse",
        description="WorkPulse - 个人工作效率助手",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # start
    subparsers.add_parser("start", help="启动后台追踪")

    # stop
    subparsers.add_parser("stop", help="停止后台追踪")

    # status
    subparsers.add_parser("status", help="查看运行状态")

    # report
    report_parser = subparsers.add_parser("report", help="生成报告")
    report_parser.add_argument(
        "period",
        nargs="?",
        default="today",
        choices=["today", "yesterday", "week"],
        help="报告时间范围 (默认: today)",
    )
    report_parser.add_argument(
        "--format",
        dest="fmt",
        default="table",
        choices=["table", "markdown", "html"],
        help="输出格式 (默认: table)",
    )
    report_parser.add_argument(
        "--with-analysis",
        action="store_true",
        help="在报告中附带启发式分析摘要",
    )
    report_parser.add_argument(
        "--output",
        help="将输出写入指定文件路径",
    )

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="生成工作模式分析")
    analyze_parser.add_argument(
        "period",
        nargs="?",
        default="today",
        choices=["today", "yesterday", "week"],
        help="分析时间范围 (默认: today)",
    )
    analyze_parser.add_argument(
        "--format",
        dest="fmt",
        default="markdown",
        choices=["markdown", "json"],
        help="输出格式 (默认: markdown)",
    )

    # prune
    prune_parser = subparsers.add_parser("prune", help="清理旧数据")
    prune_parser.add_argument(
        "--before",
        required=True,
        help="删除此日期之前的数据 (格式: 2026-01-01)",
    )

    # autostart
    autostart_parser = subparsers.add_parser("autostart", help="管理开机自启动")
    autostart_parser.add_argument(
        "action",
        choices=["enable", "disable", "status"],
        help="自启动操作",
    )

    # config
    config_parser = subparsers.add_parser("config", help="查看当前配置")
    config_parser.add_argument(
        "action",
        choices=["show"],
        help="配置操作",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "start":
        from workpulse.tracker import start_daemon
        start_daemon()

    elif args.command == "stop":
        from workpulse.tracker import stop_daemon
        stop_daemon()

    elif args.command == "status":
        from workpulse.tracker import show_status
        show_status()

    elif args.command == "report":
        from workpulse.reporter import generate_report
        output = generate_report(
            period=args.period,
            fmt=args.fmt,
            include_analysis=args.with_analysis,
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
        else:
            print(output)

    elif args.command == "analyze":
        from workpulse.ai_analyzer import format_analysis
        print(format_analysis(period=args.period, fmt=args.fmt))

    elif args.command == "prune":
        from workpulse.tracker import prune_data
        prune_data(args.before)

    elif args.command == "autostart":
        from workpulse.autostart import disable_autostart, enable_autostart, show_autostart_status

        if args.action == "enable":
            enable_autostart()
        elif args.action == "disable":
            disable_autostart()
        else:
            show_autostart_status()

    elif args.command == "config":
        from workpulse.settings import SETTINGS_PATH, load_settings

        settings = load_settings()
        print(f"settings_path: {SETTINGS_PATH}")
        print(f"poll_interval_seconds: {settings.poll_interval_seconds}")
        print(f"archive_retention_days: {settings.archive_retention_days}")


if __name__ == "__main__":
    main()
