from __future__ import annotations


class LifecycleService:
    """Coordinates application shutdown steps."""

    def __init__(self, audio, users_manager, research):
        self.audio = audio
        self.users_manager = users_manager
        self.research = research

    def close(self, root) -> None:
        try:
            self.audio.stop()
        except Exception:
            pass
        try:
            self.users_manager.finalize_current_user_segment()
            self.users_manager.update_user_session_on_close()
        except Exception:
            pass
        try:
            self.research.flush_session_if_needed(
                user_id=self.users_manager.current_user_id or "",
                user_name=self.users_manager.get_current_user_name() or "",
                reason="close_app",
            )
        except Exception:
            pass
        root.destroy()
