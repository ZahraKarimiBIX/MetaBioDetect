from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog
import sys
from GUI.responsive.gui_setting import Ui_Settings
import config


class SettingsMain(QMainWindow, Ui_Settings):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.lineEdit_vsearch.setText(config.get_vsearch_location())
        self.lineEdit_blast.setText(config.get_blast_location())

        self.pushButton_vsearch.clicked.connect(self.browse_vsearch)
        self.pushButton_blast.clicked.connect(self.browse_blast)
        self.lineEdit_vsearch.editingFinished.connect(self.save_paths)
        self.lineEdit_blast.editingFinished.connect(self.save_paths)

        self.show()

    def browse_vsearch(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select VSEARCH executable",
            self.lineEdit_vsearch.text(),
            # "Executables (*.exe);;All files (*)"
            "All files (*)"
        )
        if path:
            self.lineEdit_vsearch.setText(path)
            self.save_paths()

    def browse_blast(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select BLAST executable",
            self.lineEdit_blast.text(),
            # "Executables (*.exe);;All files (*)"
            "All files (*)"
        )
        if path:
            self.lineEdit_blast.setText(path)
            self.save_paths()

    def save_paths(self):
        config.set_vsearch_location(self.lineEdit_vsearch.text())
        config.set_blast_location(self.lineEdit_blast.text())




if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = SettingsMain()
    sys.exit(app.exec())