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
        choices=["table", "markdown"],
        help="输出格式 (默认: table)",
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
        print(generate_report(period=args.period, fmt=args.fmt))

    elif args.command == "analyze":
        from workpulse.ai_analyzer import format_analysis
        print(format_analysis(period=args.period, fmt=args.fmt))

    elif args.command == "prune":
        from workpulse.tracker import prune_data
        prune_data(args.before)


if __name__ == "__main__":
    main()
