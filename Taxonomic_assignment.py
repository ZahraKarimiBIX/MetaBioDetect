from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QMainWindow, QMessageBox
import subprocess
import os
from GUI.responsive.gui_taxonomic_assignment import Ui_Taxonomic
from Taxonomy_report import ReportMain
import config
from tool_runner import split_extra_args, display_command, tool_exists


class TaxonimicMain(QMainWindow, Ui_Taxonomic):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.show()

        self.selected_asvs_file = None
        self.selected_database = None
        self.assign_file = None
        self.log_directory = None

        self.pushButton_loadfile_otu.clicked.connect(self.load_asvs_file)
        self.pushButton_loadfile_db.clicked.connect(self.load_database)
        self.pushButton_run.clicked.connect(self.run_taxonomic)

    def load_asvs_file(self):
        file_filter = "All Files (*.*);;Nochimera Files (*.nochimera.fa)"
        loaded_asvs_file, _ = QtWidgets.QFileDialog.getOpenFileName(self, "select ASVs file", '', file_filter)
        if loaded_asvs_file:
            asvfilename = os.path.basename(loaded_asvs_file)
            print(f'\n ASVs file is: \n{asvfilename}\n')
            self.selected_asvs_file = loaded_asvs_file

    def load_database(self):
        database_file, _ = QtWidgets.QFileDialog.getOpenFileName(self, "select dadabase file")
        if database_file:
            databasefilename = os.path.basename(database_file)
            print(f'\n database file is: \n{databasefilename}\n')
            self.selected_database = database_file

    def run_taxonomic(self):
        vsearch_location = config.get_vsearch_location()
        if not tool_exists(vsearch_location):
            QMessageBox.warning(self, 'Warning',
                f'VSEARCH not found at:\n{vsearch_location}\n\nPlease set the correct path in Settings.')
            return

        if not self.global_directory:
            QMessageBox.warning(self, 'Warning', 'Please select directory from main window \n then open quality filtering window again')
            return

        if not self.selected_asvs_file:
            QMessageBox.warning(self, 'Warning', 'Please load ASVs file')
            return

        if not self.selected_database:
            QMessageBox.warning(self, 'Warning', 'Please load database')
            return

        args = [
            vsearch_location,
            '--usearch_global', self.selected_asvs_file,
            '--db', self.selected_database,
        ]

        if self.lineEdit_idthreshold.text():
            args += ['--id', self.lineEdit_idthreshold.text()]
        else:
            args += ['--id', '0.97']

        args += ['--top_hits_only']

        if self.lineEdit_userfields.text():
            args += ['--userfields', self.lineEdit_userfields.text()]
        else:
            args += ['--userfields', 'query+target+qstrand+id']

        if self.lineEdit_max_target_seq.text():
            args += ['--maxaccepts', self.lineEdit_max_target_seq.text()]

        if self.lineEdit_cpu_threads.text():
            args += ['--threads', self.lineEdit_cpu_threads.text()]

        if self.lineEdit_outnameassign.text():
            self.assign_file = os.path.join(
                self.global_directory, f'{self.lineEdit_outnameassign.text()}.txt')
            args += ['--userout', self.assign_file]

        if self.lineEdit_outnameunassign.text():
            args += ['--notmatched',
                     os.path.join(self.global_directory, f'{self.lineEdit_outnameunassign.text()}.txt')]

        if self.lineEdit_logname.text():
            self.log_directory = os.path.join(
                self.global_directory, f'{self.lineEdit_logname.text()}.log')
            args += ['--log', self.log_directory]

        args += split_extra_args(self.textEdit_othercommand.toPlainText())

        print(f"Command: {display_command(args)}")

        try:
            # List of args + no shell: paths with spaces are handled safely.
            subprocess.run(args, check=True)
            print("Taxonomy assignment executed successfully.")
            if self.log_directory and self.assign_file:
                self.show_taxonomyreport_window(self.log_directory, self.assign_file)
        except FileNotFoundError:
            QMessageBox.warning(self, 'Warning',
                f'VSEARCH could not be started:\n{vsearch_location}')
        except subprocess.CalledProcessError as e:
            print(f"Error executing: {e}")

    def show_taxonomyreport_window(self, log_directory, assign_file):
        self.separate_taxonomyreport_window = TaxonomyReportWindow(log_directory, assign_file)
        self.separate_taxonomyreport_window.show()


class TaxonomyReportWindow(ReportMain):
    def __init__(self, log_directory, assign_file):
        super().__init__(log_directory, assign_file)