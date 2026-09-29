from PyQt6.QtWidgets import QMainWindow, QApplication, QMessageBox, QFileDialog
from PyQt6.QtCore import QThread, pyqtSignal
import subprocess
import sys
import os
import io
import contextlib
import logging
from GUI.responsive.gui_adapter_trimming import Ui_Adapter


try:
    from cutadapt.cli import main as cutadapt_main   # cutadapt >= 4.x
except ImportError:
    from cutadapt.__main__ import main as cutadapt_main  # older versions


class AdapterWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, args):          # now takes a list of args, not a command string
        super().__init__()
        self.args = args


    def run(self):
        buffer = io.StringIO()
        # Remove stale log handlers so cutadapt re-attaches to this run's buffer
        for h in logging.root.handlers[:]:
            logging.root.removeHandler(h)
        try:
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                cutadapt_main(self.args)
            self.finished.emit(buffer.getvalue())
        except SystemExit as e:
            if e.code in (0, None):
                self.finished.emit(buffer.getvalue())
            else:
                self.error.emit(buffer.getvalue())
        except Exception as e:
            self.error.emit(f"{buffer.getvalue()}\n{e}")




class AdapterMain(QMainWindow, Ui_Adapter):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.show()

        self.selected_forward_file = None
        self.selected_reverse_file = None

        self.pushButton_loadforwardfile.clicked.connect(self.load_forward_file)
        self.pushButton_loadreversefile.clicked.connect(self.load_reverse_file)
        self.pushButton_run.clicked.connect(self.run_adapter)

    def load_forward_file(self):
        loaded_forward_file, _ = QFileDialog.getOpenFileName(self, "Select forward file")
        if loaded_forward_file:
            forwardfilename = os.path.basename(loaded_forward_file)
            print(f"\n Forward file is: \n {forwardfilename}")
            # self.label_filenameforward.setText(forwardfilename)
            self.selected_forward_file = loaded_forward_file

    def load_reverse_file(self):
        loaded_reverse_file, _ = QFileDialog.getOpenFileName(self, "Select reverse file")
        if loaded_reverse_file:
            reversefilename = os.path.basename(loaded_reverse_file)
            print(f"\n Reverse file is: \n {reversefilename}")
            # self.label_filenamereverse.setText(reversefilename)
            self.selected_reverse_file = loaded_reverse_file


    def run_adapter(self):
        print('\n adapter trimming is running...')

        args = []

        data_mapping = [
            (self.lineEdit_forward.text(), '-a'),
            (self.lineEdit_reverse.text(), '-A'),
            (self.lineEdit_min.text(), '-m'),
            (self.lineEdit_quality.text(), '-q'),
            (self.lineEdit_max.text(), '--max-n'),
            (self.lineEdit_overlap.text(), '--overlap'),
            (self.lineEdit_error.text(), '--error-rate'),
        ]

        for data, flag in data_mapping:
            if data:
                args += [flag, data]

        if self.global_directory:
            name = self.lineEdit_outputname.text()
            args += ['-o', f'{self.global_directory}/{name}.out.1.fastq']
            args += ['-p', f'{self.global_directory}/{name}.out.2.fastq']
        else:
            QMessageBox.warning(self, 'Warning', 'Please select directory from main window, then reopen this window.')
            return

        if self.radioButton_yes.isChecked():
            args.append('--discard-untrimmed')

        if self.textEdit_othercommand.toPlainText():
            args += self.textEdit_othercommand.toPlainText().split()

        if self.selected_forward_file and self.selected_reverse_file:
            args += [self.selected_forward_file, self.selected_reverse_file]
        else:
            QMessageBox.warning(self, 'Warning', 'Please load forward and reverse files')
            return

        self.worker = AdapterWorker(args)
        self.worker.finished.connect(self.on_process_finished)
        self.worker.error.connect(self.on_process_error)
        self.worker.start()

        
    def on_process_finished(self, output):
        QMessageBox.information(self, "Success", "Adapter trimming executed successfully.")
        print(output)

    def on_process_error(self, error_message):
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_message}")
        print(error_message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = AdapterMain()
    sys.exit(app.exec())
