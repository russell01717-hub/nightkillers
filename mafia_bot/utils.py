"""Utility functions for atomic file writes and safe JSON loading."""

import json
import os
import shutil
import logging


def atomic_write(filepath, data):
    tmp = filepath + ".tmp"
    backup = filepath + ".bak"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(filepath):
            try:
                shutil.copy2(filepath, backup)
            except:
                pass
        if os.path.exists(filepath):
            os.replace(tmp, filepath)
        else:
            shutil.move(tmp, filepath)
    except Exception as e:
        logging.error(f"atomic_write failed for {filepath}: {e}")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except:
            pass


def safe_json_load(filepath, default=None):
    try:
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        backup = filepath + ".bak"
        try:
            with open(backup, encoding="utf-8") as f:
                data = json.load(f)
            logging.warning(f"Recovered {filepath} from backup")
            atomic_write(filepath, data)
            return data
        except:
            pass
    except Exception:
        pass
    return default if default is not None else {}