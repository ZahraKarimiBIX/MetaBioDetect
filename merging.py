from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
import sys
import os
from GUI.responsive.gui_merging import Ui_Merging
import config
from tool_runner import ToolWorker, split_extra_args, tool_exists


class MergeMain(QMainWindow, Ui_Merging):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.show()

        self.selected_forward_file = None
        self.selected_reverse_file = None
        self.worker_thread = None  # Placeholder for worker thread

        self.pushButton_run.clicked.connect(self.merge)
        self.pushButton_loadforwardfile.clicked.connect(self.load_forward_file)
        self.pushButton_loadreversefile.clicked.connect(self.load_reverse_file)

    def load_forward_file(self):
        loaded_forward_file, _ = QFileDialog.getOpenFileName(self, "Select forward file")
        if loaded_forward_file:
            forwardfilename = os.path.basename(loaded_forward_file)
            print(f"\n Forward file is: \n {forwardfilename}")
            self.selected_forward_file = loaded_forward_file

    def load_reverse_file(self):
        loaded_reverse_file, _ = QFileDialog.getOpenFileName(self, "Select reverse file")
        if loaded_reverse_file:
            reversefilename = os.path.basename(loaded_reverse_file)
            print(f"\n Reverse file is: \n {reversefilename}")
            self.selected_reverse_file = loaded_reverse_file

    def merge(self):
        if not self.global_directory:
            QMessageBox.warning(self, 'Warning', 'Please select directory from main window, then reopen this window.')
            return
        if not self.selected_forward_file:
            QMessageBox.warning(self, 'Warning', 'Please select forward file.')
            return
        if not self.selected_reverse_file:
            QMessageBox.warning(self, 'Warning', 'Please select reverse file.')
            return
        if not self.lineEdit_name.text():
            QMessageBox.warning(self, 'Warning', 'Please enter output name.')
            return

        vsearch_location = config.get_vsearch_location()
        if not tool_exists(vsearch_location):
            QMessageBox.warning(self, 'Warning',
                f'VSEARCH not found at:\n{vsearch_location}\n\nPlease set the correct path in Settings.')
            return

        out_fastq = os.path.join(self.global_directory, f'{self.lineEdit_name.text()}.fastq')

        # Command built as a LIST: no quoting needed, spaces in paths are safe.
        args = [
            vsearch_location,
            '--fastq_mergepairs', self.selected_forward_file,
            '--reverse', self.selected_reverse_file,
            '--relabel', 'merged',
            '--fastqout', out_fastq,
            '--fastq_allowmergestagger',
        ]

        if self.lineEdit_max_overlap_mismatch.text():
            args += ['--fastq_maxdiffs', self.lineEdit_max_overlap_mismatch.text()]
        if self.lineEdit_min_overlap_le.text():
            args += ['--fastq_minovlen', self.lineEdit_min_overlap_le.text()]
        args += split_extra_args(self.textEdit_other_commands.toPlainText())

        print('\n merging is running \n')

        self.pushButton_run.setEnabled(False)

        self.worker_thread = ToolWorker(args)
        self.worker_thread.output_signal.connect(self.print_output)
        self.worker_thread.error_signal.connect(self.print_output)
        self.worker_thread.finished_signal.connect(self.on_merge_finished)
        self.worker_thread.start()

    def print_output(self, text):
        """Append command output to the console area."""
        print(text)

    def on_merge_finished(self):
        """Handle post-merge completion."""
        self.pushButton_run.setEnabled(True)
        QMessageBox.information(self, "Success", "Merge executed successfully.")
        print(" \n ")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = MergeMain()
    sys.exit(app.exec())