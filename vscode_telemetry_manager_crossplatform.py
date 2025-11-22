#!/usr/bin/env python3
"""
VS Code/Cursor/VSCodium Telemetry Manager (跨平台版) - 优化版
修改遥测ID和清理数据库工具
支持 Windows/macOS/Linux 系统自动检测

优化特性:
- 配置文件支持 (telemetry_config.json)
- 并发处理提升性能
- 更精确的Augment对话数据清理
- 权限检查和安全验证
"""
import json
import sqlite3
import uuid
import shutil
import subprocess
import glob
import logging
import re
import time
import sys
import platform
import os
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# 尝试导入psutil，如果没有安装则使用备用方案
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logging.warning("psutil未安装，将使用基本的进程管理功能")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TelemetryManager:
    """VS Code系列编辑器的遥测管理器 (跨平台) - 优化版"""

    # 支持的编辑器配置 - 扩展版（支持所有VSCode系列）
    EDITORS = {
        # 主流编辑器
        'vscode': 'Code',
        'cursor': 'Cursor',
        'windsurf': 'Windsurf',
        'vscodium': 'VSCodium',

        # VS Code变体
        'code-oss': 'Code - OSS',
        'vscode-insiders': 'Code - Insiders',
        'vscode-exploration': 'Code - Exploration',

        # AI编辑器
        'codebuddy': 'CodeBuddy',
        'kiro': 'Kiro',
        'trae': 'Trae',
        'qoder': 'Qoder',

        # 其他基于VSCode的编辑器
        'theia': 'Theia',
        'openvscode': 'OpenVSCode',
        'gitpod': 'Gitpod',
        'code-server': 'code-server',
        'stackblitz': 'StackBlitz',

        # 企业版
        'vscode-server': 'VS Code Server',
        'github-codespaces': 'GitHub Codespaces'
    }

    def __init__(self, config_path: Optional[str] = None):
        self.home_path = Path.home()
        self.current_os = platform.system().lower()
        self.app_support_path = self._get_app_support_path()

        # 加载配置文件
        self.config = self._load_config(config_path)

        print(f"🖥️  检测到系统: {self.current_os.title()}")
        print(f"📁 配置路径: {self.app_support_path}")
        print(f"⚙️  配置版本: {self.config.get('version', 'N/A')}")

    def _load_config(self, config_path: Optional[str] = None) -> Dict:
        """加载配置 - 默认使用内置配置，可选外部配置文件"""
        # 先获取内置配置
        config = self._get_default_config()

        # 如果提供了外部配置文件路径，尝试加载并合并
        if config_path is not None:
            config_path = Path(config_path)
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        user_config = json.load(f)

                    # 深度合并配置
                    for key, value in user_config.items():
                        if isinstance(value, dict) and key in config:
                            config[key].update(value)
                        else:
                            config[key] = value

                    logger.info(f"✅ 已加载外部配置: {config_path}")
                except Exception as e:
                    logger.warning(f"⚠️  加载外部配置失败: {e}，使用内置配置")

        return config

    def _get_default_config(self) -> Dict:
        """获取内置配置 - 全集成，无需外部文件"""
        return {
            "version": "3.0",

            # Augment扩展ID列表（支持所有VSCode系列编辑器）
            "augment_extension_ids": [
                "augmentcode.augment",
                "augmentcode.augment-vscode",
                "augmentcode.augment-cursor",
                "augmentcode.augment-windsurf",
                "augmentcode.augment-vscodium",
                "augment.augment",
                "vscode-augment",
                "augment-code",
                "augmentcode.vscode-augment"
            ],

            # AI扩展ID列表（可选清理）
            "ai_extension_ids": [
                "github.copilot",
                "github.copilot-chat",
                "tabnine.tabnine-vscode",
                "codeium.codeium",
                "continue.continue",
                "amazonwebservices.aws-toolkit-vscode",
                "cursor.cursor-vscode"
            ],

            # 数据库清理关键词
            "database_cleanup_keys": {
                "augment_specific": [
                    "%augment%", "%AugmentCode%", "%augmentcode%",
                    "%chat%", "%conversation%", "%message%",
                    "%dialog%", "%session%", "%history%",
                    "%Fix with Augment%", "%vscode-augment%"
                ],
                "chat": [
                    "%chat%", "%conversation%", "%message%", "%dialog%",
                    "%session%", "%history%", "%augment%", "%AugmentCode%",
                    "%augmentcode%", "%vscode-augment%", "%Fix with Augment%"
                ],
                "analytics": [
                    "%telemetry%", "%tracking%", "%analytics%", "%metrics%"
                ]
            },

            # 危险路径（防止误删）
            "dangerous_paths": [
                "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
                "/System", "/Library", "/usr", "/bin", "/sbin",
                str(Path.home()),
                str(Path.home() / "Desktop"),
                str(Path.home() / "Documents"),
                str(Path.home() / "Downloads")
            ],

            # 性能配置
            "performance": {
                "enable_parallel_processing": True,
                "max_workers": 4,
                "scan_timeout": 300,  # 扫描超时（秒）
                "clean_timeout": 600  # 清理超时（秒）
            },

            # 检测配置
            "detection": {
                "enable_auto_scan": True,  # 启用自动扫描
                "enable_windows_programs_scan": True,  # Windows Programs目录扫描
                "known_editors_only": False  # 仅检测已知编辑器
            },

            # 清理配置
            "cleanup": {
                "backup_before_clean": True,  # 清理前备份
                "verify_after_clean": True,   # 清理后验证
                "max_retries": 3,             # 最大重试次数
                "retry_delay": 2              # 重试延迟（秒）
            }
        }
    
    def _get_app_support_path(self) -> Path:
        """根据操作系统获取应用支持路径"""
        if self.current_os == 'windows':
            # Windows: %APPDATA%
            return Path(os.environ.get('APPDATA', self.home_path / 'AppData' / 'Roaming'))
        elif self.current_os == 'darwin':
            # macOS: ~/Library/Application Support
            return self.home_path / "Library" / "Application Support"
        else:
            # Linux: ~/.config
            return self.home_path / ".config"
        
    def get_editor_path(self, editor_type: str) -> Path:
        """获取编辑器的配置路径"""
        if editor_type not in self.EDITORS:
            raise ValueError(f"不支持的编辑器类型: {editor_type}")
        
        return self.app_support_path / self.EDITORS[editor_type]
    
    def get_system_info(self) -> Dict:
        """获取系统信息 - 增强版，自动检测所有VSCode系列编辑器"""
        info = {
            'platform': self.current_os,
            'platform_version': platform.platform(),
            'python_version': platform.python_version(),
            'home_path': str(self.home_path),
            'app_support_path': str(self.app_support_path),
            'available_editors': []
        }

        print("\n🔍 正在扫描已安装的VSCode系列编辑器...")

        # 方法1: 检测已知编辑器
        for editor_key, editor_name in self.EDITORS.items():
            editor_path = self.get_editor_path(editor_key)
            if editor_path.exists():
                # 检查是否真的是编辑器目录（包含User目录）
                user_dir = editor_path / "User"
                if user_dir.exists():
                    info['available_editors'].append({
                        'type': editor_key,
                        'name': editor_name,
                        'path': str(editor_path),
                        'detection_method': 'known_editor'
                    })
                    print(f"   ✅ 找到: {editor_name} ({editor_key})")

        # 方法2: 自动扫描app_support_path下的所有可能的编辑器
        print("\n🔍 扫描未知的VSCode系列编辑器...")
        if self.app_support_path.exists():
            for item in self.app_support_path.iterdir():
                if item.is_dir():
                    # 检查是否是VSCode系列编辑器的特征
                    user_dir = item / "User"
                    global_storage = item / "User" / "globalStorage"

                    # 特征检测：有User目录和globalStorage
                    if user_dir.exists() and global_storage.exists():
                        # 检查是否已经在已知列表中
                        already_detected = any(
                            e['path'] == str(item)
                            for e in info['available_editors']
                        )

                        if not already_detected:
                            # 尝试识别编辑器类型
                            editor_name = item.name
                            editor_key = editor_name.lower().replace(' ', '-')

                            info['available_editors'].append({
                                'type': editor_key,
                                'name': editor_name,
                                'path': str(item),
                                'detection_method': 'auto_scan'
                            })
                            print(f"   🆕 发现未知编辑器: {editor_name}")

        # 方法3: 检查常见的安装位置（Windows特殊处理）
        if self.current_os == 'windows':
            print("\n🔍 检查Windows特殊安装位置...")
            local_appdata = Path(os.environ.get('LOCALAPPDATA', ''))
            if local_appdata.exists():
                # 检查Programs目录
                programs_dir = local_appdata / "Programs"
                if programs_dir.exists():
                    for item in programs_dir.iterdir():
                        if item.is_dir():
                            # 检查是否有VSCode特征
                            possible_data_dirs = [
                                self.app_support_path / item.name,
                                self.app_support_path / item.name.replace(' ', '')
                            ]

                            for data_dir in possible_data_dirs:
                                if data_dir.exists() and (data_dir / "User").exists():
                                    already_detected = any(
                                        e['path'] == str(data_dir)
                                        for e in info['available_editors']
                                    )

                                    if not already_detected:
                                        editor_name = item.name
                                        editor_key = editor_name.lower().replace(' ', '-')

                                        info['available_editors'].append({
                                            'type': editor_key,
                                            'name': editor_name,
                                            'path': str(data_dir),
                                            'detection_method': 'windows_programs'
                                        })
                                        print(f"   🆕 发现: {editor_name} (Programs目录)")

        print(f"\n✅ 共检测到 {len(info['available_editors'])} 个编辑器")

        return info
    
    def kill_editor_processes(self, editor_type: str) -> bool:
        """强制结束编辑器进程 (跨平台)"""
        try:
            editor_name = self.EDITORS[editor_type]
            
            if self.current_os == 'windows':
                # Windows: 使用taskkill强制杀死
                result = subprocess.run(
                    ['taskkill', '/F', '/IM', f'{editor_name}.exe'],
                    capture_output=True, 
                    text=True
                )
            elif self.current_os == 'darwin':
                # macOS: 使用killall -9强制杀死
                result = subprocess.run(
                    ['killall', '-9', editor_name], 
                    capture_output=True, 
                    text=True
                )
            else:
                # Linux: 使用pkill -9强制杀死
                result = subprocess.run(
                    ['pkill', '-9', '-f', editor_name], 
                    capture_output=True, 
                    text=True
                )
                
            logger.info(f"尝试结束 {editor_name} 进程 ({self.current_os}): {result.returncode}")
            return True
        except Exception as e:
            logger.error(f"结束进程时出错: {e}")
            return False
    
    def kill_editor_processes_command(self, editor_type: str) -> Dict:
        """完整的进程管理命令 - 带等待和状态检查"""
        
        logger.info(f"开始完整进程终止流程: {editor_type}")
        
        if not HAS_PSUTIL:
            # 如果没有psutil，回退到基本的进程管理
            logger.warning("psutil不可用，使用基本进程管理")
            basic_result = self.kill_editor_processes(editor_type)
            return {
                'editor_type': editor_type,
                'status': 'success' if basic_result else 'error',
                'message': '使用基本进程管理功能',
                'killed_processes': [],
                'remaining_processes': [],
                'fallback_used': True
            }
        
        editor_info = {
            'vscode': {
                'app_names': ['Visual Studio Code', 'Code'],
                'process_names': ['code', 'Code Helper']
            },
            'cursor': {
                'app_names': ['Cursor'],
                'process_names': ['cursor', 'Cursor Helper']
            },
            'vscodium': {
                'app_names': ['VSCodium'],
                'process_names': ['codium', 'VSCodium Helper']
            },
            'code-oss': {
                'app_names': ['Code - OSS'],
                'process_names': ['code-oss', 'code-oss Helper']
            },
            'vscode-insiders': {
                'app_names': ['Visual Studio Code - Insiders'],
                'process_names': ['code-insiders', 'code-insiders Helper']
            },
            'theia': {
                'app_names': ['Theia'],
                'process_names': ['theia', 'node']
            },
            'openvscode': {
                'app_names': ['OpenVSCode Server'],
                'process_names': ['openvscode-server', 'node']
            },
            'gitpod': {
                'app_names': ['Gitpod'],
                'process_names': ['gitpod', 'node']
            }
        }
        
        if editor_type not in editor_info:
            return {
                'editor_type': editor_type,
                'status': 'error',
                'error': f'不支持的编辑器类型: {editor_type}'
            }
        
        info = editor_info[editor_type]
        killed_processes = []
        remaining_processes = []
        
        try:
            # 第1步: 查找运行中的进程
            logger.info("步骤1: 查找目标进程")
            target_processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_name = proc.info['name']
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    
                    # 检查进程名或命令行是否匹配
                    is_target = False
                    for name in info['process_names']:
                        if name.lower() in proc_name.lower() or name.lower() in cmdline.lower():
                            is_target = True
                            break
                    
                    if is_target:
                        target_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc_name,
                            'cmdline': cmdline[:100]  # 截断过长的命令行
                        })
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            logger.info(f"找到 {len(target_processes)} 个目标进程")
            
            if not target_processes:
                return {
                    'editor_type': editor_type,
                    'status': 'success',
                    'message': '未找到运行中的进程',
                    'killed_processes': [],
                    'remaining_processes': []
                }
            
            # 第2步: 优雅终止进程 (SIGTERM)
            logger.info("步骤2: 发送SIGTERM信号")
            for proc_info in target_processes:
                try:
                    proc = psutil.Process(proc_info['pid'])
                    proc.terminate()
                    logger.info(f"发送SIGTERM到进程 {proc_info['pid']}: {proc_info['name']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.warning(f"无法终止进程 {proc_info['pid']}: {e}")
            
            # 第3步: 等待进程退出 (最多10秒)
            logger.info("步骤3: 等待进程退出")
            wait_time = 0
            max_wait = 10
            
            while wait_time < max_wait:
                time.sleep(1)
                wait_time += 1
                
                # 检查进程是否还在运行
                remaining = []
                for proc_info in target_processes:
                    try:
                        proc = psutil.Process(proc_info['pid'])
                        if proc.is_running():
                            remaining.append(proc_info)
                    except psutil.NoSuchProcess:
                        # 进程已经退出
                        killed_processes.append(proc_info)
                
                if not remaining:
                    logger.info(f"所有进程已退出 (耗时 {wait_time} 秒)")
                    break
                    
                target_processes = remaining
            
            # 第4步: 强制终止剩余进程 (SIGKILL)
            if target_processes:
                logger.info("步骤4: 强制终止剩余进程")
                for proc_info in target_processes:
                    try:
                        proc = psutil.Process(proc_info['pid'])
                        proc.kill()
                        logger.info(f"强制终止进程 {proc_info['pid']}: {proc_info['name']}")
                        killed_processes.append(proc_info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        logger.error(f"无法强制终止进程 {proc_info['pid']}: {e}")
                        remaining_processes.append(proc_info)
                
                # 最后检查
                time.sleep(2)
                final_remaining = []
                for proc_info in target_processes:
                    try:
                        proc = psutil.Process(proc_info['pid'])
                        if proc.is_running():
                            final_remaining.append(proc_info)
                    except psutil.NoSuchProcess:
                        pass
                
                remaining_processes = final_remaining
            
            # 第5步: 确保文件访问权限释放
            logger.info("步骤5: 等待文件系统释放")
            time.sleep(2)  # 给文件系统一些时间来释放锁定的文件
            
            result = {
                'editor_type': editor_type,
                'status': 'success' if not remaining_processes else 'partial',
                'killed_processes': killed_processes,
                'remaining_processes': remaining_processes,
                'total_found': len(killed_processes) + len(remaining_processes),
                'total_killed': len(killed_processes),
                'total_remaining': len(remaining_processes),
                'wait_time_seconds': wait_time,
                'message': f'进程终止完成。成功: {len(killed_processes)}, 剩余: {len(remaining_processes)}'
            }
            
            if remaining_processes:
                logger.warning(f"仍有 {len(remaining_processes)} 个进程无法终止")
            else:
                logger.info("所有目标进程已成功终止")
            
            return result
            
        except Exception as e:
            logger.error(f"进程管理过程中出错: {e}")
            return {
                'editor_type': editor_type,
                'status': 'error',
                'error': str(e),
                'killed_processes': killed_processes,
                'remaining_processes': remaining_processes
            }
    
    def modify_telemetry_ids(self, editor_type: str) -> Dict:
        """修改遥测ID"""
        print("🔄 正在修改遥测ID...")
        print(f"   📁 目标编辑器: {self.EDITORS.get(editor_type, editor_type)}")
        sys.stdout.flush()
        
        editor_path = self.get_editor_path(editor_type)
        storage_path = editor_path / "User" / "globalStorage" / "storage.json"
        
        if not storage_path.exists():
            print(f"   ❌ 配置文件不存在: {storage_path}")
            raise FileNotFoundError(f"配置文件不存在: {storage_path}")
        
        print("   📋 创建备份文件...")
        # 创建备份
        backup_path = storage_path.with_suffix('.json.bak')
        shutil.copy2(storage_path, backup_path)
        print(f"   ✅ 备份已创建: {backup_path.name}")
        logger.info(f"已创建备份: {backup_path}")
        
        # 创建 machine_id_backup_path 备份 (需求中提到的额外备份)
        machine_id_backup_path = editor_path / "User" / "globalStorage" / "machine_id_backup.json"
        
        print("   📖 读取现有配置...")
        # 读取现有配置
        with open(storage_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 记录原始ID
        old_machine_id = config.get('telemetry.machineId', 'NOT_FOUND')
        old_device_id = config.get('telemetry.devDeviceId', 'NOT_FOUND')
        
        print(f"   🆔 原始machineId: {old_machine_id[:8]}...")
        print(f"   🆔 原始deviceId: {old_device_id[:8]}...")
        
        print("   💾 创建ID专用备份...")
        # 创建machine_id专门备份
        machine_id_backup = {
            'timestamp': str(uuid.uuid4()),  # 用作时间戳标识
            'old_machine_id': old_machine_id,
            'old_device_id': old_device_id,
            'editor_type': editor_type
        }
        
        with open(machine_id_backup_path, 'w', encoding='utf-8') as f:
            json.dump(machine_id_backup, f, indent=2, ensure_ascii=False)
        
        print("   🎲 生成新的ID...")
        # 生成新的ID
        new_machine_id = str(uuid.uuid4())
        new_device_id = str(uuid.uuid4())
        
        print(f"   🆕 新machineId: {new_machine_id[:8]}...")
        print(f"   🆕 新deviceId: {new_device_id[:8]}...")
        
        print("   💾 保存新配置...")
        # 更新配置
        config['telemetry.machineId'] = new_machine_id
        config['telemetry.devDeviceId'] = new_device_id
        
        # 保存配置
        with open(storage_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print("   ✅ 遥测ID修改完成！")
        
        result = {
            'editor_type': editor_type,
            'backup_created': str(backup_path),
            'machine_id_backup_path': str(machine_id_backup_path),
            'old_machine_id': old_machine_id,
            'new_machine_id': new_machine_id,
            'old_device_id': old_device_id,
            'new_device_id': new_device_id,
            'storage_path': str(storage_path)
        }
        
        logger.info(f"遥测ID修改完成: {editor_type}")
        logger.debug(f"原始machineId: {old_machine_id}")
        logger.debug(f"新machineId: {new_machine_id}")
        logger.debug(f"原始deviceId: {old_device_id}")
        logger.debug(f"新deviceId: {new_device_id}")
        return result
    
    def clean_database(self, editor_type: str) -> Dict:
        """清理数据库中的augment相关数据"""
        print("\n🔄 正在清理数据库...")
        print(f"   🎯 目标: 删除包含'augment'的数据")
        sys.stdout.flush()
        
        editor_path = self.get_editor_path(editor_type)
        workspace_storage_path = editor_path / "User" / "workspaceStorage"
        
        if not workspace_storage_path.exists():
            print("   ⚠️  工作区存储目录不存在")
            return {'deleted_rows': 0, 'message': '工作区存储目录不存在'}
        
        total_deleted = 0
        processed_dbs = []
        
        print("   🔍 查找数据库文件...")
        # 查找所有state.vscdb文件
        db_pattern = str(workspace_storage_path / "*" / "state.vscdb")
        db_files = glob.glob(db_pattern)
        
        print(f"   📁 找到 {len(db_files)} 个数据库文件")
        
        for i, db_file in enumerate(db_files, 1):
            print(f"   🗃️  处理数据库 {i}/{len(db_files)}: {Path(db_file).parent.name}")
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                
                # 执行删除操作
                cursor.execute("DELETE FROM ItemTable WHERE key LIKE '%augment%'")
                deleted_count = cursor.rowcount
                total_deleted += deleted_count
                
                conn.commit()
                conn.close()
                
                if deleted_count > 0:
                    print(f"      ✅ 删除了 {deleted_count} 行数据")
                else:
                    print(f"      ⚪ 无需要删除的数据")
                
                processed_dbs.append({
                    'db_file': db_file,
                    'deleted_rows': deleted_count
                })
                
                logger.info(f"已清理数据库 {db_file}: 删除 {deleted_count} 行")
                
            except Exception as e:
                print(f"      ❌ 处理失败: {e}")
                logger.error(f"清理数据库 {db_file} 时出错: {e}")
                processed_dbs.append({
                    'db_file': db_file,
                    'error': str(e)
                })
        
        print(f"   ✅ 数据库清理完成！共删除 {total_deleted} 行数据")
        
        result = {
            'editor_type': editor_type,
            'total_deleted_rows': total_deleted,
            'deleted_rows': total_deleted,  # 兼容字段
            'processed_databases': processed_dbs,
            'message': f'Database cleaned successfully. Deleted {total_deleted} rows.'
        }
        
        return result
    
    def clean_workspace(self, editor_type: str) -> Dict:
        """清理工作区文件"""
        print("\n🔄 正在清理工作区...")
        print(f"   🎯 目标: 删除augment相关工作区文件")
        
        editor_path = self.get_editor_path(editor_type)
        workspace_storage_path = editor_path / "User" / "workspaceStorage"
        
        if not workspace_storage_path.exists():
            print("   ⚠️  工作区存储目录不存在")
            return {'deleted_files': 0, 'message': '工作区存储目录不存在'}
        
        deleted_files = 0
        deleted_dirs = []
        
        print("   🔍 扫描工作区目录...")
        # 查找包含augment的目录
        workspace_dirs = list(workspace_storage_path.iterdir())
        print(f"   📁 找到 {len(workspace_dirs)} 个工作区目录")
        
        processed_count = 0
        for workspace_dir in workspace_dirs:
            if workspace_dir.is_dir():
                processed_count += 1
                print(f"   📂 检查目录 {processed_count}/{len(workspace_dirs)}: {workspace_dir.name[:20]}...")
                
                # 检查目录中是否有augment相关文件
                augment_files = list(workspace_dir.glob("*augment*"))
                if augment_files:
                    print(f"      🎯 发现 {len(augment_files)} 个augment相关文件")
                    try:
                        for file_path in augment_files:
                            if file_path.is_file():
                                file_path.unlink()
                                deleted_files += 1
                                print(f"         🗑️  删除文件: {file_path.name}")
                            elif file_path.is_dir() and not self._is_dangerous_path(file_path):
                                file_count = len(list(file_path.rglob("*")))
                                shutil.rmtree(file_path)
                                deleted_files += file_count
                                print(f"         🗑️  删除目录: {file_path.name} ({file_count}个文件)")
                        
                        deleted_dirs.append(str(workspace_dir))
                        print(f"      ✅ 清理完成: {workspace_dir.name}")
                        logger.info(f"已清理工作区目录: {workspace_dir}")
                        
                    except Exception as e:
                        print(f"      ❌ 清理失败: {e}")
                        logger.error(f"清理工作区 {workspace_dir} 时出错: {e}")
                else:
                    print(f"      ⚪ 无augment文件")
        
        print(f"   ✅ 工作区清理完成！共删除 {deleted_files} 个文件")
        
        result = {
            'editor_type': editor_type,
            'deleted_files': deleted_files,
            'processed_directories': deleted_dirs,
            'message': f'Workspace cleaned successfully. Deleted {deleted_files} files.'
        }
        
        return result
    
    def deep_scan_augment_data(self, editor_type: str) -> Dict:
        """深度扫描所有Augment相关数据 - 多方案检测"""
        print("\n🔍 正在执行深度扫描...")
        print(f"   🎯 目标: 全面检测Augment数据位置")

        editor_path = self.get_editor_path(editor_type)
        found_locations = {
            'globalStorage_dirs': [],
            'workspaceStorage_dirs': [],
            'database_files': [],
            'cache_files': [],
            'config_files': [],
            'other_files': []
        }

        # 从配置获取扩展ID列表
        ext_ids = self.config.get('augment_extension_ids', [
            'augmentcode.augment',
            'augmentcode.augment-vscode',
            'augment.augment'
        ])

        # 方案1: 扫描globalStorage - 精确匹配扩展ID
        print("   📂 方案1: 扫描globalStorage (精确匹配)...")
        global_storage = editor_path / "User" / "globalStorage"
        if global_storage.exists():
            # 精确匹配扩展ID
            for ext_id in ext_ids:
                ext_path = global_storage / ext_id
                if ext_path.exists():
                    found_locations['globalStorage_dirs'].append(ext_path)
                    print(f"      🎯 找到扩展: {ext_id}")

            # 模糊匹配包含augment的目录
            for item in global_storage.iterdir():
                if item.is_dir() and 'augment' in item.name.lower():
                    if item not in found_locations['globalStorage_dirs']:
                        found_locations['globalStorage_dirs'].append(item)
                        print(f"      🎯 找到目录: {item.name}")

                    # 检查目录内容
                    try:
                        for sub_item in item.rglob("*"):
                            if 'augment' in str(sub_item).lower() or 'chat' in str(sub_item).lower():
                                if sub_item.is_file() and sub_item not in found_locations['other_files']:
                                    found_locations['other_files'].append(sub_item)
                    except:
                        pass

        # 方案2: 扫描workspaceStorage - 多重检测
        print("   📂 方案2: 扫描workspaceStorage (多重检测)...")
        workspace_storage = editor_path / "User" / "workspaceStorage"
        if workspace_storage.exists():
            for workspace_dir in workspace_storage.iterdir():
                if workspace_dir.is_dir():
                    should_clean = False

                    # 检测1: workspace.json内容
                    workspace_json = workspace_dir / "workspace.json"
                    if workspace_json.exists():
                        try:
                            with open(workspace_json, 'r', encoding='utf-8') as f:
                                content = f.read().lower()
                                if any(keyword in content for keyword in ['augment', 'augmentcode']):
                                    should_clean = True
                                    print(f"      🎯 workspace.json匹配: {workspace_dir.name[:20]}...")
                        except:
                            pass

                    # 检测2: 扫描augment相关文件
                    try:
                        augment_files = list(workspace_dir.glob("*augment*"))
                        if augment_files:
                            should_clean = True
                            print(f"      🎯 文件名匹配: {workspace_dir.name[:20]}... ({len(augment_files)}个文件)")
                    except:
                        pass

                    # 检测3: 检查state.vscdb数据库
                    state_db = workspace_dir / "state.vscdb"
                    if state_db.exists():
                        try:
                            conn = sqlite3.connect(str(state_db))
                            cursor = conn.cursor()
                            cursor.execute("SELECT COUNT(*) FROM ItemTable WHERE key LIKE '%augment%'")
                            count = cursor.fetchone()[0]
                            conn.close()
                            if count > 0:
                                should_clean = True
                                print(f"      🎯 数据库匹配: {workspace_dir.name[:20]}... ({count}条记录)")
                        except:
                            pass

                    if should_clean and workspace_dir not in found_locations['workspaceStorage_dirs']:
                        found_locations['workspaceStorage_dirs'].append(workspace_dir)

        # 方案3: 扫描数据库 - 扩展关键词检测
        print("   📂 方案3: 扫描数据库 (扩展关键词)...")
        if workspace_storage.exists():
            db_pattern = str(workspace_storage / "*" / "state.vscdb")
            db_files = glob.glob(db_pattern)

            # 扩展的数据库检测关键词
            db_keywords = self.config.get('database_cleanup_keys', {}).get('augment_specific', [
                '%augment%', '%AugmentCode%', '%augmentcode%',
                '%chat%', '%conversation%', '%message%'
            ])

            for db_file in db_files:
                try:
                    conn = sqlite3.connect(db_file)
                    cursor = conn.cursor()

                    total_count = 0
                    for keyword in db_keywords:
                        cursor.execute("SELECT COUNT(*) FROM ItemTable WHERE key LIKE ?", (keyword,))
                        count = cursor.fetchone()[0]
                        total_count += count

                    conn.close()

                    if total_count > 0:
                        found_locations['database_files'].append((db_file, total_count))
                        print(f"      🎯 找到数据库: {Path(db_file).parent.name[:20]}... ({total_count}条)")
                except:
                    pass

        # 方案4: 全局文件名搜索 - 多模式匹配
        print("   📂 方案4: 全局文件名搜索 (多模式)...")
        search_patterns = [
            '*augment*', '*conversation*', '*chat*', '*dialog*',
            '*AugmentCode*', '*augmentcode*', '*.augment'
        ]

        try:
            for pattern in search_patterns:
                matches = list(editor_path.rglob(pattern))
                for match in matches[:20]:  # 增加显示数量
                    # 过滤掉已经在其他列表中的
                    if (match not in found_locations['other_files'] and
                        match not in found_locations['globalStorage_dirs'] and
                        match not in found_locations['workspaceStorage_dirs']):

                        # 只添加文件，不添加目录（目录已在前面处理）
                        if match.is_file():
                            found_locations['other_files'].append(match)
                            print(f"      🎯 找到文件: {match.name}")
        except Exception as e:
            logger.debug(f"全局搜索出错: {e}")

        # 方案5: 检查配置文件中的augment设置
        print("   📂 方案5: 检查配置文件...")
        settings_json = editor_path / "User" / "settings.json"
        if settings_json.exists():
            try:
                with open(settings_json, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'augment' in content.lower():
                        found_locations['config_files'].append(settings_json)
                        print(f"      🎯 settings.json包含augment配置")
            except:
                pass

        keybindings_json = editor_path / "User" / "keybindings.json"
        if keybindings_json.exists():
            try:
                with open(keybindings_json, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'augment' in content.lower():
                        found_locations['config_files'].append(keybindings_json)
                        print(f"      🎯 keybindings.json包含augment配置")
            except:
                pass

        # 统计
        total_found = (
            len(found_locations['globalStorage_dirs']) +
            len(found_locations['workspaceStorage_dirs']) +
            len(found_locations['database_files']) +
            len(found_locations['other_files'])
        )

        print(f"   ✅ 深度扫描完成！共发现 {total_found} 个位置")

        return {
            'editor_type': editor_type,
            'found_locations': found_locations,
            'total_found': total_found
        }

    def clear_chat_history(self, editor_type: str) -> Dict:
        """清理聊天历史记录 - 优化版，针对Augment扩展"""
        print("\n🔄 正在清理聊天历史...")
        print(f"   🎯 目标: 删除聊天记录和augment缓存")

        editor_path = self.get_editor_path(editor_type)
        global_storage = editor_path / "User" / "globalStorage"
        workspace_storage = editor_path / "User" / "workspaceStorage"

        # 扩展的可能ID（Augment扩展的各种变体）
        augment_extension_ids = [
            'augmentcode.augment',
            'augmentcode.augment-vscode',
            'augment.augment',
            'vscode-augment',
            'augment-code',
            'augmentcode.vscode-augment'
        ]

        # 更全面的聊天历史存储位置
        chat_paths = []

        # 1. globalStorage下的扩展目录
        if global_storage.exists():
            for ext_id in augment_extension_ids:
                ext_path = global_storage / ext_id
                if ext_path.exists():
                    chat_paths.append(ext_path)

            # 通配符匹配任何包含augment的目录
            for item in global_storage.iterdir():
                if item.is_dir() and 'augment' in item.name.lower():
                    if item not in chat_paths:
                        chat_paths.append(item)

        # 2. workspaceStorage下的扩展数据
        if workspace_storage.exists():
            for workspace_dir in workspace_storage.iterdir():
                if workspace_dir.is_dir():
                    # 检查workspace.json中是否包含augment
                    workspace_json = workspace_dir / "workspace.json"
                    if workspace_json.exists():
                        try:
                            with open(workspace_json, 'r', encoding='utf-8') as f:
                                content = f.read()
                                if 'augment' in content.lower():
                                    chat_paths.append(workspace_dir)
                        except:
                            pass

                    # 检查是否有augment相关文件
                    augment_files = list(workspace_dir.glob("*augment*"))
                    if augment_files and workspace_dir not in chat_paths:
                        chat_paths.append(workspace_dir)

        # 3. 其他可能的位置
        additional_paths = [
            editor_path / "User" / "globalStorage" / "chat",
            editor_path / "CachedExtensions" / "*augment*",
            editor_path / "User" / "History" / "*augment*",
        ]

        for path_pattern in additional_paths:
            if "*" in str(path_pattern):
                matching = glob.glob(str(path_pattern))
                chat_paths.extend([Path(p) for p in matching if Path(p).exists()])
            elif path_pattern.exists():
                chat_paths.append(path_pattern)

        # 去重
        chat_paths = list(set(chat_paths))

        deleted_files = 0
        processed_paths = []

        print(f"   🔍 找到 {len(chat_paths)} 个需要清理的位置...")

        for i, path_obj in enumerate(chat_paths, 1):
            print(f"   📂 清理位置 {i}/{len(chat_paths)}: {path_obj.name}")

            try:
                if not self._is_dangerous_path(path_obj):
                    if path_obj.is_file():
                        path_obj.unlink()
                        deleted_files += 1
                        print(f"      ✅ 删除文件")
                    elif path_obj.is_dir():
                        file_count = len(list(path_obj.rglob("*")))
                        shutil.rmtree(path_obj)
                        deleted_files += file_count
                        print(f"      ✅ 删除目录 ({file_count}个文件)")

                    processed_paths.append(str(path_obj))
                else:
                    print(f"      ⚠️  跳过危险路径")

            except Exception as e:
                print(f"      ❌ 删除失败: {e}")
                logger.error(f"清理聊天历史 {path_obj} 时出错: {e}")

        # 4. 清理数据库中的聊天记录
        print("   🗄️  清理数据库中的聊天记录...")
        db_cleaned = 0
        if workspace_storage.exists():
            db_pattern = str(workspace_storage / "*" / "state.vscdb")
            db_files = glob.glob(db_pattern)

            chat_keys = [
                '%chat%', '%conversation%', '%message%', '%dialog%',
                '%augment.chat%', '%augment.history%', '%augment.session%'
            ]

            for db_file in db_files:
                try:
                    conn = sqlite3.connect(db_file)
                    cursor = conn.cursor()

                    for key_pattern in chat_keys:
                        cursor.execute("DELETE FROM ItemTable WHERE key LIKE ?", (key_pattern,))
                        deleted_count = cursor.rowcount
                        if deleted_count > 0:
                            db_cleaned += deleted_count
                            print(f"      🗑️  清理 {key_pattern}: {deleted_count} 行")

                    conn.commit()
                    conn.close()

                except Exception as e:
                    logger.error(f"清理数据库 {db_file} 时出错: {e}")

        total_deleted = deleted_files + db_cleaned
        print(f"   ✅ 聊天历史清理完成！文件: {deleted_files}, 数据库: {db_cleaned}, 总计: {total_deleted}")

        result = {
            'editor_type': editor_type,
            'deleted_files': deleted_files,
            'deleted_db_rows': db_cleaned,
            'total_deleted': total_deleted,
            'processed_paths': processed_paths,
            'message': f'聊天历史清理完成。删除了 {deleted_files} 个文件和 {db_cleaned} 条数据库记录。'
        }

        return result
    
    def clean_extension_cache(self, editor_type: str) -> Dict:
        """清理扩展缓存数据"""
        print("\n🔄 正在清理扩展缓存...")
        print(f"   🎯 目标: 删除扩展缓存和临时文件")
        sys.stdout.flush()
        
        editor_path = self.get_editor_path(editor_type)
        
        # 扩展缓存路径
        cache_paths = [
            editor_path / "CachedExtensions",
            editor_path / "CachedExtensionVSIXs", 
            editor_path / "extensions" / ".obsolete",
            editor_path / "User" / "globalStorage" / "*cache*",
            editor_path / "GPUCache",
            editor_path / "DawnGraphiteCache"
        ]
        
        deleted_files = 0
        processed_paths = []
        
        print(f"   🔍 扫描 {len(cache_paths)} 个缓存位置...")
        
        for i, path_pattern in enumerate(cache_paths, 1):
            print(f"   📂 检查缓存 {i}/{len(cache_paths)}: {path_pattern.name}")
            
            if "*" in str(path_pattern):
                matching_paths = glob.glob(str(path_pattern))
                for match_path in matching_paths:
                    path_obj = Path(match_path)
                    if path_obj.exists():
                        try:
                            if not self._is_dangerous_path(path_obj):
                                if path_obj.is_file():
                                    path_obj.unlink()
                                    deleted_files += 1
                                elif path_obj.is_dir():
                                    file_count = len(list(path_obj.rglob("*")))
                                    shutil.rmtree(path_obj)
                                    deleted_files += file_count
                                processed_paths.append(str(path_obj))
                                print(f"      ✅ 清理: {path_obj.name}")
                            else:
                                print(f"      ⚠️  跳过危险路径: {path_obj}")
                        except Exception as e:
                            print(f"      ❌ 清理失败: {e}")
                            logger.error(f"清理缓存 {path_obj} 时出错: {e}")
            else:
                if path_pattern.exists():
                    try:
                        if path_pattern.is_file():
                            path_pattern.unlink()
                            deleted_files += 1
                        elif path_pattern.is_dir() and not self._is_dangerous_path(path_pattern):
                            file_count = len(list(path_pattern.rglob("*")))
                            shutil.rmtree(path_pattern)
                            deleted_files += file_count
                        processed_paths.append(str(path_pattern))
                        print(f"      ✅ 清理: {path_pattern.name}")
                    except Exception as e:
                        print(f"      ❌ 清理失败: {e}")
        
        print(f"   ✅ 扩展缓存清理完成！共删除 {deleted_files} 个文件")
        
        return {
            'editor_type': editor_type,
            'deleted_files': deleted_files,
            'processed_paths': processed_paths,
            'message': f'扩展缓存清理完成。删除了 {deleted_files} 个文件。'
        }
    
    def clean_logs_and_crashes(self, editor_type: str) -> Dict:
        """清理日志和崩溃转储"""
        print("\n🔄 正在清理日志和崩溃文件...")
        print(f"   🎯 目标: 删除所有日志和崩溃转储")
        
        editor_path = self.get_editor_path(editor_type)
        
        # 根据操作系统设置日志路径
        if self.current_os == 'windows':
            log_paths = [
                editor_path / "logs",
                editor_path / "crashes",
                editor_path / "User" / "logs", 
                self.home_path / "AppData" / "Local" / self.EDITORS[editor_type] / "logs",
                Path(os.environ.get('TEMP', '')) / f"{self.EDITORS[editor_type].lower()}-*"
            ]
        elif self.current_os == 'darwin':
            log_paths = [
                editor_path / "logs",
                editor_path / "crashes",
                editor_path / "User" / "logs",
                self.home_path / "Library" / "Logs" / self.EDITORS[editor_type],
                Path("/tmp") / f"{self.EDITORS[editor_type].lower()}-*"
            ]
        else:  # Linux
            log_paths = [
                editor_path / "logs",
                editor_path / "crashes", 
                editor_path / "User" / "logs",
                self.home_path / ".cache" / self.EDITORS[editor_type] / "logs",
                Path("/tmp") / f"{self.EDITORS[editor_type].lower()}-*"
            ]
        
        deleted_files = 0
        processed_paths = []
        
        for path_pattern in log_paths:
            if "*" in str(path_pattern):
                matching_paths = glob.glob(str(path_pattern))
                for match_path in matching_paths:
                    path_obj = Path(match_path)
                    if path_obj.exists():
                        try:
                            if path_obj.is_dir() and not self._is_dangerous_path(path_obj):
                                file_count = len(list(path_obj.rglob("*")))
                                shutil.rmtree(path_obj)
                                deleted_files += file_count
                                processed_paths.append(str(path_obj))
                                print(f"      ✅ 清理日志目录: {path_obj.name}")
                        except Exception as e:
                            print(f"      ❌ 清理失败: {e}")
            else:
                if path_pattern.exists() and not self._is_dangerous_path(path_pattern):
                    try:
                        file_count = len(list(path_pattern.rglob("*")))
                        shutil.rmtree(path_pattern)
                        deleted_files += file_count
                        processed_paths.append(str(path_pattern))
                        print(f"      ✅ 清理: {path_pattern.name}")
                    except Exception as e:
                        print(f"      ❌ 清理失败: {e}")
        
        print(f"   ✅ 日志清理完成！共删除 {deleted_files} 个文件")
        
        return {
            'editor_type': editor_type,
            'deleted_files': deleted_files,
            'processed_paths': processed_paths,
            'message': f'日志和崩溃文件清理完成。删除了 {deleted_files} 个文件。'
        }
    
    def clean_browser_cache(self, editor_type: str) -> Dict:
        """清理浏览器缓存"""
        print("\n🔄 正在清理浏览器缓存...")
        print(f"   🎯 目标: 删除WebView和渲染缓存")
        
        editor_path = self.get_editor_path(editor_type)
        
        browser_cache_paths = [
            editor_path / "GPUCache",
            editor_path / "DawnGraphiteCache",
            editor_path / "WebviewCache",
            editor_path / "CachedData",
            editor_path / "blob_storage",
            editor_path / "Local Storage",
            editor_path / "Session Storage"
        ]
        
        deleted_files = 0
        processed_paths = []
        
        for cache_path in browser_cache_paths:
            if cache_path.exists():
                try:
                    if cache_path.is_file():
                        cache_path.unlink()
                        deleted_files += 1
                    elif cache_path.is_dir() and not self._is_dangerous_path(cache_path):
                        file_count = len(list(cache_path.rglob("*")))
                        shutil.rmtree(cache_path)
                        deleted_files += file_count
                    processed_paths.append(str(cache_path))
                    print(f"      ✅ 清理: {cache_path.name}")
                except Exception as e:
                    print(f"      ❌ 清理失败: {e}")
        
        print(f"   ✅ 浏览器缓存清理完成！共删除 {deleted_files} 个文件")
        
        return {
            'editor_type': editor_type,
            'deleted_files': deleted_files,
            'processed_paths': processed_paths,
            'message': f'浏览器缓存清理完成。删除了 {deleted_files} 个文件。'
        }
    
    def clean_user_settings(self, editor_type: str) -> Dict:
        """清理用户设置中的AI相关配置"""
        print("\n🔄 正在清理用户设置...")
        print(f"   🎯 目标: 清理AI和augment相关设置")
        
        editor_path = self.get_editor_path(editor_type)
        settings_path = editor_path / "User" / "settings.json"
        keybindings_path = editor_path / "User" / "keybindings.json"
        
        cleaned_items = 0
        backup_files = []
        
        # 清理settings.json
        if settings_path.exists():
            try:
                backup_path = settings_path.with_suffix('.json.settings_bak')
                shutil.copy2(settings_path, backup_path)
                backup_files.append(str(backup_path))
                
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                # 需要清理的设置项
                ai_related_keys = [
                    'augment', 'copilot', 'tabnine', 'codeium', 'continue',
                    'telemetry.enableTelemetry', 'telemetry.enableCrashReporter'
                ]
                
                for key in list(settings.keys()):
                    if any(ai_key in key.lower() for ai_key in ai_related_keys):
                        del settings[key]
                        cleaned_items += 1
                        print(f"      🗑️  清理设置项: {key}")
                
                with open(settings_path, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=2, ensure_ascii=False)
                
            except Exception as e:
                print(f"      ❌ 清理settings.json失败: {e}")
        
        # 清理keybindings.json
        if keybindings_path.exists():
            try:
                backup_path = keybindings_path.with_suffix('.json.keybindings_bak')
                shutil.copy2(keybindings_path, backup_path)
                backup_files.append(str(backup_path))
                
                with open(keybindings_path, 'r', encoding='utf-8') as f:
                    keybindings = json.load(f)
                
                # 过滤augment相关的快捷键
                original_count = len(keybindings)
                keybindings = [kb for kb in keybindings 
                             if not any(ai_key in str(kb).lower() for ai_key in ['augment', 'copilot', 'ai'])]
                cleaned_items += original_count - len(keybindings)
                
                with open(keybindings_path, 'w', encoding='utf-8') as f:
                    json.dump(keybindings, f, indent=2, ensure_ascii=False)
                    
            except Exception as e:
                print(f"      ❌ 清理keybindings.json失败: {e}")
        
        print(f"   ✅ 用户设置清理完成！清理了 {cleaned_items} 个配置项")
        
        return {
            'editor_type': editor_type,
            'cleaned_items': cleaned_items,
            'backup_files': backup_files,
            'message': f'用户设置清理完成。清理了 {cleaned_items} 个配置项。'
        }
    
    def clean_network_cache(self, editor_type: str) -> Dict:
        """清理网络缓存"""
        print("\n🔄 正在清理网络缓存...")
        print(f"   🎯 目标: 删除HTTP缓存和网络数据")
        
        editor_path = self.get_editor_path(editor_type)
        
        # 根据操作系统设置网络缓存路径
        if self.current_os == 'windows':
            network_cache_paths = [
                editor_path / "HTTPCache",
                editor_path / "Code Cache",
                editor_path / "Network Persistent State",
                editor_path / "TransportSecurity",
                self.home_path / "AppData" / "Local" / self.EDITORS[editor_type] / "http-cache"
            ]
        elif self.current_os == 'darwin':
            network_cache_paths = [
                editor_path / "HTTPCache",
                editor_path / "Code Cache",
                editor_path / "Network Persistent State",
                editor_path / "TransportSecurity",
                self.home_path / "Library" / "Caches" / self.EDITORS[editor_type] / "http-cache"
            ]
        else:  # Linux
            network_cache_paths = [
                editor_path / "HTTPCache",
                editor_path / "Code Cache",
                editor_path / "Network Persistent State",
                editor_path / "TransportSecurity",
                self.home_path / ".cache" / self.EDITORS[editor_type] / "http-cache"
            ]
        
        deleted_files = 0
        processed_paths = []
        
        for cache_path in network_cache_paths:
            if cache_path.exists():
                try:
                    if cache_path.is_file():
                        cache_path.unlink()
                        deleted_files += 1
                    elif cache_path.is_dir() and not self._is_dangerous_path(cache_path):
                        file_count = len(list(cache_path.rglob("*")))
                        shutil.rmtree(cache_path)
                        deleted_files += file_count
                    processed_paths.append(str(cache_path))
                    print(f"      ✅ 清理: {cache_path.name}")
                except Exception as e:
                    print(f"      ❌ 清理失败: {e}")
        
        print(f"   ✅ 网络缓存清理完成！共删除 {deleted_files} 个文件")
        
        return {
            'editor_type': editor_type,
            'deleted_files': deleted_files,
            'processed_paths': processed_paths,
            'message': f'网络缓存清理完成。删除了 {deleted_files} 个文件。'
        }
    
    def clean_temporary_files(self, editor_type: str) -> Dict:
        """清理临时文件 (跨平台)"""
        print("\n🔄 正在清理临时文件...")
        print(f"   🎯 目标: 删除临时文件和锁文件")
        
        # 根据操作系统设置临时文件路径
        if self.current_os == 'windows':
            temp_base = Path(os.environ.get('TEMP', self.home_path / 'AppData' / 'Local' / 'Temp'))
            temp_paths = [
                temp_base / f"*{self.EDITORS[editor_type].lower()}*",
                temp_base / "*vscode*",
                temp_base / "*augment*",
                self.home_path / "AppData" / "Local" / self.EDITORS[editor_type],
                Path(os.environ.get('LOCALAPPDATA', self.home_path / 'AppData' / 'Local')) / self.EDITORS[editor_type]
            ]
        elif self.current_os == 'darwin':
            temp_paths = [
                Path("/tmp") / f"*{self.EDITORS[editor_type].lower()}*",
                Path("/tmp") / "*vscode*", 
                Path("/tmp") / "*augment*",
                self.home_path / "Library" / "Caches" / self.EDITORS[editor_type],
                Path("/var/tmp") / f"*{self.EDITORS[editor_type].lower()}*"
            ]
        else:  # Linux
            temp_paths = [
                Path("/tmp") / f"*{self.EDITORS[editor_type].lower()}*",
                Path("/tmp") / "*vscode*",
                Path("/tmp") / "*augment*",
                self.home_path / ".cache" / self.EDITORS[editor_type],
                Path("/var/tmp") / f"*{self.EDITORS[editor_type].lower()}*"
            ]
        
        deleted_files = 0
        processed_paths = []
        
        for path_pattern in temp_paths:
            if "*" in str(path_pattern):
                try:
                    matching_paths = glob.glob(str(path_pattern))
                    for match_path in matching_paths:
                        path_obj = Path(match_path)
                        if path_obj.exists() and not self._is_dangerous_path(path_obj):
                            try:
                                if path_obj.is_file():
                                    path_obj.unlink()
                                    deleted_files += 1
                                elif path_obj.is_dir():
                                    file_count = len(list(path_obj.rglob("*")))
                                    shutil.rmtree(path_obj)
                                    deleted_files += file_count
                                processed_paths.append(str(path_obj))
                                print(f"      ✅ 清理临时文件: {path_obj.name}")
                            except Exception as e:
                                print(f"      ❌ 清理失败: {e}")
                except Exception as e:
                    print(f"      ❌ 扫描失败: {e}")
            else:
                if path_pattern.exists() and not self._is_dangerous_path(path_pattern):
                    try:
                        if path_pattern.is_file():
                            path_pattern.unlink()
                            deleted_files += 1
                        elif path_pattern.is_dir() and not self._is_dangerous_path(path_pattern):
                            file_count = len(list(path_pattern.rglob("*")))
                            shutil.rmtree(path_pattern)
                            deleted_files += file_count
                        processed_paths.append(str(path_pattern))
                        print(f"      ✅ 清理: {path_pattern.name}")
                    except Exception as e:
                        print(f"      ❌ 清理失败: {e}")
        
        print(f"   ✅ 临时文件清理完成！共删除 {deleted_files} 个文件")
        
        return {
            'editor_type': editor_type,
            'deleted_files': deleted_files,
            'processed_paths': processed_paths,
            'message': f'临时文件清理完成。删除了 {deleted_files} 个文件。'
        }
    
    def clean_augment_deep(self, editor_type: str) -> Dict:
        """深度清理Augment相关数据 - 基于JS分析发现"""
        print("\n🔄 正在执行Augment深度清理...")
        print(f"   🎯 目标: 基于JS分析的深度数据清理")
        
        editor_path = self.get_editor_path(editor_type)
        
        # 基于分析发现的关键清理目标
        deep_clean_patterns = [
            # 存储相关
            "**/*augment*",
            "**/*telemetry*", 
            "**/*analytics*",
            "**/*tracking*",
            "**/*session*",
            "**/*machine*",
            "**/*device*",
            "**/*client*",
            
            # 缓存相关
            "**/Code Cache/**",
            "**/GPUCache/**", 
            "**/DawnGraphiteCache/**",
            "**/CachedData/**",
            "**/blob_storage/**",
            "**/Local Storage/**",
            "**/Session Storage/**",
            "**/IndexedDB/**",
            
            # 网络缓存
            "**/HTTPCache/**",
            "**/NetworkPersistentState/**",
            "**/TransportSecurity/**",
            
            # 日志和调试
            "**/logs/**/*.log",
            "**/crashes/**",
            "**/*.sqlite",
            "**/*.sqlite3", 
            "**/*.db",
            "**/debugging/**"
        ]
        
        deleted_files = 0
        processed_patterns = []
        
        print(f"   🔍 扫描 {len(deep_clean_patterns)} 个深度模式...")
        
        for i, pattern in enumerate(deep_clean_patterns, 1):
            print(f"   📂 清理模式 {i}/{len(deep_clean_patterns)}: {pattern}")
            
            try:
                # 正确处理glob模式
                if pattern.startswith("**/"):
                    # 对于 **/ 开头的模式，使用rglob
                    clean_pattern = pattern[3:]  # 移除 **/
                    matching_paths = list(editor_path.rglob(clean_pattern))
                else:
                    # 对于普通模式，使用glob
                    matching_paths = list(editor_path.glob(pattern))
                
                if matching_paths:
                    print(f"      🎯 找到 {len(matching_paths)} 个匹配项")
                    
                    for path_obj in matching_paths:
                        try:
                            if path_obj.is_file():
                                path_obj.unlink()
                                deleted_files += 1
                                print(f"         🗑️  删除文件: {path_obj.name}")
                            elif path_obj.is_dir() and not self._is_dangerous_path(path_obj):
                                file_count = len(list(path_obj.rglob("*")))
                                shutil.rmtree(path_obj)
                                deleted_files += file_count
                                print(f"         🗑️  删除目录: {path_obj.name} ({file_count}个文件)")
                        except Exception as e:
                            print(f"         ❌ 删除失败: {e}")
                    
                    processed_patterns.append({
                        'pattern': pattern,
                        'matches': len(matching_paths),
                        'status': 'processed'
                    })
                else:
                    print(f"      ⚪ 无匹配文件")
                    
            except Exception as e:
                print(f"      ❌ 处理模式失败: {e}")
                processed_patterns.append({
                    'pattern': pattern,
                    'error': str(e),
                    'status': 'error'
                })
        
        print(f"   ✅ Augment深度清理完成！共删除 {deleted_files} 个文件")
        
        return {
            'editor_type': editor_type,
            'deleted_files': deleted_files,
            'processed_patterns': processed_patterns,
            'pattern_count': len(deep_clean_patterns),
            'message': f'Augment深度清理完成。删除了 {deleted_files} 个文件。'
        }
    
    def clean_analytics_data(self, editor_type: str) -> Dict:
        """清理分析和遥测数据 - 基于JS分析"""
        print("\n🔄 正在清理分析数据...")
        print(f"   🎯 目标: 删除所有analytics和遥测数据")
        
        editor_path = self.get_editor_path(editor_type)
        workspace_storage_path = editor_path / "User" / "workspaceStorage"
        
        deleted_files = 0
        cleaned_databases = 0
        
        # 深度清理数据库中的分析数据
        if workspace_storage_path.exists():
            db_pattern = str(workspace_storage_path / "*" / "state.vscdb")
            db_files = glob.glob(db_pattern)
            
            # 基于JS分析发现的关键词
            analytics_keys = [
                '%analytics%', '%telemetry%', '%tracking%', '%metrics%',
                '%sessionId%', '%deviceId%', '%machineId%', '%clientId%',
                '%fingerprint%', '%userAgent%', '%platform%', '%augment%',
                '%AugmentExtension%', '%vscode-augment%', '%Fix with Augment%'
            ]
            
            for db_file in db_files:
                try:
                    conn = sqlite3.connect(db_file)
                    cursor = conn.cursor()
                    
                    for key_pattern in analytics_keys:
                        cursor.execute("DELETE FROM ItemTable WHERE key LIKE ?", (key_pattern,))
                        deleted_count = cursor.rowcount
                        if deleted_count > 0:
                            cleaned_databases += deleted_count
                            print(f"      🗑️  清理 {key_pattern}: {deleted_count} 行")
                    
                    conn.commit()
                    conn.close()
                    
                except Exception as e:
                    print(f"      ❌ 数据库清理失败: {e}")
        
        print(f"   ✅ 分析数据清理完成！数据库清理: {cleaned_databases} 行")
        
        return {
            'editor_type': editor_type,
            'cleaned_database_rows': cleaned_databases,
            'message': f'分析数据清理完成。清理了 {cleaned_databases} 行数据。'
        }
    
    def clean_vscode_cdn_cache(self, editor_type: str) -> Dict:
        """清理VSCode CDN缓存"""
        print("\n🔄 正在清理VSCode CDN缓存...")
        print(f"   🎯 目标: 清理*.vscode-cdn.net相关缓存")
        
        editor_path = self.get_editor_path(editor_type)
        
        # 根据操作系统设置CDN缓存路径
        if self.current_os == 'windows':
            cdn_cache_paths = [
                editor_path / "CachedData",
                editor_path / "Code Cache" / "js",
                editor_path / "Code Cache" / "wasm", 
                self.home_path / "AppData" / "Local" / self.EDITORS[editor_type] / "cdn-cache",
                editor_path / "User" / "globalStorage" / "*cdn*",
                editor_path / "User" / "globalStorage" / "*vscode-cdn*"
            ]
        elif self.current_os == 'darwin':
            cdn_cache_paths = [
                editor_path / "CachedData",
                editor_path / "Code Cache" / "js",
                editor_path / "Code Cache" / "wasm", 
                self.home_path / "Library" / "Caches" / self.EDITORS[editor_type] / "cdn-cache",
                editor_path / "User" / "globalStorage" / "*cdn*",
                editor_path / "User" / "globalStorage" / "*vscode-cdn*"
            ]
        else:  # Linux
            cdn_cache_paths = [
                editor_path / "CachedData",
                editor_path / "Code Cache" / "js",
                editor_path / "Code Cache" / "wasm", 
                self.home_path / ".cache" / self.EDITORS[editor_type] / "cdn-cache",
                editor_path / "User" / "globalStorage" / "*cdn*",
                editor_path / "User" / "globalStorage" / "*vscode-cdn*"
            ]
        
        deleted_files = 0
        processed_paths = []
        
        print(f"   🔍 扫描 {len(cdn_cache_paths)} 个CDN缓存位置...")
        
        for i, path_pattern in enumerate(cdn_cache_paths, 1):
            print(f"   📂 检查CDN缓存 {i}/{len(cdn_cache_paths)}: {path_pattern.name}")
            
            if "*" in str(path_pattern):
                try:
                    matching_paths = list(path_pattern.parent.glob(path_pattern.name))
                    for path_obj in matching_paths:
                        if path_obj.exists() and not self._is_dangerous_path(path_obj):
                            try:
                                if path_obj.is_file():
                                    path_obj.unlink()
                                    deleted_files += 1
                                elif path_obj.is_dir():
                                    file_count = len(list(path_obj.rglob("*")))
                                    shutil.rmtree(path_obj)
                                    deleted_files += file_count
                                processed_paths.append(str(path_obj))
                                print(f"      ✅ 清理CDN缓存: {path_obj.name}")
                            except Exception as e:
                                print(f"      ❌ 清理失败: {e}")
                except Exception as e:
                    print(f"      ❌ 扫描失败: {e}")
            else:
                if path_pattern.exists() and not self._is_dangerous_path(path_pattern):
                    try:
                        if path_pattern.is_file():
                            path_pattern.unlink()
                            deleted_files += 1
                        elif path_pattern.is_dir():
                            file_count = len(list(path_pattern.rglob("*")))
                            shutil.rmtree(path_pattern)
                            deleted_files += file_count
                        processed_paths.append(str(path_pattern))
                        print(f"      ✅ 清理: {path_pattern.name}")
                    except Exception as e:
                        print(f"      ❌ 清理失败: {e}")
        
        print(f"   ✅ CDN缓存清理完成！共删除 {deleted_files} 个文件")
        
        return {
            'editor_type': editor_type,
            'deleted_files': deleted_files,
            'processed_paths': processed_paths,
            'message': f'VSCode CDN缓存清理完成。删除了 {deleted_files} 个文件。'
        }
    
    def _is_dangerous_path(self, path: Path) -> bool:
        """检查是否是危险路径 (跨平台) - 增强版"""
        path_str = str(path).lower()

        # 从配置文件加载危险路径模式
        config_dangerous = self.config.get('safety', {}).get('dangerous_path_patterns', [])

        # 默认危险路径 - 只保护系统目录和用户主目录本身，不保护子目录
        if self.current_os == 'windows':
            dangerous_paths = [
                'c:\\windows', 'c:\\program files', 'c:\\program files (x86)',
                'c:\\system', 'c:\\boot', 'c:\\recovery', 'c:\\'
            ]
            # 只保护用户主目录本身，不保护子目录
            home_str = str(self.home_path).lower()
            if path_str == home_str:
                return True
        elif self.current_os == 'darwin':
            dangerous_paths = [
                '/system', '/usr', '/bin', '/sbin', '/library/system',
                '/boot', '/etc', '/var/root', '/'
            ]
            # 只保护用户主目录本身，不保护子目录
            home_str = str(self.home_path).lower()
            if path_str == home_str:
                return True
        else:  # Linux
            dangerous_paths = [
                '/usr', '/bin', '/sbin', '/boot', '/etc', '/sys', '/proc',
                '/root', '/var/lib', '/opt', '/', '/home'
            ]
            # 只保护用户主目录本身，不保护子目录
            home_str = str(self.home_path).lower()
            if path_str == home_str:
                return True

        # 合并配置文件中的危险路径
        dangerous_paths.extend(config_dangerous)

        # 检查是否匹配危险路径
        for danger in dangerous_paths:
            danger_lower = danger.lower()
            if path_str == danger_lower or path_str.startswith(danger_lower + os.sep):
                return True

        return False

    def _check_write_permission(self, path: Path) -> bool:
        """检查是否有写权限"""
        try:
            if path.exists():
                return os.access(path, os.W_OK)
            else:
                # 检查父目录权限
                parent = path.parent
                return parent.exists() and os.access(parent, os.W_OK)
        except Exception as e:
            logger.warning(f"权限检查失败: {path}, {e}")
            return False

    def _require_admin_check(self) -> bool:
        """检查是否需要管理员权限"""
        try:
            if self.current_os == 'windows':
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                return os.geteuid() == 0
        except:
            return False
    
    def reinstall_plugin(self, editor_type: str, plugin_id: str = None) -> Dict:
        """重新安装插件 - 实际执行版本"""
        print("\n🔄 正在重新安装插件...")
        sys.stdout.flush()
        
        logger.info(f"开始重新安装插件流程: {editor_type}")
        
        # 常见的AI代码助手插件 - 使用正确的完整ID
        target_plugins = [
            'continue.continue',  # Continue AI Assistant (已验证)
            'tabnine.tabnine-vscode',  # TabNine AI (已验证)
            'GitHub.copilot',  # GitHub Copilot (正确格式)
            'Codeium.codeium',  # Codeium AI (正确格式) 
            'ms-vscode.vscode-typescript-next',  # TypeScript助手
            # 注意：某些AI插件可能需要特定权限或不在公共市场
        ]
        
        if plugin_id:
            target_plugins = [plugin_id]
            print(f"   🎯 指定插件: {plugin_id}")
        else:
            print(f"   🎯 尝试安装常见AI插件: {len(target_plugins)} 个")
        
        editor_commands = {
            'vscode': 'code',
            'cursor': 'cursor', 
            'vscodium': 'codium',
            'code-oss': 'code-oss',
            'vscode-insiders': 'code-insiders',
            'theia': 'theia',
            'openvscode': 'openvscode-server',
            'gitpod': 'gitpod'
        }
        
        command = editor_commands.get(editor_type)
        if not command:
            print(f"   ❌ 不支持的编辑器类型: {editor_type}")
            return {
                'editor_type': editor_type,
                'status': 'error',
                'error': f'不支持的编辑器类型: {editor_type}'
            }
        
        print(f"   🔧 使用命令: {command}")
        
        installed_plugins = []
        failed_plugins = []
        
        for i, plugin in enumerate(target_plugins, 1):
            print(f"   📦 安装插件 {i}/{len(target_plugins)}: {plugin}")
            
            try:
                logger.info(f"尝试安装插件: {plugin}")
                
                # 执行插件安装命令
                result = subprocess.run(
                    [command, '--install-extension', plugin],
                    capture_output=True,
                    text=True,
                    timeout=60  # 60秒超时
                )
                
                if result.returncode == 0:
                    print(f"      ✅ 安装成功")
                    installed_plugins.append({
                        'plugin_id': plugin,
                        'status': 'success',
                        'output': result.stdout.strip()
                    })
                    logger.info(f"插件 {plugin} 安装成功")
                else:
                    print(f"      ❌ 安装失败: {result.stderr.strip()[:50]}...")
                    failed_plugins.append({
                        'plugin_id': plugin,
                        'status': 'failed',
                        'error': result.stderr.strip()
                    })
                    logger.error(f"插件 {plugin} 安装失败: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                print(f"      ⏰ 安装超时")
                failed_plugins.append({
                    'plugin_id': plugin,
                    'status': 'timeout',
                    'error': '安装超时'
                })
                logger.error(f"插件 {plugin} 安装超时")
                
            except Exception as e:
                print(f"      ❌ 安装异常: {e}")
                failed_plugins.append({
                    'plugin_id': plugin,
                    'status': 'error', 
                    'error': str(e)
                })
                logger.error(f"插件 {plugin} 安装异常: {e}")
        
        print(f"   ✅ 插件安装完成！成功: {len(installed_plugins)}, 失败: {len(failed_plugins)}")
        
        result = {
            'editor_type': editor_type,
            'action': 'reinstall_plugin',
            'status': 'completed',
            'installed_plugins': installed_plugins,
            'failed_plugins': failed_plugins,
            'total_attempted': len(target_plugins),
            'total_installed': len(installed_plugins),
            'total_failed': len(failed_plugins),
            'message': f'插件安装完成。成功: {len(installed_plugins)}, 失败: {len(failed_plugins)}'
        }
        
        logger.info(f"插件重安装流程完成: 成功{len(installed_plugins)}个, 失败{len(failed_plugins)}个")
        return result
    
    def uninstall_plugin(self, editor_type: str, plugin_id: str = None) -> Dict:
        """卸载插件"""
        logger.info(f"开始卸载插件流程: {editor_type}")
        
        # 默认的AI代码助手插件列表 - 与安装列表保持一致
        target_plugins = [
            'continue.continue',  # Continue AI Assistant (已验证)
            'tabnine.tabnine-vscode',  # TabNine AI (已验证)
            'GitHub.copilot',  # GitHub Copilot (正确格式)
            'Codeium.codeium',  # Codeium AI (正确格式)
            'ms-vscode.vscode-typescript-next',  # TypeScript助手
        ]
        
        if plugin_id:
            target_plugins = [plugin_id]
        
        editor_commands = {
            'vscode': 'code',
            'cursor': 'cursor', 
            'vscodium': 'codium',
            'code-oss': 'code-oss',
            'vscode-insiders': 'code-insiders',
            'theia': 'theia',
            'openvscode': 'openvscode-server',
            'gitpod': 'gitpod'
        }
        
        command = editor_commands.get(editor_type)
        if not command:
            return {
                'editor_type': editor_type,
                'status': 'error',
                'error': f'不支持的编辑器类型: {editor_type}'
            }
        
        uninstalled_plugins = []
        failed_plugins = []
        
        for plugin in target_plugins:
            try:
                logger.info(f"尝试卸载插件: {plugin}")
                
                # 执行插件卸载命令
                result = subprocess.run(
                    [command, '--uninstall-extension', plugin],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    uninstalled_plugins.append({
                        'plugin_id': plugin,
                        'status': 'success',
                        'output': result.stdout.strip()
                    })
                    logger.info(f"插件 {plugin} 卸载成功")
                else:
                    failed_plugins.append({
                        'plugin_id': plugin,
                        'status': 'failed',
                        'error': result.stderr.strip()
                    })
                    logger.error(f"插件 {plugin} 卸载失败: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                failed_plugins.append({
                    'plugin_id': plugin,
                    'status': 'timeout',
                    'error': '卸载超时'
                })
                logger.error(f"插件 {plugin} 卸载超时")
                
            except Exception as e:
                failed_plugins.append({
                    'plugin_id': plugin,
                    'status': 'error', 
                    'error': str(e)
                })
                logger.error(f"插件 {plugin} 卸载异常: {e}")
        
        result = {
            'editor_type': editor_type,
            'action': 'uninstall_plugin',
            'status': 'completed',
            'uninstalled_plugins': uninstalled_plugins,
            'failed_plugins': failed_plugins,
            'total_attempted': len(target_plugins),
            'total_uninstalled': len(uninstalled_plugins),
            'total_failed': len(failed_plugins),
            'message': f'插件卸载完成。成功: {len(uninstalled_plugins)}, 失败: {len(failed_plugins)}'
        }
        
        logger.info(f"插件卸载流程完成: 成功{len(uninstalled_plugins)}个, 失败{len(failed_plugins)}个")
        return result
    
    def list_installed_extensions(self, editor_type: str) -> Dict:
        """列出已安装的扩展"""
        logger.info(f"获取已安装扩展列表: {editor_type}")
        
        editor_commands = {
            'vscode': 'code',
            'cursor': 'cursor', 
            'vscodium': 'codium',
            'code-oss': 'code-oss',
            'vscode-insiders': 'code-insiders',
            'theia': 'theia',
            'openvscode': 'openvscode-server',
            'gitpod': 'gitpod'
        }
        
        command = editor_commands.get(editor_type)
        if not command:
            return {
                'editor_type': editor_type,
                'status': 'error',
                'error': f'不支持的编辑器类型: {editor_type}'
            }
        
        try:
            result = subprocess.run(
                [command, '--list-extensions'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                extensions = result.stdout.strip().split('\n') if result.stdout.strip() else []
                extensions = [ext.strip() for ext in extensions if ext.strip()]
                
                # 过滤出可能相关的插件
                relevant_extensions = []
                augment_related = []
                
                for ext in extensions:
                    if any(keyword in ext.lower() for keyword in ['augment', 'ai', 'copilot', 'codeium', 'tabnine', 'continue']):
                        augment_related.append(ext)
                    relevant_extensions.append(ext)
                
                return {
                    'editor_type': editor_type,
                    'status': 'success',
                    'total_extensions': len(extensions),
                    'all_extensions': extensions,
                    'augment_related_extensions': augment_related,
                    'message': f'找到 {len(extensions)} 个已安装扩展，其中 {len(augment_related)} 个可能相关'
                }
            else:
                return {
                    'editor_type': editor_type,
                    'status': 'error',
                    'error': result.stderr.strip() or '获取扩展列表失败'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'editor_type': editor_type,
                'status': 'timeout',
                'error': '获取扩展列表超时'
            }
        except Exception as e:
            return {
                'editor_type': editor_type,
                'status': 'error',
                'error': str(e)
            }
    
    def install_vsix_plugin(self, editor_type: str, vsix_path: str = None) -> Dict:
        """安装VSIX插件文件"""
        logger.info(f"开始安装VSIX插件: {editor_type}")
        
        # 默认的内置VSIX文件路径
        default_vsix = "augment-plugin-embedded.vsix"
        vsix_file = vsix_path if vsix_path else default_vsix
        
        # 检查VSIX文件是否存在
        if not Path(vsix_file).exists():
            return {
                'editor_type': editor_type,
                'status': 'error',
                'error': f'VSIX文件不存在: {vsix_file}'
            }
        
        editor_commands = {
            'vscode': 'code',
            'cursor': 'cursor', 
            'vscodium': 'codium',
            'code-oss': 'code-oss',
            'vscode-insiders': 'code-insiders',
            'theia': 'theia',
            'openvscode': 'openvscode-server',
            'gitpod': 'gitpod'
        }
        
        command = editor_commands.get(editor_type)
        if not command:
            return {
                'editor_type': editor_type,
                'status': 'error',
                'error': f'不支持的编辑器类型: {editor_type}'
            }
        
        try:
            logger.info(f"安装VSIX文件: {vsix_file}")
            
            result = subprocess.run(
                [command, '--install-extension', vsix_file],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return {
                    'editor_type': editor_type,
                    'status': 'success',
                    'vsix_file': vsix_file,
                    'output': result.stdout.strip(),
                    'message': f'VSIX插件安装成功: {vsix_file}'
                }
            else:
                return {
                    'editor_type': editor_type,
                    'status': 'failed',
                    'vsix_file': vsix_file,
                    'error': result.stderr.strip(),
                    'message': f'VSIX插件安装失败: {vsix_file}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'editor_type': editor_type,
                'status': 'timeout',
                'vsix_file': vsix_file,
                'error': 'VSIX安装超时'
            }
        except Exception as e:
            return {
                'editor_type': editor_type,
                'status': 'error',
                'vsix_file': vsix_file,
                'error': str(e)
            }
    
    def force_exit_app(self, editor_type: str) -> Dict:
        """强制退出应用程序"""
        logger.info(f"强制退出应用程序: {editor_type}")
        
        app_names = {
            'vscode': ['Visual Studio Code', 'Code'],
            'cursor': ['Cursor'], 
            'vscodium': ['VSCodium'],
            'code-oss': ['Code - OSS'],
            'vscode-insiders': ['Visual Studio Code - Insiders'],
            'theia': ['Theia'],
            'openvscode': ['OpenVSCode Server'],
            'gitpod': ['Gitpod']
        }
        
        names = app_names.get(editor_type, [])
        if not names:
            return {
                'editor_type': editor_type,
                'status': 'error',
                'error': f'不支持的编辑器类型: {editor_type}'
            }
        
        killed_processes = []
        failed_processes = []
        
        for app_name in names:
            try:
                # 根据操作系统强制终止进程
                if self.current_os == 'windows':
                    # Windows: 强制终止
                    result = subprocess.run(
                        ['taskkill', '/F', '/IM', f'{app_name}.exe'],
                        capture_output=True,
                        text=True
                    )
                elif self.current_os == 'darwin':
                    # macOS: 强制杀死
                    result = subprocess.run(
                        ['killall', '-9', app_name],
                        capture_output=True,
                        text=True
                    )
                else:
                    # Linux: 强制杀死
                    result = subprocess.run(
                        ['pkill', '-9', '-f', app_name],
                        capture_output=True,
                        text=True
                    )
                
                if result.returncode == 0:
                    killed_processes.append(app_name)
                    logger.info(f"成功终止进程: {app_name}")
                else:
                    # 进程不存在也算正常
                    if "No matching processes" in result.stderr:
                        killed_processes.append(f"{app_name} (未运行)")
                    else:
                        failed_processes.append({
                            'app_name': app_name,
                            'error': result.stderr.strip()
                        })
                        
            except Exception as e:
                failed_processes.append({
                    'app_name': app_name,
                    'error': str(e)
                })
                logger.error(f"终止进程 {app_name} 时出错: {e}")
        
        return {
            'editor_type': editor_type,
            'status': 'completed',
            'killed_processes': killed_processes,
            'failed_processes': failed_processes,
            'message': f'进程终止完成。成功: {len(killed_processes)}, 失败: {len(failed_processes)}'
        }
    
    def shell_execute(self, command: str, timeout: int = 30) -> Dict:
        """执行系统命令"""
        logger.info(f"执行系统命令: {command}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                'command': command,
                'status': 'completed',
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'success': result.returncode == 0
            }
            
        except subprocess.TimeoutExpired:
            return {
                'command': command,
                'status': 'timeout',
                'error': f'命令执行超时 ({timeout}秒)'
            }
        except Exception as e:
            return {
                'command': command,
                'status': 'error',
                'error': str(e)
            }
    
    def get_supported_operations(self) -> List[str]:
        """获取支持的操作列表"""
        return [
            'modify_telemetry_ids',
            'clean_database', 
            'clean_workspace',
            'clear_chat_history',
            'clean_extension_cache',
            'clean_logs_and_crashes',
            'clean_browser_cache',
            'clean_user_settings',
            'clean_network_cache',
            'clean_temporary_files',
            'clean_augment_deep',
            'clean_analytics_data',
            'clean_vscode_cdn_cache',
            'reinstall_plugin',
            'uninstall_plugin',
            'list_installed_extensions',
            'install_vsix_plugin',
            'force_exit_app',
            'shell_execute',
            'kill_editor_processes'
        ]
    
    # 文件系统操作功能
    def open_path(self, path: str) -> Dict:
        """打开文件路径"""
        try:
            path_obj = Path(path).expanduser().resolve()
            
            if path_obj.exists():
                # 根据操作系统选择打开命令
                if self.current_os == 'windows':
                    result = subprocess.run(['start', str(path_obj)], shell=True,
                                           capture_output=True, text=True)
                elif self.current_os == 'darwin':
                    result = subprocess.run(['open', str(path_obj)], 
                                           capture_output=True, text=True)
                else:  # Linux
                    result = subprocess.run(['xdg-open', str(path_obj)], 
                                           capture_output=True, text=True)
                
                if result.returncode == 0:
                    return {
                        'path': str(path_obj),
                        'status': 'success',
                        'message': f'成功打开路径: {path_obj}'
                    }
                else:
                    return {
                        'path': str(path_obj),
                        'status': 'failed',
                        'error': result.stderr.strip()
                    }
            else:
                return {
                    'path': str(path_obj),
                    'status': 'not_found',
                    'error': '路径不存在'
                }
                
        except Exception as e:
            return {
                'path': path,
                'status': 'error',
                'error': str(e)
            }
    
    def exists(self, path: str) -> Dict:
        """检查文件是否存在"""
        try:
            path_obj = Path(path).expanduser().resolve()
            
            return {
                'path': str(path_obj),
                'exists': path_obj.exists(),
                'is_file': path_obj.is_file() if path_obj.exists() else False,
                'is_directory': path_obj.is_dir() if path_obj.exists() else False,
                'size': path_obj.stat().st_size if path_obj.exists() and path_obj.is_file() else None
            }
            
        except Exception as e:
            return {
                'path': path,
                'error': str(e),
                'exists': False
            }
    
    def read_dir(self, path: str, pattern: str = "*") -> Dict:
        """读取目录内容"""
        try:
            path_obj = Path(path).expanduser().resolve()
            
            if not path_obj.exists():
                return {
                    'path': str(path_obj),
                    'status': 'not_found',
                    'error': '目录不存在'
                }
            
            if not path_obj.is_dir():
                return {
                    'path': str(path_obj),
                    'status': 'not_directory',
                    'error': '路径不是目录'
                }
            
            # 使用glob模式匹配文件
            files = []
            directories = []
            
            for item in path_obj.glob(pattern):
                item_info = {
                    'name': item.name,
                    'path': str(item),
                    'size': item.stat().st_size if item.is_file() else None,
                    'modified': item.stat().st_mtime
                }
                
                if item.is_file():
                    files.append(item_info)
                elif item.is_dir():
                    directories.append(item_info)
            
            return {
                'path': str(path_obj),
                'status': 'success',
                'pattern': pattern,
                'files': files,
                'directories': directories,
                'total_files': len(files),
                'total_directories': len(directories)
            }
            
        except Exception as e:
            return {
                'path': path,
                'status': 'error',
                'error': str(e)
            }
    
    def copy_file(self, source: str, destination: str) -> Dict:
        """文件复制操作"""
        try:
            source_path = Path(source).expanduser().resolve()
            dest_path = Path(destination).expanduser().resolve()
            
            if not source_path.exists():
                return {
                    'source': str(source_path),
                    'destination': str(dest_path),
                    'status': 'source_not_found',
                    'error': '源文件不存在'
                }
            
            # 如果目标是目录，则在目录中创建同名文件
            if dest_path.exists() and dest_path.is_dir():
                dest_path = dest_path / source_path.name
            
            # 创建目标目录（如果不存在）
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            if source_path.is_file():
                shutil.copy2(source_path, dest_path)
            elif source_path.is_dir():
                shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
            
            return {
                'source': str(source_path),
                'destination': str(dest_path),
                'status': 'success',
                'message': f'成功复制: {source_path.name}'
            }
            
        except Exception as e:
            return {
                'source': source,
                'destination': destination,
                'status': 'error',
                'error': str(e)
            }
    
    def remove(self, path: str, force: bool = False) -> Dict:
        """文件删除操作"""
        try:
            path_obj = Path(path).expanduser().resolve()
            
            if not path_obj.exists():
                return {
                    'path': str(path_obj),
                    'status': 'not_found',
                    'error': '文件或目录不存在'
                }
            
            # 安全检查 - 避免删除重要系统目录
            dangerous_paths = ['/usr', '/bin', '/sbin', '/boot', '/etc', '/sys', '/proc']
            if any(str(path_obj).startswith(danger) for danger in dangerous_paths):
                return {
                    'path': str(path_obj),
                    'status': 'forbidden',
                    'error': '不允许删除系统目录'
                }
            
            if path_obj.is_file():
                path_obj.unlink()
                return {
                    'path': str(path_obj),
                    'status': 'success',
                    'type': 'file',
                    'message': f'成功删除文件: {path_obj.name}'
                }
            elif path_obj.is_dir():
                if force:
                    shutil.rmtree(path_obj)
                    return {
                        'path': str(path_obj),
                        'status': 'success',
                        'type': 'directory',
                        'message': f'成功删除目录: {path_obj.name}'
                    }
                else:
                    # 检查目录是否为空
                    if any(path_obj.iterdir()):
                        return {
                            'path': str(path_obj),
                            'status': 'not_empty',
                            'error': '目录不为空，使用 force=True 强制删除'
                        }
                    else:
                        path_obj.rmdir()
                        return {
                            'path': str(path_obj),
                            'status': 'success',
                            'type': 'directory',
                            'message': f'成功删除空目录: {path_obj.name}'
                        }
            
        except Exception as e:
            return {
                'path': path,
                'status': 'error',
                'error': str(e)
            }
    
    def run_all_operations(self, editor_type: str) -> Dict:
        """运行所有清理操作"""
        print("\n" + "="*60)
        print("🚀 开始执行完整清理操作流程")
        print("="*60)
        print(f"📱 目标编辑器: {self.EDITORS.get(editor_type, editor_type)}")
        sys.stdout.flush()
        
        logger.info(f"开始执行完整清理操作: {editor_type}")
        
        # 首先结束编辑器进程
        print("\n🛑 第0步: 结束编辑器进程...")
        self.kill_editor_processes(editor_type)
        
        results = {
            'editor_type': editor_type,
            'operations': {}
        }
        
        operations = [
            ('modify_telemetry_ids', '🆔 第1步: 修改遥测ID', self.modify_telemetry_ids),
            ('clean_database', '🗄️  第2步: 清理数据库', self.clean_database),
            ('clean_workspace', '📁 第3步: 清理工作区', self.clean_workspace),
            ('clear_chat_history', '💬 第4步: 清理聊天历史', self.clear_chat_history),
            ('clean_extension_cache', '🗂️  第5步: 清理扩展缓存', self.clean_extension_cache),
            ('clean_logs_and_crashes', '📋 第6步: 清理日志崩溃', self.clean_logs_and_crashes),
            ('clean_browser_cache', '🌐 第7步: 清理浏览器缓存', self.clean_browser_cache),
            ('clean_user_settings', '⚙️  第8步: 清理用户设置', self.clean_user_settings),
            ('clean_network_cache', '🌍 第9步: 清理网络缓存', self.clean_network_cache),
            ('clean_temporary_files', '🗑️  第10步: 清理临时文件', self.clean_temporary_files),
            ('clean_vscode_cdn_cache', '📦 第11步: 清理CDN缓存', self.clean_vscode_cdn_cache),
            ('clean_augment_deep', '🚀 第12步: Augment深度清理', self.clean_augment_deep),
            ('clean_analytics_data', '📊 第13步: 分析数据清理', self.clean_analytics_data),
            ('reinstall_plugin', '🔌 第14步: 重新安装插件', self.reinstall_plugin)
        ]
        
        try:
            for i, (op_key, op_desc, op_func) in enumerate(operations, 1):
                print(f"\n{op_desc}")
                print(f"   进度: {i}/{len(operations)}")
                
                try:
                    results['operations'][op_key] = op_func(editor_type)
                    print(f"   ✅ {op_desc.split(':')[1].strip()} 完成")
                except Exception as e:
                    print(f"   ❌ {op_desc.split(':')[1].strip()} 失败: {e}")
                    results['operations'][op_key] = {
                        'status': 'error',
                        'error': str(e)
                    }
            
            results['status'] = 'success'
            results['message'] = '所有操作执行完成'
            
            print(f"\n🎉 所有操作执行完成！")
            print("="*60)
            
        except Exception as e:
            results['status'] = 'error'
            results['error'] = str(e)
            print(f"\n❌ 执行过程出现错误: {e}")
            logger.error(f"执行操作时出错: {e}")
        
        return results
    
    def run_all_operations_command(self, editor_type: str) -> Dict:
        """完整的操作命令"""
        logger.info(f"开始执行完整操作序列: {editor_type}")
        
        # 1. 获取系统信息
        system_info = self.get_system_info()
        
        # 2. 执行所有操作
        operations_result = self.run_all_operations(editor_type)
        
        # 3. 验证与完成
        verification_result = self.verify_operations_result(operations_result)
        
        # 4. 生成最终报告
        final_result = {
            'system_info': system_info,
            'operations_result': operations_result,
            'verification': verification_result,
            'recovery_options': {
                'storage_backup': 'storage.json.bak 文件可用于恢复配置',
                'machine_id_backup': 'machine_id_backup.json 包含原始ID信息',
                'operation_log': '详细操作日志已记录'
            }
        }
        
        # 5. 生成并打印详细报告
        detailed_report = self.generate_operation_report(final_result)
        logger.info("生成详细操作报告")
        print(detailed_report)
        
        return final_result
    
    def verify_operations_result(self, operations_result: Dict) -> Dict:
        """验证操作结果"""
        verification = {
            'overall_status': operations_result.get('status', 'unknown'),
            'operations_completed': len(operations_result.get('operations', {})),
            'issues_found': [],
            'recommendations': []
        }
        
        # 检查各个操作的结果
        operations = operations_result.get('operations', {})
        
        if 'modify_telemetry_ids' in operations:
            telemetry_result = operations['modify_telemetry_ids']
            if telemetry_result.get('backup_created'):
                verification['recommendations'].append('遥测ID已成功修改，备份文件已创建')
            
        if 'clean_database' in operations:
            db_result = operations['clean_database']
            deleted_rows = db_result.get('deleted_rows', 0)
            if deleted_rows > 0:
                verification['recommendations'].append(f'数据库清理成功，删除了 {deleted_rows} 行数据')
            else:
                verification['issues_found'].append('数据库中未找到需要清理的数据')
        
        if 'clean_workspace' in operations:
            workspace_result = operations['clean_workspace']
            deleted_files = workspace_result.get('deleted_files', 0)
            if deleted_files > 0:
                verification['recommendations'].append(f'工作区清理成功，删除了 {deleted_files} 个文件')
        
        # 检查新增的深度清洗功能
        deep_clean_ops = ['clean_extension_cache', 'clean_logs_and_crashes', 'clean_browser_cache', 
                         'clean_user_settings', 'clean_network_cache', 'clean_temporary_files',
                         'clean_vscode_cdn_cache', 'clean_augment_deep', 'clean_analytics_data']
        
        for op_name in deep_clean_ops:
            if op_name in operations:
                result = operations[op_name]
                deleted = result.get('deleted_files', 0) or result.get('cleaned_items', 0) or result.get('cleaned_database_rows', 0)
                if deleted > 0:
                    op_display = op_name.replace('_', ' ').title()
                    verification['recommendations'].append(f'{op_display}成功，清理了 {deleted} 项')
        
        verification['message'] = '操作验证完成'
        return verification
    
    def generate_operation_report(self, final_result: Dict) -> str:
        """生成详细的操作报告"""
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("📊 VS Code 遥测管理器 - 操作报告")
        report_lines.append("=" * 60)
        
        # 系统信息部分
        system_info = final_result.get('system_info', {})
        report_lines.append("\n🖥️  系统信息:")
        report_lines.append(f"   平台: {system_info.get('platform', 'unknown')}")
        report_lines.append(f"   可用编辑器: {len(system_info.get('available_editors', []))} 个")
        
        # 操作结果部分
        operations_result = final_result.get('operations_result', {})
        verification = final_result.get('verification', {})
        
        report_lines.append(f"\n📋 总体状态: {operations_result.get('status', 'unknown').upper()}")
        report_lines.append(f"📝 完成操作数: {verification.get('operations_completed', 0)}")
        
        # 详细操作结果
        operations = operations_result.get('operations', {})
        
        if operations:
            report_lines.append("\n🔧 操作详情:")
            
            # 1. 遥测ID修改
            if 'modify_telemetry_ids' in operations:
                telemetry = operations['modify_telemetry_ids']
                report_lines.append("\n   ✅ 遥测ID修改:")
                report_lines.append(f"      原machineId: {telemetry.get('old_machine_id', 'N/A')[:8]}...")
                report_lines.append(f"      新machineId: {telemetry.get('new_machine_id', 'N/A')[:8]}...")
                report_lines.append(f"      备份文件: {telemetry.get('backup_created', 'N/A')}")
            
            # 2. 数据库清理
            if 'clean_database' in operations:
                db_result = operations['clean_database']
                deleted_rows = db_result.get('deleted_rows', 0)
                status_icon = "✅" if deleted_rows > 0 else "⚠️"
                report_lines.append(f"\n   {status_icon} 数据库清理:")
                report_lines.append(f"      删除行数: {deleted_rows}")
                report_lines.append(f"      处理数据库: {len(db_result.get('processed_databases', []))}")
                
                if deleted_rows == 0:
                    report_lines.append("      注意: 未找到需要清理的augment数据")
            
            # 3. 工作区清理
            if 'clean_workspace' in operations:
                workspace = operations['clean_workspace']
                deleted_files = workspace.get('deleted_files', 0)
                status_icon = "✅" if deleted_files > 0 else "⚠️"
                report_lines.append(f"\n   {status_icon} 工作区清理:")
                report_lines.append(f"      删除文件: {deleted_files}")
                report_lines.append(f"      处理目录: {len(workspace.get('processed_directories', []))}")
            
            # 4. 聊天历史清理
            if 'clear_chat_history' in operations:
                chat = operations['clear_chat_history']
                deleted_files = chat.get('deleted_files', 0)
                status_icon = "✅" if deleted_files > 0 else "⚠️"
                report_lines.append(f"\n   {status_icon} 聊天历史清理:")
                report_lines.append(f"      删除文件: {deleted_files}")
                report_lines.append(f"      处理路径: {len(chat.get('processed_paths', []))}")
            
            # 5. 插件重安装
            if 'reinstall_plugin' in operations:
                plugin = operations['reinstall_plugin']
                installed = plugin.get('total_installed', 0)
                failed = plugin.get('total_failed', 0)
                status_icon = "✅" if installed > 0 else "❌" if failed > 0 else "⚠️"
                report_lines.append(f"\n   {status_icon} 插件重安装:")
                report_lines.append(f"      成功安装: {installed}")
                report_lines.append(f"      安装失败: {failed}")
                
                if plugin.get('installed_plugins'):
                    report_lines.append("      成功插件:")
                    for p in plugin.get('installed_plugins', [])[:3]:  # 只显示前3个
                        report_lines.append(f"        - {p.get('plugin_id', 'unknown')}")
        
        # 验证结果部分
        if verification.get('recommendations'):
            report_lines.append("\n✅ 成功项目:")
            for rec in verification['recommendations']:
                report_lines.append(f"   • {rec}")
        
        if verification.get('issues_found'):
            report_lines.append("\n⚠️  注意事项:")
            for issue in verification['issues_found']:
                report_lines.append(f"   • {issue}")
        
        # 恢复选项
        recovery = final_result.get('recovery_options', {})
        if recovery:
            report_lines.append("\n🔄 恢复选项:")
            for key, value in recovery.items():
                report_lines.append(f"   • {value}")
        
        # 操作建议
        report_lines.append("\n💡 操作建议:")
        total_changes = 0
        if operations:
            total_changes += operations.get('clean_database', {}).get('deleted_rows', 0)
            total_changes += operations.get('clean_workspace', {}).get('deleted_files', 0)
            total_changes += operations.get('clear_chat_history', {}).get('deleted_files', 0)
        
        if total_changes > 0:
            report_lines.append("   • 建议重启编辑器以确保更改生效")
            report_lines.append("   • 如有问题，可使用备份文件恢复")
        else:
            report_lines.append("   • 系统中未发现需要清理的数据")
            report_lines.append("   • 可能AugmentCode插件未安装或已清理")
        
        report_lines.append("\n" + "=" * 60)
        report_lines.append(f"📅 报告生成时间: {uuid.uuid4().hex[:8]}")  # 简单的时间标识
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)
    
    def generate_simple_report(self, operations_result: Dict) -> str:
        """生成简化的操作报告"""
        report_lines = []
        report_lines.append("\n" + "="*40)
        report_lines.append("📊 操作总结")
        report_lines.append("="*40)
        
        operations = operations_result.get('operations', {})
        total_success = 0
        total_items = 0
        
        for op_name, op_result in operations.items():
            if op_name == 'modify_telemetry_ids':
                if op_result.get('backup_created'):
                    report_lines.append("✅ 遥测ID修改 - 成功")
                    total_success += 1
                else:
                    report_lines.append("❌ 遥测ID修改 - 失败")
                total_items += 1
                
            elif op_name == 'clean_database':
                deleted = op_result.get('deleted_rows', 0)
                if deleted > 0:
                    report_lines.append(f"✅ 数据库清理 - 删除{deleted}行")
                    total_success += 1
                else:
                    report_lines.append("⚠️  数据库清理 - 无数据需清理")
                total_items += 1
                
            elif op_name == 'clean_workspace':
                deleted = op_result.get('deleted_files', 0)
                if deleted > 0:
                    report_lines.append(f"✅ 工作区清理 - 删除{deleted}文件")
                    total_success += 1
                else:
                    report_lines.append("⚠️  工作区清理 - 无文件需清理")
                total_items += 1
                
            elif op_name == 'clear_chat_history':
                deleted = op_result.get('deleted_files', 0)
                if deleted > 0:
                    report_lines.append(f"✅ 聊天历史清理 - 删除{deleted}文件")
                    total_success += 1
                else:
                    report_lines.append("⚠️  聊天历史清理 - 无历史需清理")
                total_items += 1
                
            elif op_name == 'reinstall_plugin':
                installed = op_result.get('total_installed', 0)
                failed = op_result.get('total_failed', 0)
                if installed > 0:
                    report_lines.append(f"✅ 插件重安装 - 成功{installed}个")
                    total_success += 1
                elif failed > 0:
                    report_lines.append(f"❌ 插件重安装 - 失败{failed}个")
                else:
                    report_lines.append("⚠️  插件重安装 - 无操作")
                total_items += 1
        
        report_lines.append(f"\n📈 总计: {total_success}/{total_items} 项操作成功")
        
        if operations_result.get('status') == 'success':
            report_lines.append("🎉 整体状态: 操作完成")
        else:
            report_lines.append("⚠️  整体状态: 有问题需要注意")
            
        report_lines.append("="*40)
        return "\n".join(report_lines)

    def auto_deep_clean(self, editor_type: str, max_retries: int = 3) -> Dict:
        """全自动深度清洗 - 多重试机制，确保无遗漏"""
        print("\n" + "🚀" * 30)
        print("全自动深度清洗模式")
        print("🚀" * 30 + "\n")

        # 获取编辑器路径
        editor_path = self.get_editor_path(editor_type)

        all_results = {
            'editor_type': editor_type,
            'rounds': [],
            'total_deleted_files': 0,
            'total_deleted_db_rows': 0,
            'verification_passed': False
        }

        for round_num in range(1, max_retries + 1):
            print(f"\n{'='*60}")
            print(f"🔄 第 {round_num}/{max_retries} 轮清洗")
            print(f"{'='*60}\n")

            round_result = {
                'round': round_num,
                'scan_result': None,
                'clean_results': [],
                'verification': None
            }

            # 步骤1: 深度扫描
            print(f"📍 步骤1: 深度扫描")
            scan_result = self.deep_scan_augment_data(editor_type)
            round_result['scan_result'] = scan_result

            if scan_result['total_found'] == 0:
                print(f"   ✅ 未发现Augment数据，清洗完成！")
                round_result['verification'] = {'clean': True}
                all_results['rounds'].append(round_result)
                all_results['verification_passed'] = True
                break

            print(f"   🎯 发现 {scan_result['total_found']} 个位置需要清理")

            # 步骤2: 执行多种清理方案
            print(f"\n📍 步骤2: 执行清理方案")

            # 方案A: 清理globalStorage目录
            if scan_result['found_locations']['globalStorage_dirs']:
                print(f"   🔧 方案A: 清理globalStorage ({len(scan_result['found_locations']['globalStorage_dirs'])}个)")
                deleted = 0
                for dir_path in scan_result['found_locations']['globalStorage_dirs']:
                    try:
                        print(f"      🔍 检查: {dir_path}")
                        if not dir_path.exists():
                            print(f"      ⚠️  路径不存在: {dir_path}")
                            continue

                        if self._is_dangerous_path(dir_path):
                            print(f"      ⚠️  危险路径，跳过: {dir_path}")
                            continue

                        file_count = len(list(dir_path.rglob("*")))
                        print(f"      📊 包含 {file_count} 个文件")
                        shutil.rmtree(dir_path)
                        deleted += file_count
                        print(f"      ✅ 删除: {dir_path.name} ({file_count}个文件)")
                    except PermissionError as e:
                        print(f"      ❌ 权限不足: {e}")
                    except Exception as e:
                        print(f"      ❌ 失败: {type(e).__name__}: {e}")

                round_result['clean_results'].append({'method': 'globalStorage', 'deleted': deleted})
                all_results['total_deleted_files'] += deleted
                print(f"      📊 方案A总计删除: {deleted}个文件")

            # 方案B: 清理workspaceStorage目录
            if scan_result['found_locations']['workspaceStorage_dirs']:
                print(f"   🔧 方案B: 清理workspaceStorage ({len(scan_result['found_locations']['workspaceStorage_dirs'])}个)")
                deleted = 0
                for dir_path in scan_result['found_locations']['workspaceStorage_dirs']:
                    try:
                        print(f"      🔍 检查: {dir_path.name[:30]}...")
                        if not dir_path.exists():
                            print(f"      ⚠️  路径不存在")
                            continue

                        if self._is_dangerous_path(dir_path):
                            print(f"      ⚠️  危险路径，跳过")
                            continue

                        file_count = len(list(dir_path.rglob("*")))
                        print(f"      📊 包含 {file_count} 个文件")
                        shutil.rmtree(dir_path)
                        deleted += file_count
                        print(f"      ✅ 删除: {dir_path.name[:20]}... ({file_count}个文件)")
                    except PermissionError as e:
                        print(f"      ❌ 权限不足: {e}")
                    except Exception as e:
                        print(f"      ❌ 失败: {type(e).__name__}: {e}")

                round_result['clean_results'].append({'method': 'workspaceStorage', 'deleted': deleted})
                all_results['total_deleted_files'] += deleted
                print(f"      📊 方案B总计删除: {deleted}个文件")

            # 方案C: 清理数据库
            if scan_result['found_locations']['database_files']:
                print(f"   🔧 方案C: 清理数据库 ({len(scan_result['found_locations']['database_files'])}个)")
                deleted_rows = 0

                # 从配置获取清理键
                cleanup_keys = self.config.get('database_cleanup_keys', {}).get('augment_specific', [
                    '%augment%', '%chat%', '%conversation%', '%message%',
                    '%dialog%', '%session%', '%history%', '%AugmentCode%',
                    '%augmentcode%', '%vscode-augment%', '%Fix with Augment%'
                ])

                for db_file, _ in scan_result['found_locations']['database_files']:
                    try:
                        conn = sqlite3.connect(db_file)
                        cursor = conn.cursor()

                        for key_pattern in cleanup_keys:
                            cursor.execute("DELETE FROM ItemTable WHERE key LIKE ?", (key_pattern,))
                            deleted_rows += cursor.rowcount

                        conn.commit()
                        conn.close()
                        print(f"      ✅ 清理: {Path(db_file).parent.name[:20]}... ({deleted_rows}行)")
                    except Exception as e:
                        print(f"      ❌ 失败: {e}")

                round_result['clean_results'].append({'method': 'database', 'deleted': deleted_rows})
                all_results['total_deleted_db_rows'] += deleted_rows

            # 方案D: 清理其他文件
            if scan_result['found_locations']['other_files']:
                print(f"   🔧 方案D: 清理其他文件 ({len(scan_result['found_locations']['other_files'])}个)")
                deleted = 0
                for file_path in scan_result['found_locations']['other_files']:
                    try:
                        print(f"      🔍 检查: {file_path.name[:50]}...")
                        if not file_path.exists():
                            print(f"      ⚠️  路径不存在")
                            continue

                        if self._is_dangerous_path(file_path):
                            print(f"      ⚠️  危险路径，跳过")
                            continue

                        if file_path.is_file():
                            file_path.unlink()
                            deleted += 1
                            print(f"      ✅ 删除文件: {file_path.name[:40]}...")
                        elif file_path.is_dir():
                            file_count = len(list(file_path.rglob("*")))
                            shutil.rmtree(file_path)
                            deleted += file_count
                            print(f"      ✅ 删除目录: {file_path.name[:40]}... ({file_count}个文件)")
                    except PermissionError as e:
                        print(f"      ❌ 权限不足: {e}")
                    except Exception as e:
                        print(f"      ❌ 失败: {type(e).__name__}: {e}")

                round_result['clean_results'].append({'method': 'other_files', 'deleted': deleted})
                all_results['total_deleted_files'] += deleted
                print(f"      📊 方案D总计删除: {deleted}个文件")

            # 步骤3: 验证清理效果
            print(f"\n📍 步骤3: 验证清理效果")
            time.sleep(2)  # 等待文件系统同步

            verify_scan = self.deep_scan_augment_data(editor_type)
            round_result['verification'] = verify_scan

            if verify_scan['total_found'] == 0:
                print(f"   ✅ 验证通过！所有Augment数据已清除")
                all_results['verification_passed'] = True
                all_results['rounds'].append(round_result)
                break
            else:
                print(f"   ⚠️  仍有 {verify_scan['total_found']} 个位置残留，继续下一轮...")
                all_results['rounds'].append(round_result)

        # 最终报告
        print(f"\n{'='*60}")
        print(f"📊 全自动深度清洗完成报告")
        print(f"{'='*60}")
        print(f"   执行轮数: {len(all_results['rounds'])}/{max_retries}")
        print(f"   删除文件: {all_results['total_deleted_files']}个")
        print(f"   删除数据库记录: {all_results['total_deleted_db_rows']}行")
        print(f"   验证状态: {'✅ 通过' if all_results['verification_passed'] else '⚠️  未完全清除'}")

        if not all_results['verification_passed']:
            print(f"\n⚠️  警告: 经过{max_retries}轮清洗仍有残留数据")
            print(f"   建议: 1) 检查文件权限 2) 以管理员身份运行 3) 手动检查残留位置")

        return all_results

def main():
    """主函数"""
    manager = TelemetryManager()
    
    print("=== VS Code/Cursor/VSCodium 遥测管理器 ===")
    
    # 获取系统信息
    system_info = manager.get_system_info()
    print(f"系统信息: {json.dumps(system_info, indent=2, ensure_ascii=False)}")
    
    if not system_info['available_editors']:
        print("未检测到支持的编辑器")
        return
    
    # 显示可用编辑器
    print("\n可用的编辑器:")
    for i, editor in enumerate(system_info['available_editors']):
        print(f"{i+1}. {editor['name']} ({editor['type']})")
    
    # 选择编辑器
    try:
        choice = int(input("\n请选择编辑器 (输入数字): ")) - 1
        if choice < 0 or choice >= len(system_info['available_editors']):
            print("无效选择")
            return
        
        selected_editor = system_info['available_editors'][choice]
        editor_type = selected_editor['type']
        
        print(f"\n已选择: {selected_editor['name']}")
        
        # 显示操作选项
        operations = manager.get_supported_operations()
        print("\n支持的操作:")
        for i, op in enumerate(operations):
            print(f"{i+1}. {op}")
        print(f"{len(operations)+1}. 执行所有操作 (简化报告)")
        print(f"{len(operations)+2}. 执行完整操作序列 (详细报告)")
        print(f"{len(operations)+3}. 🚀 全自动深度清洗模式 (推荐)")

        # 选择操作
        op_choice = int(input("\n请选择操作 (输入数字): "))

        if op_choice == len(operations) + 1:
            # 执行所有操作
            result = manager.run_all_operations(editor_type)
            print(f"\n执行结果:\n{json.dumps(result, indent=2, ensure_ascii=False)}")

            # 生成简化报告
            print(manager.generate_simple_report(result))

        elif op_choice == len(operations) + 2:
            # 执行完整操作序列（包含报告）
            result = manager.run_all_operations_command(editor_type)
            # 报告已在函数内打印

        elif op_choice == len(operations) + 3:
            # 🚀 全自动深度清洗模式
            print("\n" + "🚀" * 30)
            print("启动全自动深度清洗模式")
            print("🚀" * 30)
            print("\n⚠️  注意事项:")
            print("   1. 此模式将执行多轮深度扫描和清理")
            print("   2. 会自动重试直到完全清除或达到最大轮数")
            print("   3. 建议先关闭所有VS Code窗口")
            print("   4. 建议以管理员身份运行")

            confirm = input("\n是否继续? (y/n): ").lower()
            if confirm != 'y':
                print("已取消操作")
                return

            # 步骤1: 强制结束进程
            print("\n📍 步骤1: 强制结束编辑器进程")
            kill_result = manager.kill_editor_processes_command(editor_type)
            if kill_result['status'] == 'success':
                print(f"   ✅ 成功终止 {kill_result.get('total_killed', 0)} 个进程")
            else:
                print(f"   ⚠️  进程终止状态: {kill_result['status']}")

            # 步骤2: 修改遥测ID
            print("\n📍 步骤2: 修改遥测ID")
            try:
                telemetry_result = manager.modify_telemetry_ids(editor_type)
                print(f"   ✅ 遥测ID已修改")
                print(f"   新machineId: {telemetry_result['new_machine_id'][:8]}...")
            except Exception as e:
                print(f"   ⚠️  遥测ID修改失败: {e}")

            # 步骤3: 全自动深度清洗
            print("\n📍 步骤3: 执行全自动深度清洗")
            max_retries = 3
            retry_input = input(f"   最大重试轮数 (默认{max_retries}): ").strip()
            if retry_input.isdigit():
                max_retries = int(retry_input)

            clean_result = manager.auto_deep_clean(editor_type, max_retries=max_retries)

            # 步骤4: 最终验证
            print("\n📍 步骤4: 最终验证")
            final_scan = manager.deep_scan_augment_data(editor_type)

            if final_scan['total_found'] == 0:
                print("   ✅✅✅ 完美！所有Augment数据已彻底清除！")
            else:
                print(f"   ⚠️  仍有 {final_scan['total_found']} 个位置残留")
                print("   残留位置详情:")
                for key, items in final_scan['found_locations'].items():
                    if items:
                        print(f"      - {key}: {len(items)}个")

            # 生成最终报告
            print("\n" + "="*60)
            print("📊 全自动深度清洗最终报告")
            print("="*60)
            print(f"   执行轮数: {len(clean_result['rounds'])}/{max_retries}")
            print(f"   删除文件总数: {clean_result['total_deleted_files']}")
            print(f"   删除数据库记录: {clean_result['total_deleted_db_rows']}")
            print(f"   最终验证: {'✅ 通过' if final_scan['total_found'] == 0 else '⚠️  有残留'}")
            print("="*60)

        elif 1 <= op_choice <= len(operations):
            # 执行单个操作
            operation = operations[op_choice - 1]
            method = getattr(manager, operation)

            if operation == 'kill_editor_processes':
                result = method(editor_type)
                print(f"\n操作结果: {result}")
            else:
                result = method(editor_type)
                print(f"\n操作结果:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
        else:
            print("无效选择")

    except KeyboardInterrupt:
        print("\n\n操作已取消")
    except Exception as e:
        print(f"\n执行过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()