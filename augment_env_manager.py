#!/usr/bin/env python3
"""
Augment 环境管理器

针对 C:/Users/<User>/.augment 目录（默认使用当前用户的 home/.augment），
提供：
- 环境信息扫描
- 备份当前 .augment 目录
- 清理除 settings.json 之外的所有内容，保证干净环境

该脚本不依赖 VSCode，只操作 .augment 目录，可作为工具被其它模块（如
@vscode_telemetry 中的工具）调用。
"""

import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class AugmentEnvManager:
    """Augment 本地环境管理器

    默认目标目录为 Path.home()/".augment"，在你的环境中即 C:\\Users\\Nunuaa\\.augment。
    """

    def __init__(self, augment_home: Optional[str] = None) -> None:
        self.home_path = Path.home()
        self.current_os = os.name  # 'nt' / 'posix'
        if augment_home is not None:
            self.augment_home = Path(augment_home).expanduser().resolve()
        else:
            self.augment_home = (self.home_path / ".augment").resolve()

        print(f"🖥️  当前用户目录: {self.home_path}")
        print(f"📁 目标 Augment 目录: {self.augment_home}")

    # ------------------------------------------------------------------
    # 基础工具方法
    # ------------------------------------------------------------------
    def _safe_path_under_home(self, path: Path) -> bool:
        """确保目标路径在用户 home 目录下，避免误删系统关键路径。"""
        try:
            path = path.resolve()
            home = self.home_path.resolve()
            return str(path).startswith(str(home))
        except Exception as e:
            logger.warning(f"路径检查失败: {path}: {e}")
            return False

    def _safe_count_items(self, path: Path) -> int:
        """统计目录下条目数量，用于报告，不因权限错误中断。"""
        if not path.exists():
            return 0
        if path.is_file():
            return 1
        count = 0
        try:
            for _ in path.rglob("*"):
                count += 1
        except Exception as e:
            logger.debug(f"统计 {path} 内容时出错: {e}")
        return count

    # ------------------------------------------------------------------
    # 查询 / 备份
    # ------------------------------------------------------------------
    def get_env_info(self) -> Dict:
        """获取当前 .augment 环境信息（只读，不修改任何内容）。"""
        info: Dict[str, object] = {
            "augment_home": str(self.augment_home),
            "exists": self.augment_home.exists(),
            "items": [],
        }

        if not self.augment_home.exists():
            return info

        for child in self.augment_home.iterdir():
            item = {
                "name": child.name,
                "is_dir": child.is_dir(),
                "size_items": self._safe_count_items(child),
            }
            info["items"].append(item)

        return info

    def backup_env(self, backup_root: Optional[str] = None) -> Dict:
        """备份整个 .augment 目录到一个新的备份文件夹。

        默认备份到 .augment 的父目录：例如 C:\\Users\\Nunuaa\\.augment-backup-YYYYmmdd-HHMMSS
        """
        if not self.augment_home.exists():
            return {
                "status": "not_found",
                "message": f"Augment 目录不存在: {self.augment_home}",
            }

        if not self._safe_path_under_home(self.augment_home):
            return {
                "status": "error",
                "message": f"目标目录不在当前用户 home 下，出于安全原因拒绝备份: {self.augment_home}",
            }

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        if backup_root is not None:
            backup_root_path = Path(backup_root).expanduser().resolve()
        else:
            backup_root_path = self.augment_home.parent

        backup_path = backup_root_path / f".augment-backup-{timestamp}"

        logger.info(f"开始备份 .augment -> {backup_path}")
        shutil.copytree(self.augment_home, backup_path)

        return {
            "status": "ok",
            "backup_path": str(backup_path),
        }

    # ------------------------------------------------------------------
    # 清理逻辑
    # ------------------------------------------------------------------
    def clean_env(self, preserve_items: Optional[List[str]] = None) -> Dict:
        """清理 .augment 目录中的非必需文件，保留必需的配置和工具。

        Args:
            preserve_items: 要保留的文件/目录名称列表。
                          默认保留: ["settings.json", "binaries"]

        Returns:
            包含清理结果的字典，包括删除数量、保留项、错误等信息
        """
        # 默认保留项：配置文件和二进制工具目录
        if preserve_items is None:
            preserve_items = ["settings.json", "binaries"]

        result: Dict[str, object] = {
            "augment_home": str(self.augment_home),
            "deleted_files": 0,
            "deleted_dirs": 0,
            "preserved_items": [],
            "errors": [],
        }

        if not self.augment_home.exists():
            result["status"] = "not_found"
            result["message"] = f"Augment 目录不存在: {self.augment_home}"
            print(result["message"])
            return result

        if not self._safe_path_under_home(self.augment_home):
            msg = f"目标目录不在当前用户 home 下，出于安全原因拒绝清理: {self.augment_home}"
            result["status"] = "error"
            result["message"] = msg
            print(msg)
            return result

        print("\n🔄 开始清理 .augment 目录...")
        print(f"� 保留项: {', '.join(preserve_items)}\n")

        for child in self.augment_home.iterdir():
            try:
                # 检查是否在保留列表中
                if child.name in preserve_items:
                    result["preserved_items"].append(str(child))
                    item_type = "目录" if child.is_dir() else "文件"
                    print(f"   ✅ 保留{item_type}: {child.name}")
                    continue

                # 删除非保留项
                if child.is_dir():
                    items = self._safe_count_items(child)
                    shutil.rmtree(child)
                    result["deleted_dirs"] += 1
                    result["deleted_files"] += items
                    print(f"   🗑️  删除目录: {child.name} ({items} 个条目)")
                else:
                    child.unlink()
                    result["deleted_files"] += 1
                    print(f"   🗑️  删除文件: {child.name}")

            except Exception as e:
                logger.error(f"删除 {child} 时出错: {e}")
                result["errors"].append({"path": str(child), "error": str(e)})

        print("\n✅ 清理完成！")
        print(f"   删除文件数: {result['deleted_files']}")
        print(f"   删除目录数: {result['deleted_dirs']}")
        if result["preserved_items"]:
            print(f"   保留项数: {len(result['preserved_items'])}")
            for p in result["preserved_items"]:
                print(f"      - {Path(p).name}")

        result["status"] = "ok"
        result["message"] = f"Augment 本地环境已清理，保留了 {len(result['preserved_items'])} 个必需项。"
        return result


def main() -> None:
    """简单命令行入口：

    - 显示当前 .augment 目录
    - 显示其中的主要条目
    - 询问是否执行清理（仅保留 settings.json）
    """
    manager = AugmentEnvManager()

    info = manager.get_env_info()
    print("\n=== 当前 Augment 环境信息 ===")
    print(json.dumps(info, indent=2, ensure_ascii=False))

    if not info["exists"]:
        print("\n⚠️  .augment 目录不存在，无需清理。")
        return

    print("\n该操作将：")
    print("  1. 可选地备份整个 .augment 目录")
    print("  2. 删除除 settings.json 之外的所有文件和子目录")
    print("  3. 为你保留当前的 settings.json 配置")

    confirm = input("\n是否继续执行清理? (y/N): ").strip().lower()
    if confirm != "y":
        print("已取消操作。")
        return

    try:
        # 只保留 settings.json，删除其他所有内容
        result = manager.clean_env(preserve_items=["settings.json"])
        print("\n=== 清理结果 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except KeyboardInterrupt:
        print("\n操作已被用户中断。")
    except Exception as e:
        print(f"\n执行过程中出错: {e}")
        logger.exception("执行失败")


if __name__ == "__main__":
    main()

