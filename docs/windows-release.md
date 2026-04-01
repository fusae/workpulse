# Windows Packaging

## Goal

为 Windows 用户生成可直接分发的 `workpulse.exe`。

## Local Build

在 Windows PowerShell 中执行：

```powershell
.\scripts\build_windows.ps1 -Clean
```

默认流程会：

1. 升级 `pip`
2. 安装 `.[windows,build]`
3. 使用 PyInstaller 按 [workpulse.spec](/Users/jamesyu/Projects/workpulse/workpulse.spec) 打包

输出目录：

- `dist\workpulse\`

## GitHub Actions

仓库内置了 Windows 打包工作流：

- [windows-build.yml](/Users/jamesyu/Projects/workpulse/.github/workflows/windows-build.yml)

触发方式：

- 推送到 `main`
- 手动 `workflow_dispatch`

工作流会：

1. 在 `windows-latest` 上安装 Python 3.11
2. 安装 `.[windows,build]`
3. 运行测试
4. 执行 PyInstaller 打包
5. 上传构建产物

## Notes

- 当前仍是控制台程序，不是图形界面安装器
- 如果目标环境没有 Python，优先分发 PyInstaller 产物
- 如果要进一步降低使用门槛，下一步可以补 MSI / Inno Setup 安装包
