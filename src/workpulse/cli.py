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
    report_parser.add_argument("--from-date", dest="from_date", help="起始日期 (YYYY-MM-DD)")
    report_parser.add_argument("--to-date", dest="to_date", help="结束日期 (YYYY-MM-DD)")

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
    analyze_parser.add_argument(
        "--provider",
        dest="provider",
        default=None,
        choices=["heuristic", "llm", "auto"],
        help="分析提供方 (默认: 使用配置)",
    )
    analyze_parser.add_argument("--from-date", dest="from_date", help="起始日期 (YYYY-MM-DD)")
    analyze_parser.add_argument("--to-date", dest="to_date", help="结束日期 (YYYY-MM-DD)")

    # brief
    brief_parser = subparsers.add_parser("brief", help="生成日报摘要")
    brief_parser.add_argument(
        "period",
        nargs="?",
        default="today",
        choices=["today", "yesterday", "week"],
        help="摘要时间范围 (默认: today)",
    )
    brief_parser.add_argument(
        "--format",
        dest="fmt",
        default="markdown",
        choices=["markdown", "json"],
        help="输出格式 (默认: markdown)",
    )
    brief_parser.add_argument(
        "--provider",
        dest="provider",
        default=None,
        choices=["heuristic", "llm", "auto"],
        help="摘要提供方 (默认: 使用配置)",
    )
    brief_parser.add_argument("--from-date", dest="from_date", help="起始日期 (YYYY-MM-DD)")
    brief_parser.add_argument("--to-date", dest="to_date", help="结束日期 (YYYY-MM-DD)")

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

    # doctor
    doctor_parser = subparsers.add_parser("doctor", help="检查运行环境")
    doctor_parser.add_argument(
        "--format",
        dest="fmt",
        default="markdown",
        choices=["markdown", "json"],
        help="输出格式 (默认: markdown)",
    )

    # export
    export_parser = subparsers.add_parser("export", help="导出活动明细")
    export_parser.add_argument(
        "--format",
        dest="fmt",
        default="csv",
        choices=["csv", "json"],
        help="导出格式 (默认: csv)",
    )
    export_parser.add_argument(
        "--source",
        dest="source",
        default="active",
        choices=["active", "archive", "all"],
        help="导出来源 (默认: active)",
    )
    export_parser.add_argument(
        "period",
        nargs="?",
        default="today",
        choices=["today", "yesterday", "week"],
        help="导出时间范围 (默认: today)",
    )
    export_parser.add_argument("--from-date", dest="from_date", help="起始日期 (YYYY-MM-DD)")
    export_parser.add_argument("--to-date", dest="to_date", help="结束日期 (YYYY-MM-DD)")
    export_parser.add_argument("--output", help="将导出写入指定文件路径")

    # daily-report
    daily_parser = subparsers.add_parser("daily-report", help="生成结构化日报")
    daily_parser.add_argument(
        "period",
        nargs="?",
        default="today",
        choices=["today", "yesterday", "week"],
        help="日报时间范围 (默认: today)",
    )
    daily_parser.add_argument(
        "--format",
        dest="fmt",
        default="markdown",
        choices=["markdown", "json"],
        help="输出格式 (默认: markdown)",
    )
    daily_parser.add_argument(
        "--provider",
        dest="provider",
        default=None,
        choices=["heuristic", "llm", "auto"],
        help="日报提供方 (默认: 使用配置)",
    )
    daily_parser.add_argument("--from-date", dest="from_date", help="起始日期 (YYYY-MM-DD)")
    daily_parser.add_argument("--to-date", dest="to_date", help="结束日期 (YYYY-MM-DD)")
    daily_parser.add_argument("--output", help="将日报写入指定文件路径")

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
            start_date=args.from_date,
            end_date=args.to_date,
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
        else:
            print(output)

    elif args.command == "analyze":
        from workpulse.ai_analyzer import format_analysis
        print(
            format_analysis(
                period=args.period,
                fmt=args.fmt,
                start_date=args.from_date,
                end_date=args.to_date,
                provider=args.provider,
            )
        )

    elif args.command == "brief":
        from workpulse.briefing import generate_brief
        print(
            generate_brief(
                period=args.period,
                fmt=args.fmt,
                start_date=args.from_date,
                end_date=args.to_date,
                provider=args.provider,
            )
        )

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
        print(f"analysis_provider: {settings.analysis_provider}")
        print(f"llm_endpoint: {settings.llm_endpoint}")
        print(f"llm_model: {settings.llm_model}")
        print(f"llm_api_key_env: {settings.llm_api_key_env}")

    elif args.command == "doctor":
        from workpulse.doctor import run_doctor

        print(run_doctor(fmt=args.fmt))

    elif args.command == "export":
        from workpulse.exporter import export_activities

        output = export_activities(
            fmt=args.fmt,
            source=args.source,
            period=args.period,
            start_date=args.from_date,
            end_date=args.to_date,
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8", newline="") as f:
                f.write(output)
        else:
            print(output, end="" if output.endswith("\n") else "\n")

    elif args.command == "daily-report":
        from workpulse.daily_report import generate_daily_report

        output = generate_daily_report(
            period=args.period,
            fmt=args.fmt,
            start_date=args.from_date,
            end_date=args.to_date,
            provider=args.provider,
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
        else:
            print(output)


if __name__ == "__main__":
    main()
