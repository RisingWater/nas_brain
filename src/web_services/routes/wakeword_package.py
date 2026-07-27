"""web_services — 唤醒词音频打包（直接读SQLite，不走代理）"""
import os
import io
import zipfile
import sqlite3
import tempfile
import shutil
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger("web_services.wakeword")

router = APIRouter()

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


@router.get("/wakeword/package")
async def package_wakeword():
    """打包唤醒音频为 zip（用于训练）"""
    from fastapi import BackgroundTasks
    db_path = os.getenv("DB_PATH", os.path.join(_PROJECT_ROOT, "data", "nas_brain.db"))
    tmpdir = tempfile.mkdtemp()
    count = 0
    try:
        conn = sqlite3.connect(db_path)
        for row in conn.execute("SELECT file_path, category FROM wakeword_records").fetchall():
            fp, cat = row
            if not os.path.isabs(fp):
                fp = os.path.join(_PROJECT_ROOT, fp)
            if os.path.exists(fp):
                cat_dir = os.path.join(tmpdir, cat)
                os.makedirs(cat_dir, exist_ok=True)
                shutil.copy2(fp, os.path.join(cat_dir, os.path.basename(fp)))
                count += 1
        conn.close()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"wakeword_package_{ts}.zip"
        zip_path = os.path.join(tmpdir, zip_filename)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for dirpath, _, filenames in os.walk(tmpdir):
                for f in filenames:
                    if f == zip_filename:
                        continue
                    zf.write(os.path.join(dirpath, f), os.path.relpath(os.path.join(dirpath, f), tmpdir))
        logger.info("唤醒音频打包完成: %d 个文件", count)
        tasks = BackgroundTasks()
        tasks.add_task(shutil.rmtree, tmpdir, ignore_errors=True)
        return FileResponse(zip_path, media_type="application/zip", filename=zip_filename, background=tasks)
    except Exception as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(500, f"打包失败: {e}")
