# Augment Cleaner

Augment 环境管理工具集，用于清理和管理 VSCode/Cursor 相关的 Augment 扩展数据。

## 项目简介

本项目包含两个主要工具：

### 1. `augment_env_manager.py`
专门管理 `~/.augment` 目录（Augment 本地环境）的工具。

**功能：**
- 📊 扫描并显示 `.augment` 目录信息
- 🧹 清理非必需文件（缓存、日志、临时文件等）
- 💾 保留必需配置（默认保留 `settings.json`）
- 🔒 安全检查，防止误删系统关键路径

**使用方法：**

```bash
# 命令行交互模式
python augment_env_manager.py

# 在代码中调用
from augment_env_manager import AugmentEnvManager

manager = AugmentEnvManager()

# 只保留 settings.json
result = manager.clean_env(preserve_items=["settings.json"])

# 自定义保留项
result = manager.clean_env(preserve_items=["settings.json", "binaries"])
```

### 2. `vscode_telemetry_manager_crossplatform.py`
跨平台的 VSCode/Cursor/Windsurf 遥测和扩展管理工具。

**功能：**
- 🔄 修改遥测 ID（`telemetry.machineId`、`telemetry.devDeviceId`）
- 🗄️ 清理数据库中的 Augment 相关数据
- 📁 清理工作区存储（workspaceStorage）
- 💬 清除聊天历史
- 🔌 扩展缓存清理
- 📝 日志和崩溃报告清理
- 🌐 浏览器缓存清理
- 🔍 深度扫描 Augment 数据
- ⚙️ 扩展安装/卸载管理

**支持的编辑器：**
- VSCode
- Cursor
- Windsurf
- VSCodium
- Code - OSS
- 以及其他 VSCode 系列编辑器

## 系统要求

- Python 3.7+
- 支持的操作系统：Windows、macOS、Linux

## 安装依赖

```bash
pip install psutil  # 可选，用于高级进程管理
```

## 安全特性

- ✅ 路径安全检查，防止删除系统关键目录
- ✅ 权限验证
- ✅ 操作前确认
- ✅ 详细的操作日志
- ✅ 错误处理和回滚机制

## 注意事项

⚠️ **重要提醒：**
- 清理操作会永久删除数据，建议操作前手动备份重要文件
- 首次使用建议先使用查询功能了解将要删除的内容
- 某些操作可能需要管理员权限

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 作者

Created for managing Augment extension environments.

