from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox, QTableWidgetItem
from PyQt6.QtCore import QThread, pyqtSignal
import sys
import os
import sqlite3
import csv
import plotly.express as px
import plotly.io as pio
import pandas as pd
import webbrowser
import tempfile

from GUI.responsive.gui_blast_analysis import Ui_MainWindow


class BlastanAlysisWorker(QThread):
    output_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    progress_signal = pyqtSignal(int)

    def __init__(self, selected_db_file, global_directory):
        super().__init__()
        self.selected_db_file = selected_db_file
        self.global_directory = global_directory


class BlastAnalysisMain(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.show()

        self.worker_thread = None
        self.default_DB_directory = os.getcwd()
        self.selected_db_file = os.path.join(self.default_DB_directory, "MetaResultDB.db")

        self.displayed_data = []
        self.aggregated_data = []
        self.aggregated_column_names = []
        self.abundance_data = []
        self.abundance_column_names = []
        self.unique_records = []
        self.unique_filtered_records = []

        if os.path.exists(self.selected_db_file):
            self.populate_table_list()
        else:
            QMessageBox.warning(self, "Warning", "Default database 'MetaResultDB.db' not found in application root.")

        self.actionLoad_DB.triggered.connect(self.load_db_file)
        self.pushButton.clicked.connect(self.show_table_data)

        self.action_Export_All_Results.triggered.connect(self.export_all_database_results)
        self.action_Export_Filtered_Results.triggered.connect(self.export_filtered_results)
        # self.action_Aggregate_Results.triggered.connect(self.export_aggregated_results)
        self.action_Aggregate_Results.triggered.connect(self.export_aggregated_results)
        self.action_Abundance_Percentages.triggered.connect(self.export_abundance_percentages)
        self.pushButton_Aggregate.clicked.connect(self.aggregate_results)
        self.actionPlot_top_genus.triggered.connect(self.plot_top_genus)
        self.actionPlot_top_species.triggered.connect(self.plot_top_species)
        self.actionTop_Families.triggered.connect(self.plot_top_families)

        # Calculate % abundance button
        self.pushButton_calculate_abundance.clicked.connect(self.calculate_percentage_abundance)

    def load_db_file(self):
        file_filter = "All Files (*.*);; Files (*.db)"
        self.selected_db_file, _ = QFileDialog.getOpenFileName(self, "Select Blast Results file", '', file_filter)

        if self.selected_db_file:
            print(f"Selected file: {self.selected_db_file}")
            self.populate_table_list()

    def populate_table_list(self):
        if hasattr(self, 'selected_db_file') and self.selected_db_file:
            try:
                conn = sqlite3.connect(self.selected_db_file)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                conn.close()

                self.comboBox_samples.clear()
                self.comboBox_samples.addItems(tables)

            except sqlite3.Error as e:
                QMessageBox.critical(self, "Database Error", f"An error occurred while accessing the database: {e}")
        else:
            QMessageBox.warning(self, "Warning", "No database file loaded.")

    def show_table_data(self):
        if not hasattr(self, 'selected_db_file') or not self.selected_db_file:
            QMessageBox.warning(self, "Error", "Please load a database file first.")
            return

        table_name = self.comboBox_samples.currentText()
        top_rows = self.spinBox_top_hits.value()
        identities_percentage = self.spinBox_identities.value()
        is_show_unassigned = self.checkBox_show_unassigned.isChecked()

        try:
            conn = sqlite3.connect(self.selected_db_file)
            cursor = conn.cursor()
            cursor.execute(f'SELECT * FROM "{table_name}"')
            data = cursor.fetchall()
            conn.close()

            self.display_data_in_table_widget(data, top_rows, identities_percentage, is_show_unassigned)

            self.aggregated_data = []
            self.aggregated_column_names = []
            self.abundance_data = []
            self.abundance_column_names = []

        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"An error occurred while accessing the database: {e}")
    



    def display_data_in_table_widget(self, data, top_rows, identities_percentage, is_show_unassigned):
        self.tableWidget_viewer.setRowCount(0)
        self.tableWidget_viewer.setColumnCount(0)

        if not data:
            return

        column_names = [description[1] for description in self.get_column_names(
            self.selected_db_file,
            self.comboBox_samples.currentText()
        )]

        self.tableWidget_viewer.setColumnCount(len(column_names))
        self.tableWidget_viewer.setHorizontalHeaderLabels(column_names)

        try:
            identity_col_index = column_names.index("percentage_identity")
            reads_col = column_names.index("Reads")
        except ValueError:
            QMessageBox.critical(self, "Error", "Required columns not found in the table.")
            return

        def _identity(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        # Best identity per read. A read is "unassigned" when none of its
        # hits reach the identity cutoff (i.e. all results minus the
        # identified percentage).
        best_identity = {}
        for row_data in data:
            read_id = row_data[reads_col]
            percent = _identity(row_data[identity_col_index])
            if percent is None:
                continue
            current = best_identity.get(read_id)
            best_identity[read_id] = percent if current is None else max(current, percent)

        all_reads = {row_data[reads_col] for row_data in data}
        unassigned_reads = {
            read_id for read_id in all_reads
            if best_identity.get(read_id) is None
            or best_identity[read_id] < identities_percentage
        }

        # Build the visible rows
        displayed_data = []
        category_counts = {}

        for row_data in data:
            read_id = row_data[reads_col]
            percent = _identity(row_data[identity_col_index])

            meets_identity_criteria = percent is not None and percent >= identities_percentage
            show_this_unassigned = is_show_unassigned and read_id in unassigned_reads

            if not (meets_identity_criteria or show_this_unassigned):
                continue

            category = row_data[0]
            category_counts.setdefault(category, 0)

            if category_counts[category] < top_rows:
                displayed_data.append(row_data)
                category_counts[category] += 1

        self.display_table(displayed_data, column_names)
        self.displayed_data = displayed_data

        self.unique_records = list({row[0]: row for row in data}.values())
        self.unique_filtered_records = list({row[0]: row for row in displayed_data}.values())

        # Summary computed directly from the unassigned definition,
        # so it stays correct regardless of the checkbox state.
        total = len(all_reads)
        total_unassigned = len(unassigned_reads)
        total_assigned = total - total_unassigned

        if total > 0:
            total_assigned_percentage = round((total_assigned / total) * 100, 2)
            total_unassigned_percentage = round((total_unassigned / total) * 100, 2)
        else:
            total_assigned_percentage = 0.0
            total_unassigned_percentage = 0.0

        self.label_summary_data.setText(
            f'Total number of assigned: {total_assigned}   percentage: {total_assigned_percentage}%      /    '
            f'Total number of unassigned: {total_unassigned}   percentage: {total_unassigned_percentage}%'
        )

    def display_table(self, data, column_names):
        self.tableWidget_viewer.setRowCount(0)
        self.tableWidget_viewer.setColumnCount(len(column_names))
        self.tableWidget_viewer.setHorizontalHeaderLabels(column_names)

        for row_index, row_data in enumerate(data):
            self.tableWidget_viewer.insertRow(row_index)

            for col_index, cell_data in enumerate(row_data):
                item = QTableWidgetItem(str(cell_data))
                self.tableWidget_viewer.setItem(row_index, col_index, item)

    def get_column_names(self, db_file, table_name):
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute(f'PRAGMA table_info("{table_name}")')
            column_info = cursor.fetchall()
            conn.close()
            return column_info

        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Error getting column names: {e}")
            return []

    def save_csv_file(self, column_names, data, default_filename):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save CSV",
            default_filename,
            "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            with open(file_path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(column_names)
                writer.writerows(data)

            QMessageBox.information(self, "Export Successful", f"Results exported to:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export results:\n{str(e)}")

    def export_all_database_results(self):
        if not hasattr(self, 'selected_db_file') or not self.selected_db_file:
            QMessageBox.warning(self, "Error", "Please load a database file first.")
            return

        table_name = self.comboBox_samples.currentText()

        try:
            conn = sqlite3.connect(self.selected_db_file)
            cursor = conn.cursor()
            cursor.execute(f'SELECT * FROM "{table_name}"')
            data = cursor.fetchall()
            conn.close()

            if not data:
                QMessageBox.warning(self, "No Data", "No data found in the selected table.")
                return

            column_names = [description[1] for description in self.get_column_names(
                self.selected_db_file,
                table_name
            )]

            self.save_csv_file(column_names, data, "all_database_results.csv")

        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Export failed:\n{e}")

    def export_filtered_results(self):
        if not self.displayed_data:
            QMessageBox.warning(self, "No Data", "Please click 'Show Results' first.")
            return

        column_names = [description[1] for description in self.get_column_names(
            self.selected_db_file,
            self.comboBox_samples.currentText()
        )]

        self.save_csv_file(column_names, self.displayed_data, "filtered_results.csv")

    # def export_aggregated_results(self):
    #     if self.abundance_data:
    #         self.save_csv_file(
    #             self.abundance_column_names,
    #             self.abundance_data,
    #             "percentage_abundance_results.csv"
    #         )
    #         return

    #     if not self.aggregated_data:
    #         QMessageBox.warning(self, "No Data", "Please run aggregation first.")
    #         return

    #     self.save_csv_file(
    #         self.aggregated_column_names,
    #         self.aggregated_data,
    #         "aggregated_results.csv"
    #     )

    def export_aggregated_results(self):
        if not self.aggregated_data:
            QMessageBox.warning(self, "No Data", "Please click 'Aggregate Results' first.")
            return

        self.save_csv_file(
            self.aggregated_column_names,
            self.aggregated_data,
            "aggregated_results.csv"
        )

    def export_abundance_percentages(self):
        if not self.abundance_data:
            QMessageBox.warning(self, "No Data", "Please click 'Calculate % Abundance' first.")
            return

        self.save_csv_file(
            self.abundance_column_names,
            self.abundance_data,
            "percentage_abundance_results.csv"
        )
    
    def aggregate_results(self):
        if not self.displayed_data:
            QMessageBox.warning(self, "No Data", "Please click 'Show Results' first.")
            return

        column_names = [description[1] for description in self.get_column_names(
            self.selected_db_file,
            self.comboBox_samples.currentText()
        )]

        required_columns = [
            "Reads",
            "Species",
            "Scientific_name",
            "Genus_taxo",
            "Family",
            "Order_taxo"
        ]

        for col in required_columns:
            if col not in column_names:
                QMessageBox.critical(self, "Error", f"No '{col}' column found.")
                return

        reads_col = column_names.index("Reads")

        taxonomy_levels = [
            ("species", "Scientific_name"),
            ("genus", "Genus_taxo"),
            ("family", "Family"),
            ("order", "Order_taxo"),
        ]

        grouped = {}

        for row in self.displayed_data:
            read_id = row[reads_col]
            grouped.setdefault(read_id, []).append(row)

        aggregated_data = []

        for read_id, rows in grouped.items():
            taxa_level = None
            taxa_name = None

            for level_name, col_name in taxonomy_levels:
                check_col_name = "Species" if level_name == "species" else col_name
                check_col_index = column_names.index(check_col_name)

                values = [
                    str(row[check_col_index]).strip()
                    for row in rows
                    if row[check_col_index] is not None
                    and str(row[check_col_index]).strip() not in ["", "None", "nan"]
                ]

                if len(values) == len(rows) and len(set(values)) == 1:
                    taxa_level = level_name

                    if level_name == "species":
                        scientific_col_index = column_names.index("Scientific_name")
                        taxa_name = str(rows[0][scientific_col_index]).strip()
                    else:
                        taxa_name = values[0]

                    break

            if taxa_level is None:
                continue

            base_row = list(rows[0])

            new_row = (
                base_row[:reads_col + 1] +
                [taxa_level, taxa_name] +
                base_row[reads_col + 1:]
            )

            aggregated_data.append(new_row)

        new_column_names = (
            column_names[:reads_col + 1] +
            ["taxa_level", "taxa_name"] +
            column_names[reads_col + 1:]
        )

        self.display_table(aggregated_data, new_column_names)

        self.aggregated_data = aggregated_data
        self.aggregated_column_names = new_column_names
        self.abundance_data = []
        self.abundance_column_names = []

        QMessageBox.information(
            self,
            "Aggregation Complete",
            f"Aggregated records: {len(aggregated_data)}"
        )

    def calculate_percentage_abundance(self):
        if not self.aggregated_data:
            QMessageBox.warning(
                self,
                "No Aggregated Data",
                "Please click 'Aggregate Results' first."
            )
            return

        column_names = self.aggregated_column_names

        required_columns = ["taxa_level", "taxa_name", "Abundance"]

        for col in required_columns:
            if col not in column_names:
                QMessageBox.critical(self, "Error", f"No '{col}' column found.")
                return

        taxa_level_col = column_names.index("taxa_level")
        taxa_name_col = column_names.index("taxa_name")
        abundance_col = column_names.index("Abundance")

        allowed_levels = ["family", "genus", "species"]

        grouped = {}

        for row in self.aggregated_data:
            taxa_level = str(row[taxa_level_col]).strip()
            taxa_name = str(row[taxa_name_col]).strip()

            if taxa_level not in allowed_levels:
                continue

            if taxa_name in ["", "None", "nan"]:
                continue

            try:
                abundance = float(row[abundance_col])
            except (TypeError, ValueError):
                abundance = 0.0

            key = (taxa_level, taxa_name)

            if key not in grouped:
                grouped[key] = 0.0

            grouped[key] += abundance

        total_abundance = sum(grouped.values())

        if total_abundance == 0:
            QMessageBox.warning(self, "No Abundance", "Total abundance is zero.")
            return

        abundance_data = []

        for (taxa_level, taxa_name), abundance in grouped.items():
            percentage_abundance = round((abundance * 100) / total_abundance, 4)

            abundance_data.append([
                taxa_level,
                taxa_name,
                int(abundance) if abundance.is_integer() else abundance,
                percentage_abundance
            ])


        level_rank = {"family": 0, "genus": 1, "species": 2 }
        
        abundance_data.sort(
            key=lambda x: (
                level_rank.get(x[0], 99),   # family → genus → species
                -float(x[3])               # % abundance (descending)
            )
        )
        
        abundance_column_names = [
            "taxa_level",
            "taxa_name",
            "Abundance",
            "% Abundance"
        ]

        self.display_table(abundance_data, abundance_column_names)

        self.abundance_data = abundance_data
        self.abundance_column_names = abundance_column_names

        QMessageBox.information(
            self,
            "Percentage Abundance Complete",
            f"Calculated abundance records: {len(abundance_data)}"
        )

    def print_output(self, text):
        print(text)

    def plot_top_genus(self):
        total_abundance = 0

        for recordUnique in self.unique_records:
            try:
                abundance = int(recordUnique[1])
                total_abundance += abundance
            except (ValueError, IndexError):
                continue

        genus_list = []
        species_list = []
        abundance_list = []

        for record in self.unique_filtered_records:
            try:
                genus = record[4]
                abundance = int(record[1])
                species = record[5]

                genus_list.append(genus)
                abundance_list.append(abundance)
                species_list.append(species)

            except (IndexError, ValueError):
                continue

        df = pd.DataFrame({
            'Genus': genus_list,
            'Abundance': abundance_list,
            'Species': species_list,
        })

        df_grouped = df.groupby('Genus', as_index=False).sum()
        df_grouped['Percentage'] = (df_grouped['Abundance'] / total_abundance) * 100
        df_top = df_grouped.sort_values(by='Percentage', ascending=False).head(15)

        fig_bar = px.bar(
            df_top,
            x='Genus',
            y='Percentage',
            title='Top 20 Genus by Relative Abundance (%)',
            labels={'Percentage': 'Abundance (%)'}
        )

        fig_bar.update_layout(xaxis_tickangle=-45)

        fig_pie = px.pie(
            df_top,
            names='Genus',
            values='Percentage',
            title='Top 20 Genus by Relative Abundance'
        )

        fig_treemap = px.treemap(
            df_top,
            path=['Genus'],
            values='Percentage',
            title='Treemap of Genus Abundance'
        )

        fig_sunburst = px.sunburst(
            df_top,
            path=['Genus'],
            values='Percentage',
            title='Sunburst of Genus Abundance'
        )

        html_bar = pio.to_html(fig_bar, include_plotlyjs='cdn', full_html=False)
        html_pie = pio.to_html(fig_pie, include_plotlyjs=False, full_html=False)
        html_treemap = pio.to_html(fig_treemap, include_plotlyjs=False, full_html=False)
        html_sunburst = pio.to_html(fig_sunburst, include_plotlyjs=False, full_html=False)

        html_content = f"""
        <html>
        <body>
            <h1>Top Genus Abundance Charts</h1>
            <div>
                <div>{html_bar}</div>
                <div>{html_pie}</div>
                <div>{html_treemap}</div>
                <div>{html_sunburst}</div>
            </div>
        </body>
        </html>
        """

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.html', delete=False
        ) as f:
            f.write(html_content)
            tmp_path = f.name

        webbrowser.open('file://' + tmp_path)

    def plot_top_species(self):
        total_abundance = 0

        for recordUnique in self.unique_records:
            try:
                abundance = int(recordUnique[1])
                total_abundance += abundance
            except (ValueError, IndexError):
                continue

        species_list = []
        abundance_list = []

        for record in self.unique_filtered_records:
            try:
                species = record[28]
                abundance = int(record[1])

                species_list.append(species)
                abundance_list.append(abundance)

            except (IndexError, ValueError):
                continue

        df = pd.DataFrame({
            'Species': species_list,
            'Abundance': abundance_list,
        })

        df_grouped = df.groupby('Species', as_index=False).sum()
        df_grouped['Percentage'] = (df_grouped['Abundance'] / total_abundance) * 100
        df_top = df_grouped.sort_values(by='Percentage', ascending=False).head(15)

        fig_bar = px.bar(
            df_top,
            x='Species',
            y='Percentage',
            title='Top 15 Species by Relative Abundance (%)',
            labels={'Percentage': 'Abundance (%)'}
        )
        fig_bar.update_layout(xaxis_tickangle=-45)

        fig_pie = px.pie(
            df_top,
            names='Species',
            values='Percentage',
            title='Top 15 Species by Relative Abundance'
        )

        fig_treemap = px.treemap(
            df_top,
            path=['Species'],
            values='Percentage',
            title='Treemap of Species Abundance'
        )

        fig_sunburst = px.sunburst(
            df_top,
            path=['Species'],
            values='Percentage',
            title='Sunburst of Species Abundance'
        )

        html_bar      = pio.to_html(fig_bar,      include_plotlyjs='cdn', full_html=False)
        html_pie      = pio.to_html(fig_pie,      include_plotlyjs=False,  full_html=False)
        html_treemap  = pio.to_html(fig_treemap,  include_plotlyjs=False,  full_html=False)
        html_sunburst = pio.to_html(fig_sunburst, include_plotlyjs=False,  full_html=False)

        html_content = f"""
        <html><body>
            <h1>Top Species Abundance Charts</h1>
            {html_bar}{html_pie}{html_treemap}{html_sunburst}
        </body></html>
        """

        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            tmp_path = f.name

        webbrowser.open('file://' + tmp_path)

    
    
    def plot_top_families(self):
        total_abundance = 0

        for recordUnique in self.unique_records:
            try:
                abundance = int(recordUnique[1])
                total_abundance += abundance
            except (ValueError, IndexError):
                continue

        family_list = []
        abundance_list = []

        for record in self.unique_filtered_records:
            try:
                family = record[19]   
                abundance = int(record[1])

                family_list.append(family)
                abundance_list.append(abundance)

            except (IndexError, ValueError):
                continue

        df = pd.DataFrame({
            'Family': family_list,
            'Abundance': abundance_list,
        })

        df_grouped = df.groupby('Family', as_index=False).sum()
        df_grouped['Percentage'] = (df_grouped['Abundance'] / total_abundance) * 100
        df_top = df_grouped.sort_values(by='Percentage', ascending=False).head(15)

        fig_bar = px.bar(
            df_top,
            x='Family',
            y='Percentage',
            title='Top 15 Families by Relative Abundance (%)',
            labels={'Percentage': 'Abundance (%)'}
        )
        fig_bar.update_layout(xaxis_tickangle=-45)

        fig_pie = px.pie(
            df_top,
            names='Family',
            values='Percentage',
            title='Top 15 Families by Relative Abundance'
        )
        fig_pie.update_traces(
            texttemplate='%{customdata[0]:.2f}%',
            customdata=df_top[['Percentage']].values,
            hovertemplate='<b>%{label}</b><br>Abundance: %{customdata[0]:.2f}%<extra></extra>',
            textinfo='none'  # disable plotly's own percent labels
        )

        fig_treemap = px.treemap(
            df_top,
            path=['Family'],
            values='Percentage',
            title='Treemap of Family Abundance'
        )

        fig_sunburst = px.sunburst(
            df_top,
            path=['Family'],
            values='Percentage',
            title='Sunburst of Family Abundance'
        )

        html_bar      = pio.to_html(fig_bar,      include_plotlyjs='cdn', full_html=False)
        html_pie      = pio.to_html(fig_pie,      include_plotlyjs=False,  full_html=False)
        html_treemap  = pio.to_html(fig_treemap,  include_plotlyjs=False,  full_html=False)
        html_sunburst = pio.to_html(fig_sunburst, include_plotlyjs=False,  full_html=False)

        html_content = f"""
        <html><body>
            <h1>Top Family Abundance Charts</h1>
            {html_bar}{html_pie}{html_treemap}{html_sunburst}
        </body></html>
        """

        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            tmp_path = f.name

        webbrowser.open('file://' + tmp_path)







if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = BlastAnalysisMain()
    sys.exit(app.exec())