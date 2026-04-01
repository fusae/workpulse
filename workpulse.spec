# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("workpulse")

a = Analysis(
    ["src/workpulse/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "workpulse.ai_analyzer",
        "workpulse.autostart",
        "workpulse.briefing",
        "workpulse.classifier",
        "workpulse.cli",
        "workpulse.daily_report",
        "workpulse.doctor",
        "workpulse.exporter",
        "workpulse.llm_client",
        "workpulse.reporter",
        "workpulse.settings",
        "workpulse.tracker",
        "workpulse.platform.base",
        "workpulse.platform.macos",
        "workpulse.platform.windows",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="workpulse",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)
