import subprocess
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt6.QtCore import QThread, pyqtSignal
import sys
import os
import json
import sqlite3
import re
import time
from GUI.responsive.gui_blast_local import Ui_Blast_Local
import config


class BlastDataLoader:
    def __init__(self, db_path, taxdump_dir, sample_name):
        self.db_path = db_path
        self.sample_name = sample_name

        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        # Taxonomy file paths
        names_path = os.path.join(taxdump_dir, "names.dmp")
        nodes_path = os.path.join(taxdump_dir, "nodes.dmp")

        if not os.path.exists(names_path) or not os.path.exists(nodes_path):
            raise FileNotFoundError("names.dmp or nodes.dmp not found in taxdump folder")

        self.taxid_to_name = self.load_names(names_path)
        self.taxid_to_parent, self.taxid_to_rank = self.load_nodes(nodes_path)
        self._create_table()

    def _create_table(self):
        columns = """
            Reads TEXT, Abundance TEXT, Sequence TEXT, Accession TEXT, Genus TEXT, Species TEXT,
            Length TEXT, Score TEXT, Evalue TEXT, Identities TEXT, Gaps TEXT, BitScore TEXT, percentage_identity TEXT, Description TEXT,
            Cellular_root TEXT, Domain TEXT, Kingdom TEXT, Phylum TEXT, Subphylum TEXT,
            Class TEXT, Subclass TEXT, Order_taxo TEXT, Family TEXT, Subfamily TEXT, Tribe TEXT,
            Subtribe TEXT, Genus_taxo TEXT, taxid TEXT, Scientific_name TEXT
        """
        # Create table if not exists (use sample_name as table)
        self.cursor.execute(f"CREATE TABLE IF NOT EXISTS '{self.sample_name}' ({columns})")
        self.conn.commit()

    def load_names(self, filepath):
        taxid_to_name = {}
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                parts = [p.strip("|\t") for p in line.strip().split("\t|\t")]
                if len(parts) >= 4 and parts[3] == "scientific name":
                    taxid_to_name[parts[0]] = parts[1]
        return taxid_to_name

    def load_nodes(self, filepath):
        taxid_to_parent = {}
        taxid_to_rank = {}
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                parts = [p.strip("|\t") for p in line.strip().split("\t|\t")]
                taxid = parts[0]
                parent = parts[1]
                rank = parts[2].lower()
                if rank == "domain":
                    rank = "superkingdom"
                taxid_to_parent[taxid] = parent
                taxid_to_rank[taxid] = rank
        return taxid_to_parent, taxid_to_rank

    def get_lineage(self, taxid):
        expected_ranks = [
            "cellular organisms",
            "superkingdom",
            "kingdom",
            "phylum",
            "subphylum",
            "class",
            "subclass",
            "order",
            "family",
            "subfamily",
            "tribe",
            "subtribe",
            "genus"
        ]

        lineage = {rank: "" for rank in expected_ranks}
        current_id = taxid
        found_domain = ""

        while current_id != "1" and current_id in self.taxid_to_parent:
            rank = self.taxid_to_rank.get(current_id, "no rank")
            name = self.taxid_to_name.get(current_id, "")
            if rank == "superkingdom" and not lineage["superkingdom"]:
                lineage["superkingdom"] = name
                found_domain = name
            if rank in lineage and lineage[rank] == "":
                lineage[rank] = name
            current_id = self.taxid_to_parent[current_id]

        lineage["cellular organisms"] = self.taxid_to_name.get("1", "cellular organisms")

        if not lineage["superkingdom"]:
            lineage["superkingdom"] = found_domain or ""

        return lineage

    def _parse_genus_species(self, title):
        parts = title.split()
        genus = parts[0] if len(parts) > 0 else ""
        species = parts[1] if len(parts) > 1 else ""
        return genus, species

    def load_from_json(self, json_file):
        start = time.time()
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        total_hits = 0
        for blast_output in data.get("BlastOutput2", []):
            report = blast_output.get("report", {})
            results = report.get("results", {}).get("search", {})
            query_title = results.get("query_title", "")

            reads = query_title
            abundance_match = re.search(r"size=(\d+)", query_title)
            abundance = abundance_match.group(1) if abundance_match else ""

            for hit in results.get("hits", []):
                num = hit.get("num", 0)
                if 1 <= num <= 50:
                    total_hits += 1
                    desc = hit.get("description", [{}])[0]
                    accession = desc.get("accession", "")
                    title = desc.get("title", "")
                    taxid = str(desc.get("taxid", ""))

                    genus, species = self._parse_genus_species(title)

                    hsp = hit.get("hsps", [{}])[0]
                    qseq = hsp.get("qseq", "")
                    length = str(hit.get("len", ""))
                    score = str(hsp.get("score", ""))
                    evalue = str(hsp.get("evalue", ""))
                    identities = str(hsp.get("identity", ""))
                    gaps = str(hsp.get("gaps", ""))
                    bit_score = str(hsp.get("bit_score", ""))

                    align_len = hsp.get("align_len", 0)
                    if align_len:
                        percentage_identity = (float(hsp.get("identity", 0)) / float(align_len)) * 100
                    else:
                        percentage_identity = 0.0
                    percentage_identity = f"{percentage_identity:.2f}"

                    taxonomy = self.get_lineage(taxid)

                    row_values = [
                        reads,
                        abundance,
                        qseq,
                        accession,
                        genus,
                        species,
                        length,
                        score,
                        evalue,
                        identities,
                        gaps,
                        bit_score,
                        percentage_identity,
                        title,
                        taxonomy.get("cellular organisms", ""),
                        taxonomy.get("superkingdom", ""),
                        taxonomy.get("kingdom", ""),
                        taxonomy.get("phylum", ""),
                        taxonomy.get("subphylum", ""),
                        taxonomy.get("class", ""),
                        taxonomy.get("subclass", ""),
                        taxonomy.get("order", ""),
                        taxonomy.get("family", ""),
                        taxonomy.get("subfamily", ""),
                        taxonomy.get("tribe", ""),
                        taxonomy.get("subtribe", ""),
                        taxonomy.get("genus", ""),
                        taxid,
                        self.taxid_to_name.get(taxid, "")
                    ]

                    placeholders = ",".join("?" * len(row_values))
                    self.cursor.execute(f"INSERT INTO '{self.sample_name}' VALUES ({placeholders})", row_values)

        self.conn.commit()


class BlastLocalWorker(QThread):
    output_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    progress_signal = pyqtSignal(int)  # For future use with progress bar

    def __init__(self, selected_sequence_file, database_path, sample_name, max_target_seqs, num_threads, perc_identity):
        super().__init__()
        self.selected_sequence_file = selected_sequence_file
        self.database_path = database_path
        self.sample_name = sample_name.strip().replace(" ", "_")
        self.max_target_seqs = max_target_seqs
        self.num_threads = num_threads  
        self.perc_identity = perc_identity


    def run(self):
        try:
            self.output_signal.emit("Starting BLAST processing...\n")
            self.process_blast_local()
            self.output_signal.emit("BLAST processing completed.\n")
        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)}\n")
        finally:
            self.finished_signal.emit()

    def process_blast_local(self):
        """Run blastn locally"""
        output_file = os.path.join(
            os.path.dirname(self.selected_sequence_file),
            f"{self.sample_name}_blast_output.json"
        )
        databasename = os.path.join(self.database_path, "core_nt")

        blast_location = config.get_blast_location()
        if not os.path.exists(blast_location):
            raise FileNotFoundError(
                f"BLAST not found at:\n{blast_location}\n\nPlease set the correct path in Settings."
            )

        cmd = [
            blast_location,  # Path to blastn executable
            "-query", self.selected_sequence_file,
            "-db", databasename,
            "-task", "megablast",  # Use megablast for faster searches
            "-max_target_seqs", self.max_target_seqs,
            "-max_hsps", "1",
            "-out", output_file,
            "-outfmt", "15",  # JSON
            "-num_threads", self.num_threads,
            "-evalue", "1e-5",
            "-perc_identity", self.perc_identity,
        ]

        self.output_signal.emit(f"Running command: {' '.join(cmd)}\n")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        for line in process.stdout:
            self.output_signal.emit(line)
        for line in process.stderr:
            self.error_signal.emit(line)

        process.wait()
        if process.returncode != 0:
            raise RuntimeError(f"BLAST failed with code {process.returncode}")

        self.output_signal.emit("Retrieving data from the BLAST database completed.\n")

        # Load JSON and parse into database
        self.root_directory = os.getcwd()
        db_file = os.path.join(self.root_directory, "MetaResultDB.db")

        try:
            loader = BlastDataLoader(db_file, config.get_taxdump_folder(), self.sample_name)
            loader.load_from_json(output_file)
        except Exception as e:
            self.error_signal.emit(f"Error loading JSON and saving to DB: {str(e)}\n")


class BlastLocalMain(QMainWindow, Ui_Blast_Local):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.show()
        self.worker_thread = None
        self.selected_sequence_file = None
        self.selected_database_path = None

        self.pushButton_loadFile.clicked.connect(self.load_file)
        self.pushButton_DatabasePath.clicked.connect(self.db_path)
        self.pushButton_run.clicked.connect(self.start_blast_local_thread)

    def load_file(self):
        file_filter = "All Files (*.*);;Nochimera Files (*.nochimera.fa)"
        self.selected_sequence_file, _ = QFileDialog.getOpenFileName(
            self, "Select sequence file", '', file_filter
        )
        if self.selected_sequence_file:
            print(f"Selected file: {self.selected_sequence_file}")

    def db_path(self):
        self.selected_database_path = QFileDialog.getExistingDirectory(
            self,
            "Select Database Directory",
            ''
        )
        if self.selected_database_path:
            print(f"Selected database directory: {self.selected_database_path}")

    def start_blast_local_thread(self):
        if not self.selected_sequence_file:
            QMessageBox.warning(self, "Error", "Please select an ASVs file first.")
            return
        if not self.selected_database_path:
            QMessageBox.warning(self, "Error", "Please select a database path first.")
            return

        sample_name = self.lineEdit_sample_name.text()
        if not sample_name:
            QMessageBox.warning(self, "Error", "Please enter a sample name.")
            return

        max_target_seqs = self.lineEdit_max_target_seqs.text()
        if not max_target_seqs.isdigit():
            QMessageBox.warning(self, "Error", "Enter Max target sequences.")
            return
        
        num_threads = self.lineEdit_cpu_threads.text()
        if not num_threads.isdigit():
            QMessageBox.warning(self, "Error", "Enter number of threads.")
            return
        
        perc_identity = self.lineEdit_perc_identity.text()
        if not perc_identity:
            QMessageBox.warning(self, "Error", "Enter percentage identity.")
            return


        self.worker_thread = BlastLocalWorker(
            self.selected_sequence_file,
            self.selected_database_path,
            sample_name,
            max_target_seqs,
            num_threads,
            perc_identity,
        )
        self.worker_thread.output_signal.connect(self.print_output)
        self.worker_thread.error_signal.connect(self.print_output)
        self.worker_thread.start()

    def print_output(self, text):
        print(text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = BlastLocalMain()
    sys.exit(app.exec())