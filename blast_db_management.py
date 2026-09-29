import sys
import os
import locale
import json
import urllib.request
import tarfile

from PyQt6 import QtCore
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox,
    QLabel, QFrame, QVBoxLayout, QWidget,
    QHBoxLayout, QPushButton, QSpacerItem,
    QSizePolicy, QFileDialog
)
from PyQt6.QtCore import Qt

from GUI.responsive.gui_blast_database import Ui_blastdb


locale.setlocale(locale.LC_ALL, '')  # For localized number formatting


def prettify_key(key: str) -> str:
    return key.replace('-', ' ').title()


def format_value(key, value):
    if isinstance(value, int):
        return locale.format_string("%d", value, grouping=True)
    return str(value)


class BlastDbWorker(QtCore.QThread):
    output_signal = QtCore.pyqtSignal(str)
    error_signal = QtCore.pyqtSignal(str)
    finished_signal = QtCore.pyqtSignal()

    def __init__(self, file_url: str, target_directory: str):
        super().__init__()
        self.file_url = file_url
        self.target_directory = target_directory

    def run(self):
        if not os.path.isdir(self.target_directory):
            self.error_signal.emit(f"Target directory does not exist:\n{self.target_directory}")
            self.finished_signal.emit()
            return

        try:
            filename = os.path.basename(self.file_url)
            save_path = os.path.join(self.target_directory, filename)

            self.output_signal.emit(f"Starting download: {filename}")
            urllib.request.urlretrieve(self.file_url, save_path)
            self.output_signal.emit(f"Download complete: {save_path}")

            if filename.endswith(".tar.gz"):
                self.output_signal.emit("Extracting archive...")
                try:
                    with tarfile.open(save_path, "r:gz") as tar:
                        tar.extractall(path=self.target_directory)
                    self.output_signal.emit(f"Extraction complete in:\n{self.target_directory}")
                    os.remove(save_path)
                except Exception as e:
                    self.error_signal.emit(f"Failed to extract archive:\n{str(e)}")

        except Exception as e:
            self.error_signal.emit(f"Download failed:\n{str(e)}")

        self.finished_signal.emit()


class BlastDbMain(QMainWindow, Ui_blastdb):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.show()

        self.db_metadata = []
        self.selected_directory = None
        self.worker_thread = None

        self.pushButton_DatabasePath.clicked.connect(self.set_path)
        self.comboBox_DB_Names.currentIndexChanged.connect(self.show_db_details)

        self.load_dbnames_from_json()

    def load_dbnames_from_json(self):
        url = "https://ftp.ncbi.nlm.nih.gov/blast/db/blastdb-metadata-1-1.json"
        try:
            with urllib.request.urlopen(url) as response:
                data = response.read()
                self.db_metadata = json.loads(data)

            self.comboBox_DB_Names.clear()
            for entry in self.db_metadata:
                dbname = entry.get("dbname")
                if dbname:
                    self.comboBox_DB_Names.addItem(dbname)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load DB names:\n{str(e)}")

    def show_db_details(self, index):
        if index < 0 or index >= len(self.db_metadata):
            return

        entry = self.db_metadata[index]

        # Clear old content in scrollArea
        current_widget = self.scrollArea.widget()
        if current_widget:
            current_widget.deleteLater()

        # Main details frame
        details_frame = QFrame()
        details_layout = QVBoxLayout(details_frame)

        keys_to_show = [
            "version",
            "dbtype",
            "description",
            "number-of-letters",
            "number-of-sequences",
            "last-updated",
            "bytes-total",
            "bytes-to-cache",
            "number-of-volumes",
            "bytes-total-compressed"
        ]

        for key in keys_to_show:
            value = entry.get(key)
            if value is not None:
                label = QLabel(f"<b>{prettify_key(key)}:</b> {format_value(key, value)}")
                label.setWordWrap(True)
                details_layout.addWidget(label)

        # Files frame
        files_frame = QFrame()
        files_layout = QVBoxLayout(files_frame)
        files_label = QLabel("<b>Files:</b>")
        files_layout.addWidget(files_label)

        files = entry.get("files", [])
        if files:
            for file_url in files:
                line_widget = QWidget()
                line_layout = QHBoxLayout(line_widget)
                line_layout.setContentsMargins(0, 0, 0, 0)

                file_label = QLabel(file_url)
                file_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                line_layout.addWidget(file_label)

                spacer = QSpacerItem(20, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
                line_layout.addItem(spacer)

                download_button = QPushButton("Download")
                download_button.clicked.connect(self.downloader)
                download_button.setProperty("file_url", file_url)
                line_layout.addWidget(download_button)

                files_layout.addWidget(line_widget)

                # Horizontal line separator
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setFrameShadow(QFrame.Shadow.Sunken)
                files_layout.addWidget(separator)
        else:
            files_layout.addWidget(QLabel("No files available."))

        # Container widget for scrollArea
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(details_frame)
        container_layout.addWidget(files_frame)
        container_layout.addStretch()

        self.scrollArea.setWidget(container)

    def set_path(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory", "")
        if directory:
            self.selected_directory = directory

    def downloader(self):
        sender = self.sender()
        if not sender:
            QMessageBox.warning(self, "Warning", "Download button sender not found.")
            return

        file_url = sender.property("file_url")
        if not file_url:
            QMessageBox.warning(self, "Warning", "No file URL associated with this button.")
            return

        if not self.selected_directory:
            QMessageBox.warning(self, "Warning", "Please select a directory first.")
            return

        if not os.path.isdir(self.selected_directory):
            QMessageBox.warning(self, "Warning", f"Selected directory does not exist:\n{self.selected_directory}")
            return

        # Save reference to the current button so we can update its text
        self.current_download_button = sender
        self.current_download_button.setText("Downloading...")
        self.current_download_button.setEnabled(False)

        # Disable other UI elements if needed
        self.pushButton_DatabasePath.setEnabled(False)
        self.comboBox_DB_Names.setEnabled(False)

        self.worker_thread = BlastDbWorker(file_url, self.selected_directory)

        self.worker_thread.output_signal.connect(self.print_output)
        self.worker_thread.error_signal.connect(lambda msg: QMessageBox.critical(self, "Error", msg))
        self.worker_thread.finished_signal.connect(self.on_download_finished)

        self.worker_thread.start()


    def print_output(self, text):
        # For now just print; replace with logging or append to a GUI text widget if desired
        print(text)

    def on_download_finished(self):        
        # Reset the button text and enable it
        if hasattr(self, "current_download_button") and self.current_download_button:
            self.current_download_button.setText("Download")
            self.current_download_button.setEnabled(True)
            self.current_download_button = None

        self.pushButton_DatabasePath.setEnabled(True)
        self.comboBox_DB_Names.setEnabled(True)
        self.worker_thread = None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BlastDbMain()
    sys.exit(app.exec())
