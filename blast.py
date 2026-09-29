from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt6.QtCore import QThread, pyqtSignal
import sys
import os
import requests
import time
import re
import sqlite3
import xml.etree.ElementTree as ET
from GUI.responsive.gui_blast import Ui_Blast


class BlastWorker(QThread):
    output_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    progress_signal = pyqtSignal(int)

    def __init__(
        self,
        selected_asvs_file,
        global_directory,
        table_name_from_gui,
        database_text,
        blast_type_text,
        organism,
        api_key,
        max_target_seq,
        perc_identity
    ):
        super().__init__()
        self.selected_asvs_file = selected_asvs_file
        self.global_directory = global_directory
        self.total_sequences = 0
        self.table_name_from_gui = table_name_from_gui.strip().replace(" ", "_")

        self.database_text = database_text
        self.database_code = self.extract_database_code(database_text)

        self.blast_type_text = blast_type_text
        self.organism = organism.strip()
        self.api_key = api_key.strip()
        self.max_target_seq = int(max_target_seq)
        self.perc_identity = float(perc_identity)

    def run(self):
        try:
            self.output_signal.emit("Starting BLAST processing...\n")
            self.total_sequences = self.count_sequences(self.selected_asvs_file)
            self.process_blast()
            self.output_signal.emit("BLAST processing completed.\n")
        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)}\n")
        finally:
            self.finished_signal.emit()

    def extract_database_code(self, combo_text):
        match = re.search(r"\(([^()]+)\)\s*$", combo_text)
        if match:
            return match.group(1).strip()
        return "nt"

    def count_sequences(self, input_file):
        with open(input_file, "r", encoding="utf-8") as file:
            return sum(1 for line in file if line.startswith(">"))

    def refine_sequences(self, input_file):
        with open(input_file, "r", encoding="utf-8") as file:
            input_text = file.read()

        sequences = input_text.split(">")
        result = []

        for seq in sequences:
            if seq.strip():
                header, *sequence_lines = seq.split("\n")
                sequence = "".join(sequence_lines).strip()
                if sequence:
                    result.append(f">{header}\n{sequence}")

        return result

    def blast_dna_sequence(self, sequence):
        url = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"

        params = {
            "CMD": "Put",
            "DATABASE": self.database_code,
            "PROGRAM": "blastn",
            "QUERY": sequence,
            "HITLIST_SIZE": str(max(self.max_target_seq, 1))
        }

        # Optimize for selection
        if "megablast" in self.blast_type_text.lower() and "discontiguous" not in self.blast_type_text.lower():
            params["MEGABLAST"] = "on"

        # Optional organism limit
        if self.organism:
            params["ENTREZ_QUERY"] = f'"{self.organism}"[Organism]'

        # Optional API key
        if self.api_key:
            params["API_KEY"] = self.api_key

        response = requests.post(url, data=params, timeout=60)
        if response.status_code != 200:
            self.error_signal.emit(f"BLAST submit failed: HTTP {response.status_code}\n")
            return None

        rid_match = re.search(r"RID = ([^\n]+)", response.text)
        if not rid_match:
            self.error_signal.emit("Could not retrieve RID from BLAST response.\n")
            return None

        rid = rid_match.group(1).strip()
        self.output_signal.emit(f"RID: {rid}\n")

        for _ in range(30):
            time.sleep(10)
            status_params = {
                "CMD": "Get",
                "RID": rid,
                "FORMAT_OBJECT": "SearchInfo"
            }
            if self.api_key:
                status_params["API_KEY"] = self.api_key

            status_response = requests.get(url, params=status_params, timeout=60)
            if status_response.status_code != 200:
                continue

            if "Status=READY" in status_response.text:
                if "ThereAreHits=yes" in status_response.text:
                    break
                return "NO_HITS"
            elif "Status=FAILED" in status_response.text:
                self.error_signal.emit(f"BLAST search failed for RID {rid}\n")
                return None
            elif "Status=UNKNOWN" in status_response.text:
                self.error_signal.emit(f"BLAST status unknown for RID {rid}\n")
                return None
        else:
            self.error_signal.emit(f"BLAST timed out for RID {rid}\n")
            return None

        result_params = {
            "CMD": "Get",
            "RID": rid,
            "FORMAT_TYPE": "Text"
        }
        if self.api_key:
            result_params["API_KEY"] = self.api_key

        result_response = requests.get(url, params=result_params, timeout=60)
        if result_response.status_code != 200:
            self.error_signal.emit(f"Failed to retrieve results for RID {rid}\n")
            return None

        return result_response.text

    def parse_blast_results(self, data):
        parsed_data = []

        if not data or data == "NO_HITS" or "No significant similarity found." in data:
            parsed_data.append({
                "Accession": "None",
                "Description": "None",
                "Genus": "None",
                "Species": "None",
                "Length": "None",
                "Score": "None",
                "Expect": "None",
                "Identities": "None",
                "percentage_identity": None,
                "Gaps": "None"
            })
            return parsed_data

        lines = data.splitlines()
        blocks = []
        current_block = []

        for line in lines:
            if line.startswith(">") and current_block:
                blocks.append("\n".join(current_block))
                current_block = [line]
            else:
                current_block.append(line)

        if current_block:
            blocks.append("\n".join(current_block))

        filtered_blocks = [block for block in blocks if block.lstrip().startswith(">")]

        for block in filtered_blocks:
            data_dict = {
                "Accession": None,
                "Description": None,
                "Genus": None,
                "Species": None,
                "Length": None,
                "Score": None,
                "Expect": None,
                "Identities": None,
                "percentage_identity": None,
                "Gaps": None
            }

            block_lines = block.split("\n")

            for line in block_lines:
                line = line.strip()

                if line.startswith(">"):
                    parts = line.split()
                    data_dict["Accession"] = parts[0][1:] if parts else "None"
                    description = " ".join(parts[1:]) if len(parts) > 1 else "None"
                    data_dict["Description"] = description

                    genus_species = description.split(",")[0].split()
                    data_dict["Genus"] = genus_species[0] if len(genus_species) > 0 else ""
                    data_dict["Species"] = genus_species[1] if len(genus_species) > 1 else ""

                elif "Length=" in line:
                    data_dict["Length"] = line.split("=")[-1].strip()

                elif "Score" in line and "Expect" in line:
                    parts = [p.strip() for p in line.split(",")]
                    for part in parts:
                        if "Score" in part:
                            data_dict["Score"] = part.split("=")[-1].strip()
                        elif "Expect" in part:
                            data_dict["Expect"] = part.split("=")[-1].strip()

                elif "Identities" in line:
                    parts = [p.strip() for p in line.split(",")]

                    for part in parts:
                        if part.startswith("Identities"):
                            identities_str = part.split("=")[-1].strip()
                            data_dict["Identities"] = identities_str

                            match = re.search(r"(\d+)\s*/\s*(\d+)", identities_str)
                            if match:
                                num = int(match.group(1))
                                denom = int(match.group(2))
                                if denom > 0:
                                    pct = (num / denom) * 100.0
                                    data_dict["percentage_identity"] = f"{pct:.2f}"

                        elif part.startswith("Gaps"):
                            data_dict["Gaps"] = part.split("=")[-1].strip()

            parsed_data.append(data_dict)

        return parsed_data

    def filter_hits(self, parsed_hits):
        valid_hits = []

        for hit in parsed_hits:
            pct = hit.get("percentage_identity")

            # Keep unassigned/no-hit row only if nothing else passes
            if pct is None:
                continue

            try:
                if float(pct) >= self.perc_identity:
                    valid_hits.append(hit)
            except ValueError:
                continue

        valid_hits.sort(
            key=lambda x: float(x.get("percentage_identity", 0.0)),
            reverse=True
        )

        return valid_hits[:self.max_target_seq]

    def process_blast(self):
        sequences = self.refine_sequences(self.selected_asvs_file)

        self.root_directory = os.getcwd()
        conn = sqlite3.connect(os.path.join(self.root_directory, "MetaResultDB.db"))
        cursor = conn.cursor()

        table_name = self.table_name_from_gui if self.table_name_from_gui else os.path.splitext(
            os.path.basename(self.selected_asvs_file)
        )[0]
        copy_number = 1
        base_table_name = table_name

        while True:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            if not cursor.fetchone():
                break
            table_name = f"{base_table_name}_copy{copy_number}"
            copy_number += 1

        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                Reads TEXT,
                Abundance TEXT,
                Sequence TEXT,
                Accession TEXT,
                Genus TEXT,
                Species TEXT,
                Length TEXT,
                Score TEXT,
                Evalue TEXT,
                Identities TEXT,
                percentage_identity TEXT,
                Gaps TEXT,
                Description TEXT,
                Cellular_root TEXT,
                Domain TEXT,
                Kingdom TEXT,
                Phylum TEXT,
                Subphylum TEXT,
                Class TEXT,
                Subclass TEXT,
                Order_taxo TEXT,
                Family TEXT,
                Subfamily TEXT,
                Tribe TEXT,
                Subtribe TEXT,
                Genus_taxo TEXT,
                taxid TEXT,
                Scientific_name TEXT
            )
        ''')

        for counter, sequence in enumerate(sequences):
            lines = sequence.split("\n")
            header = lines[0]
            seq = lines[1].strip() if len(lines) > 1 else ""

            if not seq:
                self.error_signal.emit(f"Empty sequence for {header}\n")
                continue

            self.output_signal.emit(f"Processing: {header}\n")
            blast_response = self.blast_dna_sequence(seq)

            if blast_response is None:
                self.error_signal.emit(f"BLAST failed for {header}\n")
                continue

            file_name = header.replace(">", "").replace(";", " ")

            abundance_match = re.search(r"size=(\d+)", header)
            abundance = abundance_match.group(1) if abundance_match else ""

            parsed_hits = self.parse_blast_results(blast_response)
            filtered_hits = self.filter_hits(parsed_hits)

            if not filtered_hits:
                self.output_signal.emit(
                    f"No hits passed percentage identity >= {self.perc_identity} for {header}\n"
                )
                self.progress_signal.emit(int(((counter + 1) / self.total_sequences) * 100))
                continue

            for data in filtered_hits:
                acc = data["Accession"]
                taxonomy_info = self.fetch_taxonomy_from_accessions(acc) if acc and acc != "None" else {
                    "cellular root": None,
                    "domain": None,
                    "kingdom": None,
                    "phylum": None,
                    "subphylum": None,
                    "class": None,
                    "subclass": None,
                    "order": None,
                    "family": None,
                    "subfamily": None,
                    "tribe": None,
                    "subtribe": None,
                    "genus": None,
                    "taxid": None,
                    "scientific_name": None
                }

                cursor.execute(f'''
                    INSERT INTO "{table_name}" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    file_name,
                    abundance,
                    seq,
                    data["Accession"],
                    data["Genus"],
                    data["Species"],
                    data["Length"],
                    data["Score"],
                    data["Expect"],
                    data["Identities"],
                    data["percentage_identity"],
                    data["Gaps"],
                    data["Description"],
                    taxonomy_info["cellular root"],
                    taxonomy_info["domain"],
                    taxonomy_info["kingdom"],
                    taxonomy_info["phylum"],
                    taxonomy_info["subphylum"],
                    taxonomy_info["class"],
                    taxonomy_info["subclass"],
                    taxonomy_info["order"],
                    taxonomy_info["family"],
                    taxonomy_info["subfamily"],
                    taxonomy_info["tribe"],
                    taxonomy_info["subtribe"],
                    taxonomy_info["genus"],
                    taxonomy_info["taxid"],
                    taxonomy_info["scientific_name"]
                ))

            conn.commit()

            self.output_signal.emit(
                f"Saved {len(filtered_hits)} record(s) for {header} "
                f"(identity >= {self.perc_identity}, max={self.max_target_seq})\n"
            )

            self.progress_signal.emit(int(((counter + 1) / self.total_sequences) * 100))
            time.sleep(2)

        conn.close()

    def fetch_taxonomy_from_accessions(self, accession):
        target_ranks = {
            "cellular root", "domain", "kingdom", "phylum", "subphylum",
            "class", "subclass", "order", "family", "subfamily",
            "tribe", "subtribe", "genus"
        }

        rank_dict = {rank: None for rank in target_ranks}
        rank_dict["taxid"] = None
        rank_dict["scientific_name"] = None

        if not accession or accession == "None":
            return rank_dict

        try:
            url1 = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            params1 = {
                "db": "nuccore",
                "id": accession,
                "retmode": "json"
            }
            response1 = requests.get(url1, params=params1, timeout=60)
            data1 = response1.json()
            uids = data1.get("result", {}).get("uids", [])
            if not uids:
                return rank_dict

            uid = uids[0]
            taxid = data1["result"][uid].get("taxid")
            if not taxid:
                return rank_dict

        except Exception as e:
            self.error_signal.emit(f"Error fetching TaxID for {accession}: {e}\n")
            return rank_dict

        try:
            url2 = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            params2 = {
                "db": "taxonomy",
                "id": taxid,
                "retmode": "xml"
            }
            response2 = requests.get(url2, params=params2, timeout=60)
            response2.raise_for_status()

            root = ET.fromstring(response2.content)
            taxon = root.find("Taxon")
            if taxon is None:
                return rank_dict

            rank_dict["scientific_name"] = taxon.findtext("ScientificName", None)
            rank_dict["taxid"] = str(taxid)

            lineage_ex = taxon.find("LineageEx")
            if lineage_ex is not None:
                for lineage_taxon in lineage_ex.findall("Taxon"):
                    rank = lineage_taxon.findtext("Rank")
                    name = lineage_taxon.findtext("ScientificName")
                    if rank in target_ranks:
                        rank_dict[rank] = name

            time.sleep(0.5)
            return rank_dict

        except Exception as e:
            self.error_signal.emit(f"Error fetching taxonomy for TaxID {taxid}: {e}\n")
            return rank_dict


class BlastMain(QMainWindow, Ui_Blast):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.show()
        self.worker_thread = None
        self.selected_asvs_file = None
        self.global_directory = os.getcwd()

        self.pushButton_loadFile.clicked.connect(self.load_file)
        self.pushButton_run.clicked.connect(self.start_blast_thread)
        self.pushButton_setDefult.clicked.connect(self.set_default_values)

    def load_file(self):
        file_filter = "All Files (*.*);;Nochimera Files (*.nochimera.fa)"
        self.selected_asvs_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select ASVs file",
            "",
            file_filter
        )
        if self.selected_asvs_file:
            print(f"Selected file: {self.selected_asvs_file}")

    def set_default_values(self):
        self.lineEdit_Percentage_identity.setText("97")
        self.lineEdit_max_target_seq.setText("10")
        self.comboBox_database.setCurrentIndex(0)
        self.comboBox_blastType.setCurrentIndex(0)

    def start_blast_thread(self):
        self.progressBar.setValue(0)

        if not self.selected_asvs_file:
            QMessageBox.warning(self, "Error", "Please select an ASVs file first.")
            return

        sample_name = self.lineEdit_sample_name.text().strip()
        if not sample_name:
            QMessageBox.warning(self, "Error", "Please enter a sample name.")
            return

        max_target_seq = self.lineEdit_max_target_seq.text().strip()
        if not max_target_seq.isdigit() or int(max_target_seq) <= 0:
            QMessageBox.warning(self, "Error", "Please enter a valid Max Target Seqs.")
            return

        perc_identity = self.lineEdit_Percentage_identity.text().strip()
        try:
            perc_identity_value = float(perc_identity)
            if perc_identity_value < 0 or perc_identity_value > 100:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Error", "Please enter a valid Percentage Identity (0-100).")
            return

        database_text = self.comboBox_database.currentText()
        blast_type_text = self.comboBox_blastType.currentText()
        organism = self.lineEdit_Organism.text()
        api_key = self.lineEdit_api_key.text()

        self.worker_thread = BlastWorker(
            self.selected_asvs_file,
            self.global_directory,
            sample_name,
            database_text,
            blast_type_text,
            organism,
            api_key,
            max_target_seq,
            perc_identity
        )
        self.worker_thread.output_signal.connect(self.print_output)
        self.worker_thread.error_signal.connect(self.print_output)
        self.worker_thread.progress_signal.connect(self.update_progress_bar)
        self.worker_thread.finished_signal.connect(self.on_blast_finished)
        self.worker_thread.start()

    def print_output(self, text):
        print(text)

    def update_progress_bar(self, value):
        self.progressBar.setValue(value)

    def on_blast_finished(self):
        self.progressBar.setValue(100)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = BlastMain()
    sys.exit(app.exec())