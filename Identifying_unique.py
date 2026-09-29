from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QMainWindow, QMessageBox
import os
from GUI.responsive.gui_identifying_unique import Ui_Unique
import config
from tool_runner import ToolWorker, split_extra_args, tool_exists


class UniqueMain(QMainWindow, Ui_Unique):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.show()

        self.selected_unique_file = None
        self.worker_thread = None  # Placeholder for worker thread

        self.pushButton_loadfile.clicked.connect(self.load_unique_file)
        self.pushButton_run.clicked.connect(self.run_unique)

    def load_unique_file(self):
        file_filter = "All Files (*.*);;QFilter Files (*.qfilter.fa)"
        unique_file, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select File", '', file_filter)
        if unique_file:
            uniquefilename = os.path.basename(unique_file)
            print(f'\n Loaded file is: \n{uniquefilename} \n')
            self.selected_unique_file = unique_file

    def run_unique(self):
        vsearch_location = config.get_vsearch_location()
        if not tool_exists(vsearch_location):
            QMessageBox.warning(self, 'Warning',
                f'VSEARCH not found at:\n{vsearch_location}\n\nPlease set the correct path in Settings.')
            return

        if not self.global_directory:
            QMessageBox.warning(self, 'Warning', 'Please select directory from main window, then reopen this window.')
            return

        if not self.selected_unique_file:
            QMessageBox.warning(self, 'Warning', 'Please load a file')
            return

        if not self.lineEdit_outname.text():
            QMessageBox.warning(self, 'Warning', 'Please enter output file name.')
            return

        args = [
            vsearch_location,
            '--derep_fulllength', self.selected_unique_file,
            '--sizeout',
            '--output',
            os.path.join(self.global_directory, f'{self.lineEdit_outname.text()}.unique.fa'),
        ]

        if self.lineEdit_logname.text():
            args += ['--log',
                     os.path.join(self.global_directory, f'{self.lineEdit_logname.text()}.log')]
        else:
            args += ['--log',
                     os.path.join(self.global_directory, 'identify_unique.log')]

        if self.lineEdit_relabel.text():
            args += ['--relabel', self.lineEdit_relabel.text()]

        args += split_extra_args(self.textEdit_othercommand.toPlainText())

        # Create and start the worker thread to execute the command
        self.worker_thread = ToolWorker(args)
        self.worker_thread.output_signal.connect(self.print_output)
        self.worker_thread.error_signal.connect(self.print_output)
        self.worker_thread.finished_signal.connect(self.on_process_finished)
        self.worker_thread.start()

    def print_output(self, text):
        """Append command output to the console area in the GUI."""
        print(text)

    def on_process_finished(self):
        """Handle the post-process completion."""
        QMessageBox.information(self, "Success", "Unique sequence identification completed.")


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    ui = UniqueMain()
    app.exec()