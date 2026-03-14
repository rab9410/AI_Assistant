import json
import threading
from pathlib import Path

from app.config import THREAD_DIR, MAX_THREAD_NAME_LEN


def get_repo_data(file_path):
    fp = Path(file_path)
    if fp.exists():
        try:
            with open(fp, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def bg_save(file_path, data):
    def save():
        try:
            tmp = Path(str(file_path) + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            tmp.replace(file_path)
        except Exception:
            pass

    threading.Thread(target=save, daemon=True).start()


def read_thread_history(thread_id):
    path = THREAD_DIR / f"{thread_id}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return []


def write_thread_history(thread_id, history):
    path = THREAD_DIR / f"{thread_id}.json"
    try:
        tmp = Path(str(path) + ".tmp")
        tmp.write_text(json.dumps(history, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


def truncate_name(name, max_len=MAX_THREAD_NAME_LEN):
    name = name.replace("\n", " ").strip()
    if len(name) <= max_len:
        return name
    cut = name[:max_len - 1]
    last_space = cut.rfind(" ")
    if last_space > max_len // 2:
        cut = cut[:last_space]
    return cut.rstrip() + "…"