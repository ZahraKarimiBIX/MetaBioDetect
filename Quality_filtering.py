from PyQt6.QtWidgets import QMainWindow, QMessageBox, QFileDialog, QApplication
from PyQt6.QtCore import QThread, pyqtSignal
import os
import sys
import contextlib
import logging
import traceback
from GUI.responsive.gui_quality_filtering import Ui_Quality

try:
    from cutadapt.cli import main as cutadapt_main   # cutadapt >= 4.x
except ImportError:
    from cutadapt.__main__ import main as cutadapt_main  # older versions


class _EmittingStream:
    """File-like object: collects everything and emits complete lines via a signal."""

    def __init__(self, emit_func):
        self.emit_func = emit_func
        self.collected = []
        self._partial = ''

    def write(self, text):
        self.collected.append(text)
        self._partial += text
        while '\n' in self._partial:
            line, self._partial = self._partial.split('\n', 1)
            self.emit_func(line)

    def flush(self):
        pass

    def isatty(self):
        return False   # not a terminal, so cutadapt skips the interactive progress bar

    def getvalue(self):
        return ''.join(self.collected)


class QualityWorker(QThread):
    output_signal = pyqtSignal(str)  # Signal to send output to the GUI
    error_signal = pyqtSignal(str)   # Signal to send errors to the GUI
    finished_signal = pyqtSignal()   # Signal to notify completion

    def __init__(self, args, log_file=None, relabel_prefix='', output_path=None):
        super().__init__()
        self.args = args
        self.log_file = log_file
        self.relabel_prefix = relabel_prefix
        self.output_path = output_path

    def run(self):
        # Nothing may escape run(): PyQt6 aborts the whole app on unhandled
        # exceptions in a thread, so report crashes through the error signal.
        try:
            self._run_impl()
        except BaseException:
            self.error_signal.emit(f"Worker crashed:\n{traceback.format_exc()}")
            self.finished_signal.emit()

    def _run_impl(self):
        """Run cutadapt in-process in a separate thread.

        IMPORTANT: sys.stdout is NOT redirected here. The main window already
        replaces sys.stdout with its GUI OutputStream; redirecting it again
        process-wide made the print_output slot write back into this worker's
        stream, re-emitting the signal in the main thread -> infinite
        recursion -> 'Unhandled Python exception'. Instead, cutadapt's report
        (which goes through Python logging) is captured by attaching our own
        logging handler to the stream. stdout stays untouched, so plain
        print() everywhere still reaches the GUI console safely.
        """
        stream = _EmittingStream(self.output_signal.emit)
        exit_ok = True

        # Remove stale handlers (from earlier cutadapt runs in other windows),
        # then install our own handler so the report flows into our stream.
        for h in logging.root.handlers[:]:
            logging.root.removeHandler(h)
        handler = logging.StreamHandler(stream)
        logging.root.addHandler(handler)
        logging.root.setLevel(logging.INFO)

        try:
            # stderr only (argparse/usage errors); stdout is left alone.
            with contextlib.redirect_stderr(stream):
                cutadapt_main(self.args)
        except SystemExit as e:
            exit_ok = e.code in (0, None)
        except Exception as e:
            exit_ok = False
            self.error_signal.emit(f"Exception: {str(e)}")
        finally:
            # Leave logging clean so the next step starts fresh.
            logging.root.removeHandler(handler)

        # vsearch-style relabel (>prefix1, >prefix2, ...) done here, because
        # cutadapt's --rename has no sequential-counter variable.
        if exit_ok and self.relabel_prefix and self.output_path:
            try:
                self._relabel_fasta(self.output_path, self.relabel_prefix)
            except Exception as e:
                exit_ok = False
                self.error_signal.emit(f"Relabelling failed: {e}")

        if exit_ok:
            self.output_signal.emit("Quality filtering executed successfully.")
        else:
            self.error_signal.emit("Error during quality filtering")

        # Write the same report to the log file
        if self.log_file:
            try:
                with open(self.log_file, 'w', encoding='utf-8') as fh:
                    fh.write(stream.getvalue())
            except Exception as e:
                self.error_signal.emit(f"Could not write log file: {str(e)}")
        self.finished_signal.emit()  # Notify GUI that processing is complete

    @staticmethod
    def _relabel_fasta(path, prefix):
        """Rewrite FASTA headers as >prefix1, >prefix2, ... (like vsearch --relabel)."""
        tmp = path + '.tmp'
        n = 0
        with open(path, 'r', encoding='utf-8') as src, open(tmp, 'w', encoding='utf-8') as dst:
            for line in src:
                if line.startswith('>'):
                    n += 1
                    dst.write(f'>{prefix}{n}\n')
                else:
                    dst.write(line)
        os.replace(tmp, path)


class QualityMain(QMainWindow, Ui_Quality):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.show()

        self.selected_merged_file = None
        self.worker_thread = None  # Placeholder for worker thread

        self.pushButton_3.clicked.connect(self.load_merged_file)
        self.pushButton.clicked.connect(self.run_quality)

    def load_merged_file(self):
        merged_file, _ = QFileDialog.getOpenFileName(self, "Select Merged File")
        if merged_file:
            mergedfilename = os.path.basename(merged_file)
            print(f'\n Merged file is: \n{mergedfilename}')
            self.selected_merged_file = merged_file

    def run_quality(self):
        print('\n quality filtering is running ... ')

        if not self.global_directory:
            QMessageBox.warning(self, 'Warning', 'Please select directory from main window, then reopen this window.')
            return

        if not self.selected_merged_file:
            QMessageBox.warning(self, 'Warning', 'Please load a merged file.')
            return

        args = []

        data_mapping = [
            (self.lineEdit_maxee.text(), '--max-expected-errors'),   # was --fastq_maxee
            (self.lineEdit_maxlength.text(), '--maximum-length'),    # was --fastq_maxlen
            (self.lineEdit_minlength.text(), '--minimum-length'),    # was --fastq_minlen
            (self.lineEdit_max_N_base.text(), '--max-n'),            # was --fastq_maxns
            (self.lineEdit_min_quality.text(), '--quality-cutoff'),  # was --fastq_qmin
        ]

        for data, flag in data_mapping:
            if data:
                args += [flag, data]

        if self.textEdit_othercommand.toPlainText():
            args += self.textEdit_othercommand.toPlainText().split()

        # Output format is decided by the file extension (.fa -> FASTA, .fastq -> FASTQ)
        if self.lineEdit_outname.text():
            output_path = f'{self.global_directory}/{self.lineEdit_outname.text()}.qfilter.fa'
            args += ['--output', output_path]
        else:
            QMessageBox.warning(self, 'Warning', 'Please enter an output file name.')
            return

        # Input file must come after the options (positional argument)
        args.append(self.selected_merged_file)

        # cutadapt's report goes through logging, the worker tees it to this file
        if self.lineEdit_logname.text():
            log_name = self.lineEdit_logname.text()
        else:
            log_name = f'{self.lineEdit_outname.text()}_quality'
        log_path = f'{self.global_directory}/{log_name}.log'

        # Create and start the worker thread.
        # Relabelling is NOT passed to cutadapt (--rename has no sequential
        # counter variable); the worker rewrites the headers itself afterwards.
        self.worker_thread = QualityWorker(
            args, log_path,
            relabel_prefix=self.lineEdit_relabel.text(),
            output_path=output_path,
        )
        self.worker_thread.output_signal.connect(self.print_output)
        self.worker_thread.error_signal.connect(self.print_output)
        self.worker_thread.finished_signal.connect(self.on_process_finished)
        self.worker_thread.start()

    def print_output(self, text):
        """Append command output to the GUI console (via the main window's stdout hook)."""
        print(text)

    def on_process_finished(self):
        """Handle post-process completion."""
        QMessageBox.information(self, "Success", "Quality filtering executed successfully.")

    def on_process_error(self, error_message):
        """Handle error messages."""
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_message}")
        print(error_message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = QualityMain()
    sys.exit(app.exec())