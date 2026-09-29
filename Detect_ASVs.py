from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QMainWindow, QMessageBox
import os
from GUI.responsive.gui_detect_asv import Ui_ASV
import config
from tool_runner import ToolWorker, split_extra_args, tool_exists


class AsvsMain(QMainWindow, Ui_ASV):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.show()

        self.selected_file = None
        self.worker_thread = None  # Placeholder for worker thread

        self.pushButton_loadfile.clicked.connect(self.load_file)
        self.pushButton_run.clicked.connect(self.run_asv)

    def load_file(self):
        file_filter = "All Files (*.*);;Unique Files (*.unique.fa)"
        loaded_file, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select File", '', file_filter)
        if loaded_file:
            filename = os.path.basename(loaded_file)
            print(f'\n Loaded file is: \n {filename} \n')
            self.selected_file = loaded_file

    def run_asv(self):
        vsearch_location = config.get_vsearch_location()
        if not tool_exists(vsearch_location):
            QMessageBox.warning(self, 'Warning',
                f'VSEARCH not found at:\n{vsearch_location}\n\nPlease set the correct path in Settings.')
            return

        if not self.global_directory:
            QMessageBox.warning(self, 'Warning', 'Please select directory from main window, then reopen this window.')
            return

        if not self.selected_file:
            QMessageBox.warning(self, 'Warning', 'Please load a file')
            return

        args = [vsearch_location, '--cluster_unoise', self.selected_file]

        if self.lineEdit_outname.text():
            args += ['--centroids',
                     os.path.join(self.global_directory, f'{self.lineEdit_outname.text()}.asv.fa')]

        if self.lineEdit_logname.text():
            args += ['--log',
                     os.path.join(self.global_directory, f'{self.lineEdit_logname.text()}.log')]
        else:
            args += ['--log',
                     os.path.join(self.global_directory, 'detect_asv.log')]

        if self.lineEdit_relabel.text():
            args += ['--relabel', self.lineEdit_relabel.text()]

        if self.lineEdit_minsize.text():
            args += ['--minsize', self.lineEdit_minsize.text()]

        size_mode = self.comboBox_size_mode.currentText()
        if size_mode == "Size_out":
            args += ['--sizeout']
        elif size_mode == "Size_out and Size_in":
            args += ['--sizein', '--sizeout']

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
        """Handle post-process completion."""
        QMessageBox.information(self, "Success", "ASV detection completed successfully.")


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    ui = AsvsMain()
    app.exec()