"""
FeiShark Studio - 数据库初始化
轻量解耦方案：任务队列 + 模型资产管理
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "feishark.db")


def get_connection() -> sqlite3.Connection:
    """获取数据库连接，启用外键约束"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库，创建基础表"""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id     TEXT PRIMARY KEY,
                input_file  TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending',
                error_log   TEXT DEFAULT '',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS voice_assets (
                model_id      TEXT PRIMARY KEY,
                model_name    TEXT NOT NULL,
                pth_path      TEXT NOT NULL,
                index_path    TEXT NOT NULL,
                default_pitch INTEGER NOT NULL DEFAULT 0
            );
        """)
        conn.commit()
        print(f"[OK] 数据库初始化完成: {DB_PATH}")
        print(f"     tasks 表: {conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]} 条记录")
        print(f"     voice_assets 表: {conn.execute('SELECT COUNT(*) FROM voice_assets').fetchone()[0]} 条记录")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
