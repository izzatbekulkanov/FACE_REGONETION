import tkinter as tk
from tkinter import scrolledtext
import subprocess
import threading
import os
import sys
import time


class DaphneGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Daphne Server Manager")
        self.root.geometry("600x400")  # Boshlang‘ich o‘lcham
        self.root.configure(bg="#e6f0fa")  # Och qora shaffof fonda oqish
        self.root.resizable(True, True)  # Oynani kengaytirish va kichraytirish imkoni

        # Daphne jarayoni
        self.process = None
        self.running = False

        # GUI elementlari
        self.create_widgets()

        # Virtual muhitni faollashtirish
        self.activate_virtualenv()

        # Loglarni yangilash uchun flag
        self.log_thread = None
        self.stop_logging = False

    def create_widgets(self):
        """GUI elementlarini yaratish."""
        # Sarlavha
        title_label = tk.Label(self.root, text="Daphne Server Manager", font=("Helvetica", 18, "bold"),
                               bg="#e6f0fa", fg="#1a73e8", padx=10, pady=5)
        title_label.pack(pady=10)

        # Loglar uchun matn maydoni (dinamik o‘lcham)
        self.log_frame = tk.Frame(self.root, bg="#ffffff", bd=2, relief="flat")
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_area = scrolledtext.ScrolledText(self.log_frame, width=70, height=15, font=("Arial", 10),
                                                  bg="#ffffff", fg="#333", wrap=tk.WORD)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_area.config(state='disabled')

        # Shisha effekti uchun oqishli fonda soyalar
        self.log_frame.config(highlightbackground="#d3e3f8", highlightthickness=1)

        # Tugmalar ramkasi
        button_frame = tk.Frame(self.root, bg="#e6f0fa")
        button_frame.pack(pady=10)

        # Tugmalar (iOS uslubida yumshoq effektlar)
        self.start_button = tk.Button(button_frame, text="Start", command=self.start_server,
                                      font=("Helvetica", 10), bg="#4CAF50", fg="white",
                                      activebackground="#45a049", width=10, padx=10, pady=5,
                                      relief="flat", bd=0)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(button_frame, text="Stop", command=self.stop_server,
                                     font=("Helvetica", 10), bg="#F44336", fg="white",
                                     activebackground="#da190b", width=10, padx=10, pady=5,
                                     relief="flat", bd=0)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.stop_button.config(state='disabled')

        self.restart_button = tk.Button(button_frame, text="Restart", command=self.restart_server,
                                        font=("Helvetica", 10), bg="#2196F3", fg="white",
                                        activebackground="#1976D2", width=10, padx=10, pady=5,
                                        relief="flat", bd=0)
        self.restart_button.pack(side=tk.LEFT, padx=5)
        self.restart_button.config(state='disabled')

        # Tugmalarga soyalar qo‘shish uchun
        for btn in [self.start_button, self.stop_button, self.restart_button]:
            btn.config(highlightbackground="#d3e3f8", highlightthickness=1)

    def activate_virtualenv(self):
        """Virtual muhitni faollashtirish."""
        venv_path = os.path.join(os.getcwd(), "venv", "bin", "activate")
        if os.path.exists(venv_path):
            os.environ["VIRTUAL_ENV"] = os.path.join(os.getcwd(), "venv")
            os.environ["PATH"] = os.path.join(os.getcwd(), "venv", "bin") + ":" + os.environ.get("PATH", "")
            sys.path.insert(0, os.path.join(os.getcwd(), "venv", "lib", "python3.10", "site-packages"))
            self.log("Virtual muhit faollashtirildi.")
        else:
            self.log("XATO: Virtual muhit topilmadi! 'venv' papkasini tekshiring.")

        os.environ["DJANGO_SETTINGS_MODULE"] = "face_recognition_project.settings"
        self.log("DJANGO_SETTINGS_MODULE o‘rnatildi.")

    def log(self, message):
        """Loglarni GUI oynasida ko‘rsatish."""
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        self.log_area.config(state='disabled')
        self.log_area.yview(tk.END)

    def read_output(self, pipe):
        """Daphne jarayonining chiqishini o‘qish va loglarga yozish."""
        while not self.stop_logging:
            line = pipe.readline().strip()
            if line:
                self.log(line)
            time.sleep(0.1)

    def start_server(self):
        """Daphne serverini ishga tushirish."""
        if self.running:
            self.log("Server allaqachon ishlamoqda!")
            return

        self.log("Daphne serveri ishga tushirilmoqda...")
        try:
            cmd = ["daphne", "-b", "0.0.0.0", "-p", "8000", "face_recognition_project.asgi:application"]
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            self.running = True
            self.start_button.config(state='disabled')
            self.stop_button.config(state='normal')
            self.restart_button.config(state='normal')

            self.stop_logging = False
            self.log_thread = threading.Thread(target=self.read_output, args=(self.process.stdout,))
            self.log_thread.daemon = True
            self.log_thread.start()

            threading.Thread(target=self.read_output, args=(self.process.stderr,), daemon=True).start()

            self.log("Daphne serveri muvaffaqiyatli ishga tushdi.")

        except Exception as e:
            self.log(f"XATO: Serverni ishga tushirishda xatolik: {str(e)}")
            self.running = False
            self.start_button.config(state='normal')
            self.stop_button.config(state='disabled')
            self.restart_button.config(state='disabled')

    def stop_server(self):
        """Daphne serverini to‘xtatish."""
        if not self.running or self.process is None:
            self.log("Server ishlamayapti!")
            return

        self.log("Daphne serveri to‘xtatilmoqda...")
        self.stop_logging = True
        try:
            self.process.terminate()
            self.process.wait()
            self.running = False
            self.process = None
            self.log("Daphne serveri muvaffaqiyatli to‘xtatildi.")
        except Exception as e:
            self.log(f"XATO: Serverni to‘xtatishda xatolik: {str(e)}")

        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.restart_button.config(state='disabled')

    def restart_server(self):
        """Daphne serverini qayta ishga tushirish."""
        self.log("Daphne serveri qayta ishga tushirilmoqda...")
        self.stop_server()
        time.sleep(1)  # Qisqa pauza
        self.start_server()

    def on_closing(self):
        """Oynani yopishda serverni to‘xtatish."""
        if self.running:
            self.stop_server()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = DaphneGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()