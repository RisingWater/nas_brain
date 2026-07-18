r"""
从 Paimon 数据库导入用户和声纹到 NAS Brain

来源: D:\Users\Downloads\paimon_20260718_214951\db\paimon.db
录音: D:\Users\Downloads\paimon_20260718_214951\recordings\
目标: <project>/data/nas_brain.db, <project>/data/recordings/
"""
import os
import sys
import sqlite3
import uuid
import shutil
import logging
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("import_paimon")

# === 路径配置 ===
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAIMON_DIR = r"D:\Users\Downloads\paimon_20260718_214951"
PAIMON_DB = os.path.join(PAIMON_DIR, "db", "paimon.db")
PAIMON_RECORDINGS = os.path.join(PAIMON_DIR, "recordings")

# NAS Brain 目标
TARGET_DB = os.getenv("DB_PATH", os.path.join(PROJECT_ROOT, "data", "nas_brain.db"))
TARGET_RECORD_DIR = os.path.join(PROJECT_ROOT, "data", "recordings")


def get_target_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(TARGET_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_paimon_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(PAIMON_DB)
    conn.row_factory = sqlite3.Row
    return conn


def find_or_create_user(conn, display_name: str) -> str:
    """按 display_name 查找用户，不存在则创建"""
    cursor = conn.execute(
        "SELECT user_id, display_name FROM users WHERE display_name = ? AND is_active = 1",
        (display_name,)
    )
    row = cursor.fetchone()
    if row:
        log.info("用户已存在: %s -> %s", display_name, row["user_id"])
        return row["user_id"]

    user_id = f"u_{uuid.uuid4().hex[:8]}"
    conn.execute(
        """INSERT INTO users (user_id, display_name, user_type, is_temp, is_active)
           VALUES (?, ?, 'person', 0, 1)""",
        (user_id, display_name)
    )
    conn.commit()
    log.info("创建用户: %s -> %s", display_name, user_id)
    return user_id


def copy_audio(rel_path: str, target_user_id: str) -> str:
    """复制音频文件到目标 RECORD_DIR，返回相对路径"""
    src = os.path.join(PAIMON_RECORDINGS, rel_path.replace("recordings/", "", 1))
    if not os.path.exists(src):
        src = os.path.join(PAIMON_RECORDINGS, rel_path)
    if not os.path.exists(src):
        log.warning("音频文件不存在: %s", src)
        return ""

    target_dir = os.path.join(TARGET_RECORD_DIR, target_user_id)
    os.makedirs(target_dir, exist_ok=True)
    fname = os.path.basename(src)
    dst = os.path.join(target_dir, f"paimon_{fname}")
    shutil.copy2(src, dst)

    # 返回相对路径（data/recordings/...）
    rel = os.path.relpath(dst, os.path.dirname(TARGET_RECORD_DIR))
    relative_path = rel.replace(os.sep, "/")
    log.info("复制音频: %s -> %s", fname, relative_path)
    return relative_path


def user_id_from_paimon_id(paimon_user_id: int) -> str:
    """从 paimon user_id 转为目标 user_id"""
    # 从映射表中查找
    return _PAIMON_TO_NAS.get(paimon_user_id)


def main():
    global _PAIMON_TO_NAS

    if not os.path.exists(PAIMON_DB):
        log.error("Paimon DB 不存在: %s", PAIMON_DB)
        sys.exit(1)

    pconn = get_paimon_conn()
    tconn = get_target_conn()

    # === Step 1: 读取 Paimon 用户 ===
    p_cursor = pconn.execute("SELECT * FROM users")
    paimon_users = {r["id"]: r["name"] for r in p_cursor.fetchall()}
    log.info("Paimon 用户: %s", paimon_users)

    # === Step 2: 创建/查找 NAS Brain 用户 ===
    _PAIMON_TO_NAS = {}
    for pid, name in paimon_users.items():
        if name in ("定时任务",):
            log.info("跳过定时任务用户")
            continue
        nas_uid = find_or_create_user(tconn, name)
        _PAIMON_TO_NAS[pid] = nas_uid

    log.info("用户映射: %s", _PAIMON_TO_NAS)

    # === Step 3: 读取 Paimon 声纹 ===
    p_cursor = pconn.execute("SELECT * FROM voiceprints ORDER BY id")
    voiceprints = [dict(r) for r in p_cursor.fetchall()]
    log.info("Paimon 声纹总数: %d", len(voiceprints))

    # === Step 4: 导入声纹 ===
    imported = 0
    skipped = 0
    for vp in voiceprints:
        pid = vp["user_id"]
        if pid not in _PAIMON_TO_NAS:
            log.warning("跳过未知用户 voiceprint id=%d, user_id=%d", vp["id"], pid)
            skipped += 1
            continue

        target_uid = _PAIMON_TO_NAS[pid]
        vector = np.frombuffer(vp["vector"], dtype=np.float32)
        if len(vector) != 192:
            log.warning("跳过异常向量: id=%d, len=%d", vp["id"], len(vector))
            skipped += 1
            continue

        # 复制音频
        audio_path = copy_audio(vp["audio_path"], target_uid) if vp["audio_path"] else ""

        # 插入声纹
        tconn.execute(
            """INSERT INTO voiceprints (user_id, vector, audio_path, vp_type, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (target_uid, vp["vector"], audio_path, vp.get("type", "auto"), vp["created_at"])
        )
        imported += 1

    tconn.commit()
    tconn.close()
    pconn.close()

    log.info("=" * 40)
    log.info("导入完成!")
    log.info("  导入声纹: %d", imported)
    log.info("  跳过:     %d", skipped)
    log.info("  目标 DB:  %s", TARGET_DB)
    log.info("  目标录音: %s", TARGET_RECORD_DIR)


if __name__ == "__main__":
    main()
