from __future__ import annotations

from tkinter import messagebox, simpledialog


class DialogService:
    """Thin wrapper around tkinter dialogs to keep UI code consistent."""

    def info(self, title: str, message: str, *, parent=None) -> None:
        messagebox.showinfo(title, message, parent=parent)

    def warning(self, title: str, message: str, *, parent=None) -> None:
        messagebox.showwarning(title, message, parent=parent)

    def error(self, title: str, message: str, *, parent=None) -> None:
        messagebox.showerror(title, message, parent=parent)

    def confirm_yes_no(self, title: str, message: str, *, parent=None) -> bool:
        return bool(messagebox.askyesno(title, message, parent=parent))

    def confirm_yes_no_cancel(self, title: str, message: str, *, parent=None):
        return messagebox.askyesnocancel(title, message, parent=parent)

    def ask_string(self, title: str, prompt: str, *, parent=None, initialvalue: str | None = None):
        return simpledialog.askstring(title, prompt, parent=parent, initialvalue=initialvalue)
