from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QVBoxLayout, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal
import sys
# from GUI.gui_main import Ui_MainWindow
from GUI.responsive.gui_main import Ui_MainWindow
from Adapter_trimming import AdapterMain
from Primer_trimming import PrimerMain
from Quality_filtering import QualityMain
from Identifying_unique import UniqueMain
from Detect_ASVs import AsvsMain
from merging import MergeMain
from Remove_chimeric import ChimericMain
from Taxonomic_assignment import TaxonimicMain
from Taxonomy_report import ReportMain
from blast import BlastMain
from MetaResultDB import BlastAnalysisMain
from Samples_management import SamplesMain
from blast_local import BlastLocalMain
from blast_db_management import BlastDbMain
from Detect_OTUs import OtusMain
from GUI.responsive.gui_about import Ui_About
from GUI.responsive.gui_user_guide import Ui_UserGuide
from GUI.responsive.gui_setting import Ui_Settings
from all_in_one import AllInOneMain
from Settings import SettingsMain

class OutputStream(QObject):
    newText = pyqtSignal(str)

    def write(self, text):
        self.newText.emit(text)

    def flush(self):
        pass  # No need at the moment



class MetaMain(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.show()

        

        self.selected_directory = ''
        
        self.selected_forward = ''
        self.selected_reverse = ''
        self.console_area.setReadOnly(True)


        # Redirect sys.stdout to the custom handler
        self.output_stream = OutputStream()
        self.output_stream.newText.connect(self.append_text)
        sys.stdout = self.output_stream

        self.actionSet_directory.triggered.connect(self.set_directory)
        self.actionExit.triggered.connect(self.exit)
        self.actionLoad_Forward.triggered.connect(self.set_forward)
        self.actionLoad_Reverse.triggered.connect(self.set_reverse)
        self.action1_Adaptor_Trimmimg.triggered.connect(self.show_adapter_window)
        self.action2_Primer_Trimmimg.triggered.connect(self.show_primer_window)
        self.action3_Merging_paired_end_reads.triggered.connect(self.show_merging_window)
        self.action4_Quality_filtering.triggered.connect(self.show_quality_window)
        self.action5_Identifying_uniqe_sequences.triggered.connect(self.show_unique_window)
        self.actionASV.triggered.connect(self.show_asv_window)
        self.actionOTU.triggered.connect(self.show_otu_window)
        self.action7_Remove_chimeric_reads.triggered.connect(self.show_chimeric_window)
        self.actionCustom_Database.triggered.connect(self.show_taxonomic_window)
        self.actionTaxonimy_report.triggered.connect(self.show_taxonomyreport_window)
        self.actionBlast_Online_Alignment.triggered.connect(self.show_blast_window)
        self.actionBLAST_Results_Analysis.triggered.connect(self.show_blast_analysis_window)
        self.actionSample_Management.triggered.connect(self.show_samples_window)
        self.actionBlast_Local_Alignment.triggered.connect(self.show_blastlocal_window)
        self.actionBlast_Database.triggered.connect(self.show_blastdb_window)
        self.actionRun_Full_Pipeline.triggered.connect(self.show_all_in_one_window)
        self.actionuser_guide.triggered.connect(self.show_user_guide_window)
        self.actionabout_MetaBioDetect.triggered.connect(self.show_about_window)
        self.actionSettings.triggered.connect(self.show_settings_window)


    def append_text(self, text):
        """Append captured text to the console area with proper formatting."""
        # Replace escape sequences with proper newlines
        formatted_text = text.replace(r'\r\n', '\n').replace(r'\r', '').replace(r'\n', '\n')
        
        # Add a blank line before specific phrases
        if "Processing paired-end reads" in formatted_text:
            formatted_text = '\n' + formatted_text  # Add a blank line before this line

        if "Finished in" in formatted_text:
            formatted_text = '\n' + formatted_text  # Add a blank line before this line

        cursor = self.console_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)  # Move cursor to the end
        self.console_area.setTextCursor(cursor)
        self.console_area.insertPlainText(formatted_text)
        self.console_area.ensureCursorVisible()


    # def check_directory(self):
    #     """Warn the user if no working directory has been set."""
    #     if not self.selected_directory:
    #         QMessageBox.warning(self, 'Warning', 'Please set a directory.')
    def check_directory(self):
        """Warn the user if no working directory has been set.

        Returns True if a directory is set, False otherwise.
        """
        if not self.selected_directory:
            QMessageBox.warning(self, 'Warning', 'Please set a directory.')
            return False
        return True


    def set_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Selected Directory")
        if directory:
            print(f'\n Working directory: \n {directory}')
            self.selected_directory = directory


    def set_forward(self):
        forward, _ = QFileDialog.getOpenFileName(self, "Select Forward")
        if forward:
            print(f'\n forward file is: \n{forward}')
            self.selected_forward = forward
            

    def set_reverse(self):
        reverse, _ = QFileDialog.getOpenFileName(self, "Select Reverse")
        if reverse:
            print(f'\n reverse file is: \n{reverse}')
            self.selected_reverse = reverse



    def exit(self):
        QApplication.quit()

    

    def show_primer_window(self):
        if not self.check_directory():
            return
        self.separate_primer_window = PrimerWindow(self.selected_directory, self.selected_forward, self.selected_reverse)
        self.separate_primer_window.show()


    def show_adapter_window(self):
        if not self.check_directory():
            return
        self.separate_adapter_window = AdapterWindow(self.selected_directory, self.selected_forward, self.selected_reverse)
        self.separate_adapter_window.show()

    def show_merging_window(self):
        if not self.check_directory():
            return
        self.separate_merging_window = MergingWindow(self.selected_directory, self.selected_forward, self.selected_reverse)
        self.separate_merging_window.show()


    def show_quality_window(self):
        if not self.check_directory():
            return
        self.separate_quality_window = QualityWindow(self.selected_directory)
        self.separate_quality_window.show()

    def show_unique_window(self):
        if not self.check_directory():
            return
        self.separate_unique_window = UniqueWindow(self.selected_directory)
        self.separate_unique_window.show()

    def show_asv_window(self):
        if not self.check_directory():
            return
        self.separate_asv_window = AsvWindow(self.selected_directory)
        self.separate_asv_window.show()

    def show_otu_window(self):
        if not self.check_directory():
            return
        self.separate_otu_window = OtuWindow(self.selected_directory)
        self.separate_otu_window.show()

    def show_chimeric_window(self):
        if not self.check_directory():
            return
        self.separate_chimeric_window = ChimericWindow(self.selected_directory)
        self.separate_chimeric_window.show()

    def show_taxonomic_window(self):
        if not self.check_directory():
            return
        self.separate_Taxonomic_window = TaxonomicWindow(self.selected_directory)
        self.separate_Taxonomic_window.show()

    def show_taxonomyreport_window(self):
        self.separate_taxonomyreport_window = TaxonomyReportWindow()
        self.separate_taxonomyreport_window.show()

    def show_blast_window(self):
        if not self.check_directory():
            return
        self.separate_blast_window = BlastWindow(self.selected_directory)
        self.separate_blast_window.show()

    def show_blast_analysis_window(self):
        self.separate_blast_analysis_window = BlastAnalysisWindow(self.selected_directory)
        self.separate_blast_analysis_window.show()

    def show_samples_window(self):
        self.separate_samples_window = SamplesWindow(self.selected_directory)
        self.separate_samples_window.show()

    def show_blastlocal_window(self):
        if not self.check_directory():
            return
        self.separate_samples_window = BlastLocalMainWindow(self.selected_directory)
        self.separate_samples_window.show()

    def show_blastdb_window(self):
        self.separate_samples_window = BlastDbMainWindow(self.selected_directory)
        self.separate_samples_window.show()

    def show_all_in_one_window(self):
        if not self.check_directory():
            return
        self.separate_samples_window = AllInOneMainWindow(self.selected_directory)
        self.separate_samples_window.show()

    def show_about_window(self):
        self.about_window = AboutWindow()
        self.about_window.show()

    def show_user_guide_window(self):
        self.user_guide_window = UserGuideWindow()
        self.user_guide_window.show()


    def show_settings_window(self):
        self.settings_window = SettingsMain()



    def closeEvent(self, event):
        """Close all related windows when the main window is closed."""

        # Close every window owned/stored by MetaMain
        for name, obj in list(self.__dict__.items()):
            if name == "output_stream":
                continue

            if isinstance(obj, QMainWindow) and obj is not self:
                try:
                    obj.close()
                except Exception:
                    pass

        # Restore stdout before exiting
        sys.stdout = sys.__stdout__

        event.accept()



class AdapterWindow(AdapterMain):
    def __init__(self, directory, forward, reverse):
        super().__init__()
        self.global_directory = directory
        self.global_forward_file = forward
        self.global_reverse_file = reverse



class PrimerWindow(PrimerMain):
    def __init__(self, directory, forward, reverse):
        super().__init__()
        self.global_directory = directory
        self.global_forward_file = forward
        self.global_reverse_file = reverse



class MergingWindow(MergeMain):
    def __init__(self, directory, forward, reverse):
        super().__init__()
        self.global_directory = directory
        self.global_forward_file = forward
        self.global_reverse_file = reverse



class QualityWindow(QualityMain):
    def __init__(self, directory):
        super().__init__()
        self.global_directory = directory



class UniqueWindow(UniqueMain):
    def __init__(self, directory):
        super().__init__()
        self.global_directory = directory



class AsvWindow(AsvsMain):
    def __init__(self, directory):
        super().__init__()
        self.global_directory = directory



class OtuWindow(OtusMain):
    def __init__(self, directory):
        super().__init__()
        self.global_directory = directory



class ChimericWindow(ChimericMain):
    def __init__(self, directory):
        super().__init__()
        self.global_directory = directory



class TaxonomicWindow(TaxonimicMain):
    def __init__(self, directory):
        super().__init__()
        self.global_directory = directory


class TaxonomyReportWindow(ReportMain):
    def __init__(self):
        super().__init__()


class BlastWindow(BlastMain):
    def __init__(self, directory):
        super().__init__()
        self.global_directory = directory

class BlastAnalysisWindow(BlastAnalysisMain):
    def __init__(self, directory):
        super().__init__()
        self.global_directory = directory

class SamplesWindow(SamplesMain):
    def __init__(self, directory):
        super().__init__()
        self.global_directory = directory

class BlastLocalMainWindow(BlastLocalMain):
    def __init__(self, directory):
        super().__init__()
        self.global_directory = directory

class BlastDbMainWindow(BlastDbMain):
    def __init__(self, directory):
        super().__init__()
        self.global_directory = directory

class AllInOneMainWindow(AllInOneMain):
    def __init__(self, directory):
        super().__init__()
        self.global_directory = directory

class AboutWindow(QMainWindow, Ui_About):
    def __init__(self):
        super().__init__()
        self.setupUi(self)


class UserGuideWindow(QMainWindow, Ui_UserGuide):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

class SettingsWindow(QMainWindow, Ui_Settings):
    def __init__(self):
        super().__init__()
        self.setupUi(self)


def configure_platform_ui(app):

    if sys.platform == "darwin":
        app.setStyle("Fusion")

        app.setStyleSheet("""
            QWidget {
                font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
                font-size: 13px;
            }

            QLabel {
                font-size: 13px;
            }

            QLineEdit,
            QComboBox,
            QSpinBox,
            QDoubleSpinBox {
                min-height: 34px;
                padding: 4px 8px;
                font-size: 14px;
                border: 1px solid #b8b8b8;
                border-radius: 6px;
                background-color: white;
            }

            QLineEdit:focus,
            QComboBox:focus,
            QSpinBox:focus,
            QDoubleSpinBox:focus {
                border: 1px solid #5a9bd5;
            }

            QPushButton {
                min-height: 34px;
                min-width: 90px;
                padding: 5px 16px;
                font-size: 13px;
                border: 1px solid #b8b8b8;
                border-radius: 6px;
                background-color: #f7f7f7;
            }

            QPushButton:hover {
                background-color: #eeeeee;
            }

            QPushButton:pressed {
                background-color: #dddddd;
            }

            QTextEdit,
            QPlainTextEdit {
                padding: 8px;
                font-size: 13px;
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                background-color: white;
            }

            QCheckBox,
            QRadioButton {
                font-size: 13px;
                spacing: 6px;
            }
        """)

    elif sys.platform == "win32":
        pass




if __name__ == "__main__":
    app = QApplication(sys.argv)
    configure_platform_ui(app)
    ui = MetaMain()
    exit_code = app.exec()
    sys.stdout = sys.__stdout__
    sys.exit(exit_code)