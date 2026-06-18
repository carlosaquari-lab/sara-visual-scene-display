import tkinter as tk

from app.ui_main import SaraApp


def main() -> None:
    root = tk.Tk()
    SaraApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
