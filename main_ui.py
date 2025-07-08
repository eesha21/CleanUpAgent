from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QFileDialog, QFrame, QTextEdit, QProgressBar, QInputDialog
)
from PySide6.QtCore import QThread, Signal, QObject, Qt
import sys
import os

from agent1_duplicates import run_agent1
from agent2_heavy_files import run_agent2
from agent3_whatsapp_backup import run_agent3

def get_adb_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'adb', 'adb.exe')
    else:
        return os.path.join(os.path.dirname(__file__), 'adb', 'adb.exe')

class AgentWorker(QObject):
    finished = Signal(str)
    progress = Signal(int)
    status = Signal(str)

    def __init__(self, agent_function):
        super().__init__()
        self.agent_function = agent_function

    def run(self):
        logs = self.agent_function(self.progress.emit, self.status.emit)
        self.finished.emit(logs)

class GDriveCleanerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.threads = []

        self.adb_path = get_adb_path()
        self.db_path = "/sdcard/Android/media/com.whatsapp/WhatsApp/Backups/Databases"
        self.media_path = "/sdcard/Android/media/com.whatsapp/WhatsApp/Media"

        self.setWindowTitle("📦 GDrive Space Fixer")
        self.setGeometry(100, 100, 700, 600)
        self.setStyleSheet("""
            QWidget {
                background-color: #032539;
                color: #FBF3F2;
                font-family: Arial, sans-serif;
                font-size: 16px;
            }
            QPushButton {
                background-color: #1C768F;
                border-radius: 12px;
                padding: 12px;
                color: white;
            }
            QPushButton:hover {
                background-color: #FA991C;
            }
            QLabel#titleLabel {
                font-size: 24px;
                font-weight: bold;
                color: #FA991C;
            }
            QLabel#statusLabel {
                font-size: 15px;
                color: #FBF3F2;
            }
            QTextEdit {
                background-color: #FBF3F2;
                color: #032539;
                border-radius: 10px;
                padding: 10px;
                font-size: 14px;
            }
        """)

        layout = QVBoxLayout()

        title = QLabel("📦 GDrive Space Fixer")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.button1 = QPushButton("🧹 Remove Duplicate Images")
        self.button1.clicked.connect(self.run_agent1)
        layout.addWidget(self.button1)

        self.button2 = QPushButton("📤 Move & Compress Heavy Files to USB")
        self.button2.clicked.connect(self.pick_folder_and_run_agent2)
        layout.addWidget(self.button2)

        # Hidden by default → Shown only when Agent 3 is triggered
        self.db_button = QPushButton("📄 Set WhatsApp DB Path")
        self.db_button.clicked.connect(self.set_db_path)
        self.db_button.hide()
        layout.addWidget(self.db_button)

        self.media_button = QPushButton("🖼 Set WhatsApp Media Path")
        self.media_button.clicked.connect(self.set_media_path)
        self.media_button.hide()
        layout.addWidget(self.media_button)

        self.button3 = QPushButton("📱 WhatsApp Backup Shrinker")
        self.button3.clicked.connect(self.prepare_and_run_agent3)
        layout.addWidget(self.button3)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: #1C768F;")
        layout.addWidget(separator)

        self.status_label = QLabel("🚀 Ready.")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.setLayout(layout)

    def append_log(self, text, color="#032539"):
        self.log_output.append(f'<span style="color:{color};">{text}</span>')

    def update_status(self, text):
        self.status_label.setText(text)

    def update_progress(self, value):
        self.progress.setValue(value)

    def run_agent1(self):
        self.append_log("🔍 Starting Agent 1...", "#1C768F")
        self.update_status("🧹 Running Agent 1...")
        self.start_thread(lambda p, s: run_agent1(), self.handle_agent1_result)

    def pick_folder_and_run_agent2(self):
        folder = QFileDialog.getExistingDirectory(self, "Select USB Folder")
        if folder:
            self.append_log(f"📂 Selected Folder: {folder}", "#1C768F")
            self.update_status("📤 Running Agent 2...")
            self.start_thread(lambda p, s: run_agent2(folder, p, s), self.handle_agent2_result)

    def set_db_path(self):
        text, ok = QInputDialog.getText(self, "Enter WhatsApp DB Path", "Example: /sdcard/Android/media/com.whatsapp/WhatsApp/Backups/Databases", text=self.db_path)
        if ok and text:
            self.db_path = text
            self.append_log(f"📄 DB Path set: {self.db_path}", "#1C768F")

    def set_media_path(self):
        text, ok = QInputDialog.getText(self, "Enter WhatsApp Media Path", "Example: /sdcard/Android/media/com.whatsapp/WhatsApp/Media", text=self.media_path)
        if ok and text:
            self.media_path = text
            self.append_log(f"🖼 Media Path set: {self.media_path}", "#1C768F")

    def prepare_and_run_agent3(self):
        self.db_button.show()
        self.media_button.show()
        self.append_log("🔄 Starting Agent 3...", "#1C768F")
        self.update_status("📱 Running Agent 3...")
        self.start_thread(lambda p, s: run_agent3(self.adb_path, self.db_path, self.media_path, p, s), self.handle_agent3_result)

    def start_thread(self, function, callback):
        thread = QThread(self)
        worker = AgentWorker(function)
        worker.moveToThread(thread)

        worker.progress.connect(self.update_progress)
        worker.status.connect(self.update_status)

        thread.started.connect(worker.run)
        worker.finished.connect(callback)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self.threads.append(thread)
        self.threads.append(worker)

        thread.start()

    def handle_agent1_result(self, logs):
        self.append_log("✅ Agent 1 Completed.", "#FA991C")
        self.append_log(logs, "#032539")
        self.update_status("✅ Done.")
        self.progress.setValue(100)

    def handle_agent2_result(self, logs):
        self.append_log("✅ Agent 2 Completed.", "#FA991C")
        self.append_log(logs, "#032539")
        self.update_status("✅ Done.")
        self.progress.setValue(100)

    def handle_agent3_result(self, logs):
        self.append_log("✅ Agent 3 Completed.", "#FA991C")
        self.append_log(logs, "#032539")
        self.update_status("✅ Done.")
        self.progress.setValue(100)
        self.db_button.hide()
        self.media_button.hide()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GDriveCleanerApp()
    window.show()
    sys.exit(app.exec())
