"""
SQLite 任务持久化存储
管理分析任务的创建、更新、查询和删除
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from config import OUTPUT_DIR

DB_PATH = OUTPUT_DIR / "tasks.db"


class TaskStore:
    """
    基于 SQLite 的任务存储

    线程安全，支持并发读写
    """

    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                current_stage TEXT DEFAULT '',
                message TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT,
                files TEXT DEFAULT '[]',
                urls TEXT DEFAULT '[]',
                result TEXT DEFAULT NULL,
                error TEXT DEFAULT NULL,
                audience TEXT DEFAULT '通用视角'
            )
        """)
        try:
            conn.execute("ALTER TABLE tasks ADD COLUMN audience TEXT DEFAULT '通用视角'")
        except sqlite3.OperationalError:
            pass # 字段已存在
        conn.commit()

    def create(self, task_id: str) -> Dict[str, Any]:
        """创建新任务"""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO tasks
               (task_id, status, progress, current_stage, message, created_at, updated_at, files, urls, audience)
               VALUES (?, 'pending', 0, '等待中', '', ?, ?, '[]', '[]', '通用视角')""",
            (task_id, now, now),
        )
        conn.commit()
        return self.get(task_id)

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def update(self, task_id: str, **kwargs) -> None:
        """更新任务字段"""
        if not kwargs:
            return

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        kwargs["updated_at"] = now

        # 序列化 JSON 字段
        for key in ("result", "error", "files", "urls"):
            if key in kwargs and not isinstance(kwargs[key], str):
                kwargs[key] = json.dumps(kwargs[key], ensure_ascii=False)

        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [task_id]

        conn = self._get_conn()
        conn.execute(
            f"UPDATE tasks SET {set_clause} WHERE task_id = ?",
            values,
        )
        conn.commit()

    def contains(self, task_id: str) -> bool:
        """检查任务是否存在"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        return row is not None

    def delete(self, task_id: str) -> None:
        """删除任务"""
        conn = self._get_conn()
        conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        conn.commit()

    def list_all(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取所有任务（按创建时间倒序）"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def append_files(self, task_id: str, new_files: list) -> None:
        """追加文件记录"""
        task = self.get(task_id)
        if task is None:
            return
        files = task.get("files", [])
        files.extend(new_files)
        self.update(task_id, files=files)

    def append_urls(self, task_id: str, new_urls: list) -> None:
        """追加 URL 记录"""
        task = self.get(task_id)
        if task is None:
            return
        urls = task.get("urls", [])
        urls.extend(new_urls)
        self.update(task_id, urls=urls)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """将数据库行转为字典"""
        d = dict(row)
        # 反序列化 JSON 字段
        for key in ("files", "urls", "result", "error"):
            if key in d and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d


# 全局单例
task_store = TaskStore()
