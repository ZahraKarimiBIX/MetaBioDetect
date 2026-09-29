from PyQt6.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QFileDialog
from PyQt6.QtGui import QStandardItemModel, QStandardItem
import sys
import re
import csv
import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from GUI.responsive.gui_taxonomy_reports import Ui_ReportWindow


class MatplotlibCanvas(FigureCanvas):
    def __init__(self, parent=None, width=10, height=6, dpi=100):
        self.figure = plt.figure(figsize=(5, 4), dpi=100)
        super().__init__(self.figure)
        self.setParent(parent)



class ReportMain(QMainWindow, Ui_ReportWindow):
    def __init__(self, log_directory=None, assign_file=None):
        super().__init__()
        self.setupUi(self)
        self.log_directory = log_directory
        self.assign_file = assign_file
        self.show()



        self.actionLoad_log_file.triggered.connect(self.load_log_file)
        self.actionLoad_assigned_taxominy.triggered.connect(self.load_assigned_file)

        
        self.actionSave_as_csv.triggered.connect(self.save_csv) 
        self.actionSave_TopGenus.triggered.connect(self.save_genus_plot)
        self.actionSave_TopSpecies.triggered.connect(self.save_species_plot)




        # Initialize Matplotlib canvas with genus dimensions
        self.canvas = MatplotlibCanvas(self.frame_topgenusplot, width=8, height=5, dpi=100)
        layout = QVBoxLayout(self.frame_topgenusplot)
        layout.addWidget(self.canvas)

        # Initialize Matplotlib canvas with specific dimensions
        self.canvas_species = MatplotlibCanvas(self.frame_topspeciesplot, width=8, height=5, dpi=100)
        layout_species = QVBoxLayout(self.frame_topspeciesplot)
        layout_species.addWidget(self.canvas_species)

        # Analyze data and update GUI
        # self.analysis_assigned()
        # self.update_summary()
        # check if get input from taxonomic windows then run analysis and update summary functions
        # log_directory=None, assign_file=None
        if log_directory is not None or assign_file is not None:
            self.analysis_assigned()
            self.update_summary()


    def load_log_file(self):
        loaded_log_file, _ = QFileDialog.getOpenFileName(self, "select log file")
        if loaded_log_file:
            logfilename = os.path.basename(loaded_log_file)
            print(f'\n Log file is: \n{logfilename}')
            self.log_directory = loaded_log_file
            self.update_summary()
    
    def load_assigned_file(self):
        loaded_assigned_file, _ = QFileDialog.getOpenFileName(self, "select assigned file")
        if loaded_assigned_file:
            assignedfilename = os.path.basename(loaded_assigned_file)
            print(f'\n Assigned file is: \n{assignedfilename}')
            self.assign_file = loaded_assigned_file
            self.analysis_assigned()


    def update_summary(self):
        assigned, unassigned, assigned_percentage, unassigned_percentage = self.summary()
        self.label_totalassign.setText(f'{assigned}')
        self.label_totalunassign.setText(f'{unassigned}')
        self.label_percentageassign.setText(f'{assigned_percentage} %')
        self.label_percentageunassign.setText(f'{unassigned_percentage} %')

    def summary(self):
        try:
            with open(self.log_directory, 'r') as file:
                for line in file:
                    match = re.search(r"Matching unique query sequences: (\d+) of (\d+)", line)
                    if match:
                        assigned = int(match.group(1))
                        total = int(match.group(2))
                        unassigned = total - assigned
                        assigned_percentage = round((assigned / total) * 100, 2)
                        unassigned_percentage = round((unassigned / total) * 100, 2)
                        return assigned, unassigned, assigned_percentage, unassigned_percentage
        except FileNotFoundError:
            print("Log file not found!")
            return None

    def analysis_assigned(self):
        pattern = r"size=(\d+)\t([a-zA-Z]+)-?([a-zA-Z]*)[_-]?.*"
        total_abundance = 0
        self.output_data = []  # Hold processed data for plotting

        with open(self.assign_file, 'r') as file:
            data = file.readlines()

            # First pass: calculate total abundance
            for line in data:
                match = re.search(pattern, line)
                if match:
                    abundance = int(match.group(1))
                    total_abundance += abundance

            # Second pass: calculate rows and percentages
            for line in data:
                match = re.search(pattern, line)
                if match:
                    abundance = int(match.group(1))
                    genus = match.group(2)
                    species = match.group(3)

                    species_name = f"{genus} {species}" if species else genus
                    percentage = (abundance / total_abundance) * 100
                    self.output_data.append([genus, species_name.strip(), abundance, f"{percentage:.2f}"])

        # Sort data to get top 15 genera
        self.output_data.sort(key=lambda x: x[2], reverse=True)  # Sort by abundance
        self.output_data_top = self.output_data[:15]  # Limit to top 15

        # Update table
        self.update_table()

        # Plot top genera
        self.show_bar_plot()
        self.show_species_plot()

    def update_table(self):
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Genus", "Species", "Abundance", "Percentage"])

        for row in self.output_data:
            items = [QStandardItem(str(field)) for field in row]
            model.appendRow(items)

        self.tableView.setModel(model)
        self.tableView.setColumnWidth(1, 230)
        self.tableView.setColumnWidth(0, 130)
        self.tableView.setColumnWidth(2, 90)
        self.tableView.setColumnWidth(3, 90)


    def show_bar_plot(self):
        # Clear the canvas
        self.canvas.figure.clear()
        ax = self.canvas.figure.add_subplot(111)

        # Extract data for plotting
        genus_names = [item[0] for item in self.output_data_top]
        abundances = [item[2] for item in self.output_data_top]

        # Create bar plot
        ax.bar(genus_names, abundances, color='skyblue')
        ax.set_title("Top 15 Genus by Abundance", fontsize=12)
        ax.set_xlabel("Genus", fontsize=8)
        ax.set_ylabel("Abundance", fontsize=10)
        ax.tick_params(axis='x', labelrotation=45, labelsize=10)
        ax.tick_params(axis='y', labelsize=10)

        # Adjust layout
        self.canvas.figure.tight_layout()

        # Refresh the canvas
        self.canvas.draw()




    def show_species_plot(self):
        # Clear the species canvas
        self.canvas_species.figure.clear()
        ax = self.canvas_species.figure.add_subplot(111)

        # Extract data for plotting
        species_names = [item[1] for item in self.output_data_top]
        abundances = [item[2] for item in self.output_data_top]

        # Create bar plot
        ax.bar(species_names, abundances, color='lightgreen')
        ax.set_title("Top 15 Species by Abundance", fontsize=12)
        ax.set_xlabel("Species", fontsize=8)
        ax.set_ylabel("Abundance", fontsize=10)
        ax.tick_params(axis='x', labelrotation=45, labelsize=8)
        ax.tick_params(axis='y', labelsize=10)

        # Adjust layout
        self.canvas_species.figure.tight_layout()

        # Refresh the species canvas
        self.canvas_species.draw()


    def save_csv(self):
    # Open a file dialog to save the CSV file
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save CSV File",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        # If the user selects a file, save the data
        if file_path:
            with open(file_path, 'w', newline='') as csvfile:
                csv_writer = csv.writer(csvfile)
                csv_writer.writerow(["Genus", "Species", "Abundance", "Percentage"])
                csv_writer.writerows(self.output_data)



    def save_species_plot(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Plot as PNG",
            "",
            "PNG Files (*.png);;All Files (*)"
        )
        
        if file_path:
            self.canvas_species.figure.savefig(file_path, format='png', dpi=300)

    def save_genus_plot(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Plot as PNG",
            "",
            "PNG Files (*.png);;All Files (*)"
        )
        
        if file_path:
            self.canvas.figure.savefig(file_path, format='png', dpi=300)






if __name__ == "__main__":
    app = QApplication(sys.argv)
    log_directory = "log.txt"  # Replace with your file path
    assign_file = "assignments.txt"  # Replace with your file path
    ui = ReportMain(log_directory, assign_file)
    sys.exit(app.exec())
