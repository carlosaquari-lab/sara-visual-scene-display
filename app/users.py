import os
import csv
import time
from datetime import datetime
from app.i18n import tr
from app.services.dialog_service import DialogService


class UsersManager:
    """
    Users stored in sara_data/users.csv
    Tracks:
      total_sessions, total_key_presses, total_words_inserted, total_characters_inserted,
      total_time_seconds, last_session_date, last_session_end
    """
    def __init__(self, users_csv_path: str):
        self.users_csv = users_csv_path
        self.users = {}
        self.dialogs = DialogService()
        self.current_user_id = None

        # per-user segment counters (inside a session)
        self.user_segment_start_time = time.time()
        self.user_segment_key_presses = 0
        self.user_segment_words_inserted = 0
        self.user_segment_characters_inserted = 0

    def load_users_from_csv(self) -> None:
        self.users = {}
        self.dialogs = DialogService()
        if not os.path.exists(self.users_csv):
            return
        try:
            with open(self.users_csv, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    uid = row.get("id")
                    if not uid:
                        continue
                    self.users[uid] = {
                        "id": uid,
                        "name": row.get("name", ""),
                        "notes": row.get("notes", ""),
                        "group": row.get("group", ""),
                        "layout_file": row.get("layout_file", ""),
                        "date_created": row.get("date_created", ""),
                        "last_session_date": row.get("last_session_date", ""),
                        "last_session_end": row.get("last_session_end", ""),
                        "total_sessions": row.get("total_sessions", "0"),
                        "total_key_presses": row.get("total_key_presses", "0"),
                        "total_time_seconds": row.get("total_time_seconds", "0"),
                        "total_words_inserted": row.get("total_words_inserted", "0"),
                        "total_characters_inserted": row.get("total_characters_inserted", "0"),
                    }
        except Exception as e:
            self.dialogs.error(tr("dialog_select_user"), ("Could not read users CSV:" if tr("lang_en") == "English" else "No se pudo leer el CSV de usuarios:") + f"\n{e}")

    def save_users_to_csv(self) -> None:
        try:
            with open(self.users_csv, "w", encoding="utf-8", newline="") as f:
                fieldnames = [
                    "id", "name", "notes", "group", "layout_file",
                    "date_created", "last_session_date", "last_session_end",
                    "total_sessions", "total_key_presses", "total_words_inserted", "total_characters_inserted", "total_time_seconds"
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                def _sort_key(uid):
                    try:
                        return int(uid)
                    except Exception:
                        return 999999999

                for uid in sorted(self.users.keys(), key=_sort_key):
                    u = self.users[uid]
                    writer.writerow({
                        "id": u.get("id", ""),
                        "name": u.get("name", ""),
                        "notes": u.get("notes", ""),
                        "group": u.get("group", ""),
                        "layout_file": u.get("layout_file", ""),
                        "date_created": u.get("date_created", ""),
                        "last_session_date": u.get("last_session_date", ""),
                        "last_session_end": u.get("last_session_end", ""),
                        "total_sessions": u.get("total_sessions", 0),
                        "total_key_presses": u.get("total_key_presses", 0),
                        "total_words_inserted": u.get("total_words_inserted", 0),
                        "total_characters_inserted": u.get("total_characters_inserted", 0),
                        "total_time_seconds": u.get("total_time_seconds", 0),
                    })
        except Exception as e:
            self.dialogs.error(tr("dialog_select_user"), ("Could not write users CSV:" if tr("lang_en") == "English" else "No se pudo escribir el CSV de usuarios:") + f"\n{e}")

    def generate_user_id(self) -> str:
        existing_ids = []
        for uid in self.users.keys():
            try:
                existing_ids.append(int(uid))
            except ValueError:
                pass
        n = max(existing_ids) + 1 if existing_ids else 1
        return str(n)

    def get_current_user_name(self):
        if self.current_user_id and self.current_user_id in self.users:
            return self.users[self.current_user_id].get("name", "")
        return None

    def finalize_current_user_segment(self) -> None:
        if not self.current_user_id or self.current_user_id not in self.users:
            self.user_segment_start_time = time.time()
            self.user_segment_key_presses = 0
            self.user_segment_words_inserted = 0
            self.user_segment_characters_inserted = 0
            return

        now = datetime.now()
        segment_duration_s = time.time() - self.user_segment_start_time
        segment_key_presses = self.user_segment_key_presses
        segment_words = self.user_segment_words_inserted
        segment_chars = self.user_segment_characters_inserted

        u = self.users[self.current_user_id]

        def _to_int(value):
            try:
                return int(float(value))
            except Exception:
                return 0

        def _to_float(value):
            try:
                return float(value)
            except Exception:
                return 0.0

        total_key_presses = _to_int(u.get("total_key_presses", 0))
        total_time_seconds = _to_float(u.get("total_time_seconds", 0.0))
        total_words_inserted = _to_int(u.get("total_words_inserted", 0))
        total_characters_inserted = _to_int(u.get("total_characters_inserted", 0))

        u["total_key_presses"] = total_key_presses + segment_key_presses
        u["total_time_seconds"] = total_time_seconds + segment_duration_s
        u["total_words_inserted"] = total_words_inserted + segment_words
        u["total_characters_inserted"] = total_characters_inserted + segment_chars

        u["last_session_date"] = now.date().isoformat()
        u["last_session_end"] = now.strftime("%Y-%m-%d %H:%M:%S")

        self.users[self.current_user_id] = u
        self.save_users_to_csv()

        self.user_segment_start_time = time.time()
        self.user_segment_key_presses = 0
        self.user_segment_words_inserted = 0
        self.user_segment_characters_inserted = 0

    def update_user_session_on_close(self) -> None:
        if not self.current_user_id or self.current_user_id not in self.users:
            return
        u = self.users[self.current_user_id]

        def _to_int(value):
            try:
                return int(float(value))
            except Exception:
                return 0

        total_sessions = _to_int(u.get("total_sessions", 0))
        u["total_sessions"] = total_sessions + 1
        self.users[self.current_user_id] = u
        self.save_users_to_csv()
