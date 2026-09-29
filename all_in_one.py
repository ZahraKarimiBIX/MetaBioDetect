from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox, QInputDialog
from PyQt6.QtCore import QThread, pyqtSignal
import sys
import os
import re
import time
import json
import sqlite3
import subprocess
import contextlib
import logging
import traceback
import requests
import xml.etree.ElementTree as ET
from GUI.responsive.gui_all_in_one import Ui_AllinOne
import config
from tool_runner import split_extra_args


try:
    from cutadapt.cli import main as cutadapt_main   # cutadapt >= 4.x
except ImportError:
    from cutadapt.__main__ import main as cutadapt_main  # older versions


# ---------------------------------------------------------------------------
# Local BLAST -> taxonomy loader (JSON produced by blastn -outfmt 15)
# ---------------------------------------------------------------------------
class BlastDataLoader:
    def __init__(self, db_path, taxdump_dir, sample_name):
        self.db_path = db_path
        self.sample_name = sample_name

        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

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
            "cellular organisms", "superkingdom", "kingdom", "phylum", "subphylum",
            "class", "subclass", "order", "family", "subfamily", "tribe", "subtribe", "genus"
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
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

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
                        reads, abundance, qseq, accession, genus, species,
                        length, score, evalue, identities, gaps, bit_score,
                        percentage_identity, title,
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
                    self.cursor.execute(
                        f"INSERT INTO '{self.sample_name}' VALUES ({placeholders})",
                        row_values
                    )
        self.conn.commit()


# ---------------------------------------------------------------------------
# Helper: file-like object that emits complete lines through a callback
# ---------------------------------------------------------------------------
class _EmittingStream:
    """File-like object that emits complete lines through a callback."""

    def __init__(self, emit_func):
        self.emit_func = emit_func
        self._partial = ''

    def write(self, text):
        self._partial += text
        while '\n' in self._partial:
            line, self._partial = self._partial.split('\n', 1)
            self.emit_func(line)

    def flush(self):
        pass

    def isatty(self):
        return False   # not a terminal, so cutadapt skips the interactive progress bar


# ---------------------------------------------------------------------------
# Single worker thread that runs the whole pipeline in order
# ---------------------------------------------------------------------------
class AllInOneWorker(QThread):
    output_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    progress_signal = pyqtSignal(int)

    def __init__(self, params):
        super().__init__()
        self.p = params
        self.sample = params["sample_name"]
        self.out_dir = params["out_dir"]

    # --- helpers ----------------------------------------------------------
    def out(self, msg):
        self.output_signal.emit(msg if msg.endswith("\n") else msg + "\n")

    def err(self, msg):
        self.error_signal.emit(msg if msg.endswith("\n") else msg + "\n")

    def path(self, filename):
        return os.path.join(self.out_dir, filename)

    def _resolve_single(self, single, fwd, step_name):
        """
        Return the input file for a single-file step.

        Normally this is whatever the previous enabled step produced. If every
        upstream step that yields a single file was unticked, fall back to the
        file loaded via 'Load Forward File' so the pipeline can be started from
        the middle (e.g. run only Clustering + Remove Chimeric on an existing
        .unique.fa).
        """
        if single:
            return single
        if fwd:
            self.out(
                f"{step_name}: no upstream step produced a file, "
                f"using the loaded file as input:\n  {fwd}"
            )
            return fwd
        self.err(
            f"{step_name} has no input file. Either tick the upstream steps or "
            f"load the starting file with File > Load Forward File."
        )
        return None

    def _run(self, args, step_name):
        """Run an external tool (args list, NO shell), stream output, return True on success.

        Using a list of arguments instead of one command string means paths
        containing spaces (OneDrive folders, 'MetaBioDetect 23 8 2026', ...)
        are always passed correctly without any manual quoting.
        """
        self.out(f"===== {step_name} =====")
        self.out(f"Command: {subprocess.list2cmdline(args)}")
        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace"
            )
        except FileNotFoundError:
            self.err(f"{step_name}: executable not found:\n{args[0]}")
            return False
        for line in process.stdout:
            self.output_signal.emit(line.rstrip("\n"))
        process.wait()
        if process.returncode != 0:
            self.err(f"{step_name} failed (return code {process.returncode}).")
            return False
        self.out(f"{step_name} completed.\n")
        return True

    def _run_cutadapt(self, args, step_name):
        """Run cutadapt in-process, stream its report, return True on success.

        IMPORTANT: sys.stdout is NOT redirected here (same reasoning as in
        Quality_filtering.py). The main window replaces sys.stdout with its GUI
        OutputStream; redirecting it again process-wide makes the print_output
        slot write back into this worker's stream, re-emitting the signal in
        the main thread -> infinite loop. cutadapt's report goes through Python
        logging, so it is captured by attaching our own handler to the stream.
        """
        self.out(f"===== {step_name} =====")
        self.out(f"cutadapt {' '.join(args)}")
        stream = _EmittingStream(self.output_signal.emit)

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
                cutadapt_main(args)
        except SystemExit as e:
            if e.code not in (0, None):
                self.err(f"{step_name} failed (exit code {e.code}).")
                return False
        except Exception as e:
            self.err(f"{step_name} failed: {e}")
            return False
        finally:
            # Leave logging clean so the next step starts fresh.
            logging.root.removeHandler(handler)
        self.out(f"{step_name} completed.\n")
        return True

    # --- main -------------------------------------------------------------
    def run(self):
        try:
            # get current tool paths (reflects any changes made in Settings)
            self.vsearch_location = config.get_vsearch_location()
            self.blast_location = config.get_blast_location()
            self.taxdump_folder = config.get_taxdump_folder()

            if not os.path.exists(self.vsearch_location):
                self.err(f"VSEARCH not found at: {self.vsearch_location}\n"
                         f"Set the correct path in Settings.")
                return
            if not os.path.exists(self.blast_location):
                self.err(f"BLAST not found at: {self.blast_location}\n"
                         f"Set the correct path in Settings.")
                return
            if not os.path.exists(self.taxdump_folder):
                self.err(f"Taxonomy dump folder not found at: {self.taxdump_folder}\n"
                         f"Set the correct path in Settings.")
                return


            os.makedirs(self.out_dir, exist_ok=True)
            self.out(f"Sample: {self.sample}")
            self.out(f"Output folder: {self.out_dir}\n")

            p = self.p
            steps = p["steps"]

            fwd = p["forward_file"]
            rev = p["reverse_file"]
            single = None  # tracks the current single-file input after merging

            # 1) ADAPTER TRIMMING (cutadapt, paired) ------------------------
            if steps["adapter"]:
                if not fwd or not rev:
                    self.err("Adapter trimming needs both forward and reverse files.")
                    return
                out1 = self.path(f"{self.sample}.adapter.1.fastq")
                out2 = self.path(f"{self.sample}.adapter.2.fastq")
                args = self._cutadapt_flags(p["adapter"])
                args += ['-o', out1, '-p', out2]
                if p["adapter"]["discard_untrimmed"]:
                    args.append('--discard-untrimmed')
                if p["adapter"]["other"]:
                    args += split_extra_args(p["adapter"]["other"])
                args += [fwd, rev]
                if not self._run_cutadapt(args, "Adapter Trimming"):
                    return
                fwd, rev = out1, out2

            # 2) PRIMER TRIMMING (cutadapt, paired) -------------------------
            if steps["primer"]:
                if not fwd or not rev:
                    self.err("Primer trimming needs both forward and reverse files.")
                    return
                out1 = self.path(f"{self.sample}.primer.1.fastq")
                out2 = self.path(f"{self.sample}.primer.2.fastq")
                args = self._cutadapt_flags(p["primer"])
                args += ['-o', out1, '-p', out2]
                if p["primer"]["discard_untrimmed"]:
                    args.append('--discard-untrimmed')
                if p["primer"]["other"]:
                    args += split_extra_args(p["primer"]["other"])
                args += [fwd, rev]
                if not self._run_cutadapt(args, "Primer Trimming"):
                    return
                fwd, rev = out1, out2

            # 3) MERGING (vsearch, paired -> single) ------------------------
            if steps["merging"]:
                if not fwd or not rev:
                    self.err("Merging needs both forward and reverse files.")
                    return
                merged = self.path(f"{self.sample}.merged.fastq")
                cmd = [
                    self.vsearch_location,
                    '--fastq_mergepairs', fwd,
                    '--reverse', rev,
                    '--relabel', 'merged',
                    '--fastqout', merged,
                    '--fastq_allowmergestagger',
                ]
                m = p["merging"]
                if m["max_mismatch"]:
                    cmd += ['--fastq_maxdiffs', m["max_mismatch"]]
                if m["min_overlap"]:
                    cmd += ['--fastq_minovlen', m["min_overlap"]]
                cmd += split_extra_args(m["other"])
                cmd += ['--log', self.path(f"{self.sample}.merged.log")]
                if not self._run(cmd, "Merging"):
                    return
                single = merged

            # 4) QUALITY FILTERING (cutadapt, single) -----------------------
            if steps["quality"]:
                qf_input = self._resolve_single(single, fwd, "Quality Filtering")
                if not qf_input:
                    return
                qfilter = self.path(f"{self.sample}.qfilter.fa")
                q = p["quality"]
                args = []
                mapping = [
                    (q["maxee"], "--max-expected-errors"),
                    (q["maxlen"], "--maximum-length"),
                    (q["minlen"], "--minimum-length"),
                    (q["maxn"], "--max-n"),
                    (q["minq"], "--quality-cutoff"),
                ]
                for val, flag in mapping:
                    if val:
                        args += [flag, val]
                if q["other"]:
                    args += split_extra_args(q["other"])
                args += ['--output', qfilter, qf_input]
                if not self._run_cutadapt(args, "Quality Filtering"):
                    return
                # Relabelling is NOT passed to cutadapt (--rename has no
                # sequential-counter variable; {rn} is the paired read number).
                # Rewrite the headers ourselves, like Quality_filtering.py.
                if q["relabel"]:
                    try:
                        self._relabel_fasta(qfilter, q["relabel"])
                    except Exception as e:
                        self.err(f"Quality Filtering relabelling failed: {e}")
                        return
                single = qfilter

            # 5) IDENTIFY UNIQUE SEQ (vsearch --derep_fulllength) -----------
            if steps["unique"]:
                single = self._resolve_single(single, fwd, "Identifying Unique Seq")
                if not single:
                    return
                unique = self.path(f"{self.sample}.unique.fa")
                cmd = [
                    self.vsearch_location,
                    '--derep_fulllength', single,
                    '--sizeout',
                    '--output', unique,
                    '--log', self.path(f"{self.sample}.unique.log"),
                ]
                u = p["unique"]
                if u["relabel"]:
                    cmd += ['--relabel', u["relabel"]]
                cmd += split_extra_args(u["other"])
                if not self._run(cmd, "Identifying Unique Seq"):
                    return
                single = unique

            # 6) CLUSTERING (ASV: cluster_unoise / OTU: cluster_size) -------
            if steps["clustering"]:
                single = self._resolve_single(single, fwd, "Clustering")
                if not single:
                    return
                c = p["clustering"]
                if c["mode"] == "asv":
                    clustered = self.path(f"{self.sample}.asv.fa")
                    cmd = [
                        self.vsearch_location,
                        '--cluster_unoise', single,
                        '--centroids', clustered,
                        '--log', self.path(f"{self.sample}.asv.log"),
                    ]
                    if c["min_size"]:
                        cmd += ['--minsize', c["min_size"]]
                    if c["size_mode"] == "Size_out and Size_in":
                        cmd += ['--sizein', '--sizeout']
                    else:
                        cmd += ['--sizeout']
                    cmd += split_extra_args(c["other"])
                    if not self._run(cmd, "Clustering (ASV)"):
                        return
                else:  # OTU
                    clustered = self.path(f"{self.sample}.otu.fa")
                    cmd = [
                        self.vsearch_location,
                        '--cluster_size', single,
                        '--id', '0.97',
                        '--centroids', clustered,
                        '--log', self.path(f"{self.sample}.otu.log"),
                        '--sizeout',
                    ]
                    cmd += split_extra_args(c["other"])
                    if not self._run(cmd, "Clustering (OTU)"):
                        return
                single = clustered

            # 7) REMOVE CHIMERIC (vsearch --uchime3_denovo) -----------------
            if steps["chimeric"]:
                single = self._resolve_single(single, fwd, "Remove Chimeric")
                if not single:
                    return
                nochimera = self.path(f"{self.sample}.nochimera.fa")
                cmd = [
                    self.vsearch_location,
                    '--uchime3_denovo', single,
                    '--nonchimeras', nochimera,
                ]
                r = p["chimeric"]
                if r["width"]:
                    cmd += ['--fasta_width', r["width"]]
                if r["relabel"]:
                    cmd += ['--relabel', r["relabel"]]
                cmd += ['--xsize']
                cmd += ['--log', self.path(f"{self.sample}.chimera.log")]
                cmd += ['--sizeout']
                cmd += split_extra_args(r["other"])
                if not self._run(cmd, "Remove Chimeric"):
                    return
                single = nochimera

            # 8) TAXONOMIC ASSIGNMENT (local or online BLAST) ---------------
            if steps["taxonomic"]:
                single = self._resolve_single(single, fwd, "Taxonomic Assignment")
                if not single:
                    return
                if p["blast"]["mode"] == "local":
                    # Local BLAST does not drive the progress bar.
                    self._run_local_blast(single)
                else:
                    # Online BLAST is the only step that drives the progress bar.
                    self._run_online_blast(single)

            self.out("All selected steps completed.\n")

        except BaseException:
            # Nothing may escape run(): PyQt6 aborts the whole app on unhandled
            # exceptions in a thread, so report crashes through the error signal.
            self.err(f"Pipeline crashed:\n{traceback.format_exc()}")
        finally:
            self.finished_signal.emit()

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

    # --- cutadapt shared flag builder ------------------------------------
    def _cutadapt_flags(self, d):
        args = []
        mapping = [
            (d["forward"], "-a"),
            (d["reverse"], "-A"),
            (d["min"], "-m"),
            (d["quality"], "-q"),
            (d["max"], "--max-n"),
            (d["overlap"], "--overlap"),
            (d["error"], "--error-rate"),
        ]
        for val, flag in mapping:
            if val:
                args += [flag, val]
        return args

    # --- local blast ------------------------------------------------------
    def _run_local_blast(self, input_fasta):
        self.out("===== Taxonomic Assignment (Local BLAST) =====")
        b = self.p["blast"]
        if not b["database_path"]:
            self.err("No local BLAST database path selected.")
            return

        output_json = self.path(f"{self.sample}_blast_output.json")
        database_name = os.path.join(b["database_path"], "core_nt")

        # map the "Optimize for" combo to a blast task
        bt = b["blast_type_text"].lower()
        if "discontiguous" in bt:
            task = "dc-megablast"
        elif "megablast" in bt:
            task = "megablast"
        else:
            task = "blastn"

        cmd = [
            self.blast_location,
            "-query", input_fasta,
            "-db", database_name,
            "-task", task,
            "-max_target_seqs", str(b["max_target_seq"]),
            "-max_hsps", "1",
            "-out", output_json,
            "-outfmt", "15",
            "-num_threads", str(b["cpu_threads"]),
            "-evalue", "1e-5",
            "-perc_identity", str(b["perc_identity"]),
        ]
        self.out(f"Command: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace"
        )
        for line in process.stdout:
            self.output_signal.emit(line.rstrip("\n"))
        process.wait()
        if process.returncode != 0:
            self.err(f"Local BLAST failed (return code {process.returncode}).")
            return

        self.out("Loading BLAST JSON into database...")
        db_file = os.path.join(os.getcwd(), "MetaResultDB.db")
        try:
            loader = BlastDataLoader(db_file, self.taxdump_folder, self.sample)
            loader.load_from_json(output_json)
            self.out(f"Results saved to table '{self.sample}' in MetaResultDB.db\n")
        except Exception as e:
            self.err(f"Error loading JSON into DB: {str(e)}")

    # --- online blast -----------------------------------------------------
    def _run_online_blast(self, input_fasta):
        self.out("===== Taxonomic Assignment (Online BLAST) =====")
        b = self.p["blast"]
        self.database_code = self._extract_database_code(b["database_text"])
        self.blast_type_text = b["blast_type_text"]
        self.max_target_seq = int(b["max_target_seq"])
        self.perc_identity = float(b["perc_identity"])
        self.api_key = ""
        self.organism = ""

        sequences = self._refine_sequences(input_fasta)
        total = len(sequences)

        # Progress bar starts fresh for the online BLAST run.
        self.progress_signal.emit(0)

        db_file = os.path.join(os.getcwd(), "MetaResultDB.db")
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS "{self.sample}" (
                Reads TEXT, Abundance TEXT, Sequence TEXT, Accession TEXT, Genus TEXT,
                Species TEXT, Length TEXT, Score TEXT, Evalue TEXT, Identities TEXT,
                percentage_identity TEXT, Gaps TEXT, Description TEXT, Cellular_root TEXT,
                Domain TEXT, Kingdom TEXT, Phylum TEXT, Subphylum TEXT, Class TEXT,
                Subclass TEXT, Order_taxo TEXT, Family TEXT, Subfamily TEXT, Tribe TEXT,
                Subtribe TEXT, Genus_taxo TEXT, taxid TEXT, Scientific_name TEXT
            )
        ''')

        for counter, sequence in enumerate(sequences):
            lines = sequence.split("\n")
            header = lines[0]
            seq = lines[1].strip() if len(lines) > 1 else ""
            if not seq:
                self.err(f"Empty sequence for {header}")
                continue

            self.out(f"Processing: {header}")
            blast_response = self._blast_dna_sequence(seq)
            if blast_response is None:
                self.err(f"BLAST failed for {header}")
                continue

            file_name = header.replace(">", "").replace(";", " ")
            abundance_match = re.search(r"size=(\d+)", header)
            abundance = abundance_match.group(1) if abundance_match else ""

            parsed_hits = self._parse_blast_results(blast_response)
            filtered_hits = self._filter_hits(parsed_hits)

            if not filtered_hits:
                self.out(f"No hits >= {self.perc_identity}% identity for {header}")
            else:
                for data in filtered_hits:
                    acc = data["Accession"]
                    tax = self._fetch_taxonomy(acc) if acc and acc != "None" else self._empty_tax()
                    cursor.execute(f'''
                        INSERT INTO "{self.sample}" VALUES
                        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        file_name, abundance, seq, data["Accession"], data["Genus"],
                        data["Species"], data["Length"], data["Score"], data["Expect"],
                        data["Identities"], data["percentage_identity"], data["Gaps"],
                        data["Description"], tax["cellular root"], tax["domain"],
                        tax["kingdom"], tax["phylum"], tax["subphylum"], tax["class"],
                        tax["subclass"], tax["order"], tax["family"], tax["subfamily"],
                        tax["tribe"], tax["subtribe"], tax["genus"], tax["taxid"],
                        tax["scientific_name"]
                    ))
                conn.commit()
                self.out(f"Saved {len(filtered_hits)} record(s) for {header}")

            # Progress bar is driven solely by the online BLAST loop.
            if total:
                self.progress_signal.emit(int(((counter + 1) / total) * 100))
            time.sleep(2)

        conn.close()
        self.progress_signal.emit(100)
        self.out(f"Online BLAST results saved to table '{self.sample}'.\n")

    # --- online blast helpers --------------------------------------------
    def _extract_database_code(self, combo_text):
        match = re.search(r"\(([^()]+)\)\s*$", combo_text)
        return match.group(1).strip() if match else "nt"

    def _refine_sequences(self, input_file):
        with open(input_file, "r", encoding="utf-8") as f:
            input_text = f.read()
        result = []
        for seq in input_text.split(">"):
            if seq.strip():
                header, *seq_lines = seq.split("\n")
                sequence = "".join(seq_lines).strip()
                if sequence:
                    result.append(f">{header}\n{sequence}")
        return result

    def _blast_dna_sequence(self, sequence):
        url = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"
        params = {
            "CMD": "Put",
            "DATABASE": self.database_code,
            "PROGRAM": "blastn",
            "QUERY": sequence,
            "HITLIST_SIZE": str(max(self.max_target_seq, 1)),
        }
        if "megablast" in self.blast_type_text.lower() and "discontiguous" not in self.blast_type_text.lower():
            params["MEGABLAST"] = "on"

        response = requests.post(url, data=params, timeout=60)
        if response.status_code != 200:
            self.err(f"BLAST submit failed: HTTP {response.status_code}")
            return None

        rid_match = re.search(r"RID = ([^\n]+)", response.text)
        if not rid_match:
            self.err("Could not retrieve RID from BLAST response.")
            return None
        rid = rid_match.group(1).strip()
        self.out(f"RID: {rid}")

        for _ in range(30):
            time.sleep(10)
            status = requests.get(
                url, params={"CMD": "Get", "RID": rid, "FORMAT_OBJECT": "SearchInfo"},
                timeout=60
            )
            if status.status_code != 200:
                continue
            if "Status=READY" in status.text:
                if "ThereAreHits=yes" in status.text:
                    break
                return "NO_HITS"
            elif "Status=FAILED" in status.text:
                self.err(f"BLAST search failed for RID {rid}")
                return None
            elif "Status=UNKNOWN" in status.text:
                self.err(f"BLAST status unknown for RID {rid}")
                return None
        else:
            self.err(f"BLAST timed out for RID {rid}")
            return None

        result = requests.get(
            url, params={"CMD": "Get", "RID": rid, "FORMAT_TYPE": "Text"}, timeout=60
        )
        if result.status_code != 200:
            self.err(f"Failed to retrieve results for RID {rid}")
            return None
        return result.text

    def _parse_blast_results(self, data):
        parsed = []
        if not data or data == "NO_HITS" or "No significant similarity found." in data:
            parsed.append({
                "Accession": "None", "Description": "None", "Genus": "None",
                "Species": "None", "Length": "None", "Score": "None", "Expect": "None",
                "Identities": "None", "percentage_identity": None, "Gaps": "None"
            })
            return parsed

        lines = data.splitlines()
        blocks, current = [], []
        for line in lines:
            if line.startswith(">") and current:
                blocks.append("\n".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            blocks.append("\n".join(current))

        for block in [b for b in blocks if b.lstrip().startswith(">")]:
            d = {k: None for k in ["Accession", "Description", "Genus", "Species",
                                   "Length", "Score", "Expect", "Identities",
                                   "percentage_identity", "Gaps"]}
            for line in block.split("\n"):
                line = line.strip()
                if line.startswith(">"):
                    parts = line.split()
                    d["Accession"] = parts[0][1:] if parts else "None"
                    description = " ".join(parts[1:]) if len(parts) > 1 else "None"
                    d["Description"] = description
                    gs = description.split(",")[0].split()
                    d["Genus"] = gs[0] if len(gs) > 0 else ""
                    d["Species"] = gs[1] if len(gs) > 1 else ""
                elif "Length=" in line:
                    d["Length"] = line.split("=")[-1].strip()
                elif "Score" in line and "Expect" in line:
                    for part in [p.strip() for p in line.split(",")]:
                        if "Score" in part:
                            d["Score"] = part.split("=")[-1].strip()
                        elif "Expect" in part:
                            d["Expect"] = part.split("=")[-1].strip()
                elif "Identities" in line:
                    for part in [p.strip() for p in line.split(",")]:
                        if part.startswith("Identities"):
                            ident = part.split("=")[-1].strip()
                            d["Identities"] = ident
                            m = re.search(r"(\d+)\s*/\s*(\d+)", ident)
                            if m and int(m.group(2)) > 0:
                                d["percentage_identity"] = f"{(int(m.group(1)) / int(m.group(2))) * 100:.2f}"
                        elif part.startswith("Gaps"):
                            d["Gaps"] = part.split("=")[-1].strip()
            parsed.append(d)
        return parsed

    def _filter_hits(self, parsed_hits):
        valid = []
        for hit in parsed_hits:
            pct = hit.get("percentage_identity")
            if pct is None:
                continue
            try:
                if float(pct) >= self.perc_identity:
                    valid.append(hit)
            except ValueError:
                continue
        valid.sort(key=lambda x: float(x.get("percentage_identity", 0.0)), reverse=True)
        return valid[:self.max_target_seq]

    def _empty_tax(self):
        keys = ["cellular root", "domain", "kingdom", "phylum", "subphylum", "class",
                "subclass", "order", "family", "subfamily", "tribe", "subtribe",
                "genus", "taxid", "scientific_name"]
        return {k: None for k in keys}

    def _fetch_taxonomy(self, accession):
        target_ranks = {"cellular root", "domain", "kingdom", "phylum", "subphylum",
                        "class", "subclass", "order", "family", "subfamily",
                        "tribe", "subtribe", "genus"}
        rank_dict = self._empty_tax()
        if not accession or accession == "None":
            return rank_dict
        try:
            r1 = requests.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                params={"db": "nuccore", "id": accession, "retmode": "json"}, timeout=60
            )
            data1 = r1.json()
            uids = data1.get("result", {}).get("uids", [])
            if not uids:
                return rank_dict
            taxid = data1["result"][uids[0]].get("taxid")
            if not taxid:
                return rank_dict
        except Exception as e:
            self.err(f"Error fetching TaxID for {accession}: {e}")
            return rank_dict
        try:
            r2 = requests.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                params={"db": "taxonomy", "id": taxid, "retmode": "xml"}, timeout=60
            )
            r2.raise_for_status()
            root = ET.fromstring(r2.content)
            taxon = root.find("Taxon")
            if taxon is None:
                return rank_dict
            rank_dict["scientific_name"] = taxon.findtext("ScientificName", None)
            rank_dict["taxid"] = str(taxid)
            lineage = taxon.find("LineageEx")
            if lineage is not None:
                for lt in lineage.findall("Taxon"):
                    rank = lt.findtext("Rank")
                    name = lt.findtext("ScientificName")
                    if rank in target_ranks:
                        rank_dict[rank] = name
            time.sleep(0.5)
            return rank_dict
        except Exception as e:
            self.err(f"Error fetching taxonomy for TaxID {taxid}: {e}")
            return rank_dict


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class AllInOneMain(QMainWindow, Ui_AllinOne):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.show()

        self.worker_thread = None
        self.selected_forward_file = None
        self.selected_reverse_file = None
        self.selected_database_path = None
        self.global_directory = os.getcwd()  # may be overridden by the main window

        # menu actions to load raw paired-end files
        self.actionLoad_Forward_File.triggered.connect(self.load_forward_file)
        self.actionLoad_Reverse_File.triggered.connect(self.load_reverse_file)

        # buttons
        self.pushButton_DatabasePath.clicked.connect(self.select_database_path)
        self.pushButton_run.clicked.connect(self.start_pipeline)
        self.pushButton_reset.clicked.connect(self.reset_fields)

        # steps-to-run checkboxes control tab availability
        self._connect_step_checkboxes()

    # --- steps-to-run checkboxes <-> tabs ---------------------------------
    def _connect_step_checkboxes(self):
        """Map each 'Steps to Run' checkbox to its tab and keep them in sync."""
        # Make disabled tabs visibly greyed out (the default Windows style
        # shows almost no difference between enabled and disabled tabs)
        self.tabWidget.tabBar().setStyleSheet(
            "QTabBar::tab:disabled {"
            "    color: #b0b0b0;"
            "    background-color: #f0f0f0;"
            "}"
        )

        self._step_map = {
            self.checkBox_adapter_trimming:     self.tab_adapter_trimmig,
            self.checkBox_primer_trimming:      self.tab_primer_trimming,
            self.checkBox_merging:              self.tab_merging,
            self.checkBox_quality_filtering:    self.tab_quality_filtering,
            self.checkBox_identify_unique_seq:  self.tab_identify_unique,
            self.checkBox_clustering:           self.tab_clustering,
            self.checkBox_remove_chimeric:      self.tab_remove_chimeric,
            self.checkBox_taxonomic_assignment: self.tab_taxonomic_assignment,
        }

        for checkbox, tab in self._step_map.items():
            # default argument (t=tab) captures the right tab per connection
            checkbox.toggled.connect(
                lambda checked, t=tab: self._set_tab_enabled(t, checked)
            )

        # special handling: sample name lives inside the taxonomy tab
        self.checkBox_taxonomic_assignment.toggled.connect(
            self._on_taxonomy_toggled
        )

    def _set_tab_enabled(self, tab, enabled):
        """Enable/disable the tab that belongs to a step checkbox."""
        index = self.tabWidget.indexOf(tab)
        if index == -1:
            return
        self.tabWidget.setTabEnabled(index, enabled)

        # if the currently open tab was just disabled, jump to the first
        # tab that is still enabled
        if not enabled and self.tabWidget.currentIndex() == index:
            for i in range(self.tabWidget.count()):
                if self.tabWidget.isTabEnabled(i):
                    self.tabWidget.setCurrentIndex(i)
                    break

    def _on_taxonomy_toggled(self, checked):
        """
        The (required) Sample Name field lives inside the Taxonomic
        Assignment tab. When that step is unchecked, the tab becomes
        inaccessible, so prompt for the sample name via a dialog instead.
        """
        if checked:
            return

        # nothing to do if a sample name was already entered
        if self.lineEdit_sample_name_blast.text().strip():
            return

        while True:
            name, ok = QInputDialog.getText(
                self,
                "Sample Name Required",
                "Taxonomic Assignment is disabled, but a sample name is\n"
                "still required for the analysis. Please enter it:",
            )
            if ok and name.strip():
                self.lineEdit_sample_name_blast.setText(name.strip())
                break
            elif not ok:
                # user cancelled: re-enable the step so the required
                # field stays reachable
                QMessageBox.warning(
                    self,
                    "Sample Name Required",
                    "A sample name is required. The Taxonomic Assignment "
                    "step has been re-enabled so you can enter it there.",
                )
                self.checkBox_taxonomic_assignment.setChecked(True)
                break
            # ok pressed but empty text -> ask again

    # --- file loading -----------------------------------------------------
    def load_forward_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select forward file")
        if f:
            self.selected_forward_file = f
            print(f"Forward file: {os.path.basename(f)}")

    def load_reverse_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select reverse file")
        if f:
            self.selected_reverse_file = f
            print(f"Reverse file: {os.path.basename(f)}")

    def select_database_path(self):
        d = QFileDialog.getExistingDirectory(self, "Select BLAST Database Directory")
        if d:
            self.selected_database_path = d
            print(f"Database directory: {d}")

    # --- run --------------------------------------------------------------
    def start_pipeline(self):
        self.progressBar_blast.setValue(0)

        steps = {
            "adapter": self.checkBox_adapter_trimming.isChecked(),
            "primer": self.checkBox_primer_trimming.isChecked(),
            "merging": self.checkBox_merging.isChecked(),
            "quality": self.checkBox_quality_filtering.isChecked(),
            "unique": self.checkBox_identify_unique_seq.isChecked(),
            "clustering": self.checkBox_clustering.isChecked(),
            "chimeric": self.checkBox_remove_chimeric.isChecked(),
            "taxonomic": self.checkBox_taxonomic_assignment.isChecked(),
        }

        if not self.global_directory:
            QMessageBox.warning(self, "Error", "Please select a directory from the main window, then reopen this window.")
            return

        if not any(steps.values()):
            QMessageBox.warning(self, "Error", "Please select at least one step to run.")
            return

        # Sample name is required: it names the output folder and the DB table
        sample_name = self.lineEdit_sample_name_blast.text().strip()
        if not sample_name:
            QMessageBox.warning(self, "Error", "Please enter the sample name in the Sample Name field on the Taxonomy Assignment tab.")
            return
        sample_name = sample_name.replace(" ", "_")

        # if not self.global_directory:
        #     QMessageBox.warning(self, "Error", "Please select a directory from the main window, then reopen this window.")
        #     return

        out_dir = os.path.join(self.global_directory, sample_name)

        # Paired steps need both reads; single-file steps need at least one input.
        needs_paired = steps["adapter"] or steps["primer"] or steps["merging"]
        if needs_paired:
            if not self.selected_forward_file or not self.selected_reverse_file:
                QMessageBox.warning(
                    self, "Error",
                    "Adapter trimming, primer trimming and merging need paired reads.\n"
                    "Please load forward and reverse files from the File menu."
                )
                return
        elif not self.selected_forward_file:
            # Starting mid-pipeline: the loaded forward file is the input.
            QMessageBox.warning(
                self, "Error",
                "No input file loaded.\n\n"
                "You have unticked all the paired-read steps, so the pipeline will "
                "start from an existing file. Load it with File > Load Forward File."
            )
            return

        # validate BLAST parameters when the taxonomic step is enabled
        blast_params = None
        if steps["taxonomic"]:
            mode = "local" if self.radioButton_local_blast.isChecked() else "online"

            max_target_seq = self.lineEdit_max_target_seq_blast.text().strip() or "30"
            if not max_target_seq.isdigit() or int(max_target_seq) <= 0:
                QMessageBox.warning(self, "Error", "Please enter a valid Max Target Seqs.")
                return

            perc_identity = self.lineEdit_Percentage_identity.text().strip() or "97"
            try:
                v = float(perc_identity)
                if v < 0 or v > 100:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(self, "Error", "Please enter a valid Percentage Identity (0-100).")
                return

            cpu_threads = self.lineEdit_cpu_threads_blast.text().strip() or "12"
            if not cpu_threads.isdigit() or int(cpu_threads) <= 0:
                QMessageBox.warning(self, "Error", "Please enter a valid CPU thread count.")
                return

            if mode == "local" and not self.selected_database_path:
                QMessageBox.warning(self, "Error", "Please select a local BLAST database path.")
                return

            blast_params = {
                "mode": mode,
                "database_path": self.selected_database_path,
                "database_text": self.comboBox_database_type.currentText(),
                "blast_type_text": self.comboBox_blastType.currentText(),
                "max_target_seq": max_target_seq,
                "perc_identity": perc_identity,
                "cpu_threads": cpu_threads,
            }

        params = {
            "sample_name": sample_name,
            "out_dir": out_dir,
            "forward_file": self.selected_forward_file,
            "reverse_file": self.selected_reverse_file,
            "steps": steps,
            "adapter": {
                "forward": self.lineEdit_forward_trim_adapter.text().strip(),
                "reverse": self.lineEdit_reverse_trim_adapter.text().strip(),
                "min": self.lineEdit_min__trim_adapter.text().strip(),
                "quality": self.lineEdit_quality_trim_adapter.text().strip(),
                "max": self.lineEdit_max_trim_adapter.text().strip(),
                "overlap": self.lineEdit_overlap_trim_adapter.text().strip(),
                "error": self.lineEdit_error_trim_adapter.text().strip(),
                "discard_untrimmed": self.radioButton_yes_trim_adapter.isChecked(),
                "other": self.textEdit_othercommand_trim_adapter.toPlainText().strip(),
            },
            "primer": {
                "forward": self.lineEdit_forward_trim_primer.text().strip(),
                "reverse": self.lineEdit_reverse_trim_primer.text().strip(),
                "min": self.lineEdit_min__trim_primer.text().strip(),
                "quality": self.lineEdit_quality_trim_primer.text().strip(),
                "max": self.lineEdit_max_trim_primer.text().strip(),
                "overlap": self.lineEdit_overlap_trim_primer.text().strip(),
                "error": self.lineEdit_error_trim_primer.text().strip(),
                "discard_untrimmed": self.radioButton_yes_trim_primer.isChecked(),
                "other": self.textEdit_othercommand_trim_primer.toPlainText().strip(),
            },
            "merging": {
                "min_overlap": self.lineEdit_min_overlap_merging.text().strip(),
                "max_mismatch": self.lineEdit_max_overlap_mismatch_merging.text().strip(),
                "other": self.textEdit_other_commands_merging.toPlainText().strip(),
            },
            "quality": {
                "maxee": self.lineEdit_maxee_quality_filtering.text().strip(),
                "maxlen": self.lineEdit_maxlength_quality_filtering.text().strip(),
                "minlen": self.lineEdit_minlength_quality_filtering.text().strip(),
                "maxn": self.lineEdit_max_N_base_quality_filtering.text().strip(),
                "minq": self.lineEdit_min_quality_quality_filtering.text().strip(),
                "relabel": self.lineEdit_relabel_quality_filtering.text().strip(),
                "other": self.textEdit_othercommand_quality_filtering.toPlainText().strip(),
            },
            "unique": {
                "relabel": self.lineEdit_relabel_seq_identify_unique.text().strip(),
                "other": self.textEdit_othercommand_identify_unique.toPlainText().strip(),
            },
            "clustering": {
                "mode": "asv" if self.radioButton_asv.isChecked() else "otu",
                "min_size": self.lineEdit_min_seq_size_clustering.text().strip(),
                "size_mode": self.comboBox_size_annotation_mode_clustering.currentText(),
                "other": self.textEdit_othercommand_clustering.toPlainText().strip(),
            },
            "chimeric": {
                "width": self.lineEdit_seq_width_remove_chimeric.text().strip(),
                "relabel": self.lineEdit_relabel_remove_chimeric.text().strip(),
                "other": self.textEdit_othercommand_remove_chimeric.toPlainText().strip(),
            },
            "blast": blast_params,
        }

        self.worker_thread = AllInOneWorker(params)
        self.worker_thread.output_signal.connect(self.print_output)
        self.worker_thread.error_signal.connect(self.print_output)
        self.worker_thread.progress_signal.connect(self.update_progress_bar)
        self.worker_thread.finished_signal.connect(self.on_pipeline_finished)
        self.pushButton_run.setEnabled(False)
        self.worker_thread.start()

    # --- ui callbacks -----------------------------------------------------
    def print_output(self, text):
        print(text)

    def update_progress_bar(self, value):
        self.progressBar_blast.setValue(value)

    def on_pipeline_finished(self):
        self.pushButton_run.setEnabled(True)
        QMessageBox.information(self, "Done", "Pipeline finished. Check the output folder and log.")

    def reset_fields(self):
        for le in self.findChildren(type(self.lineEdit_sample_name_blast)):
            le.clear()
        for te in [
            self.textEdit_othercommand_trim_adapter,
            self.textEdit_othercommand_trim_primer,
            self.textEdit_other_commands_merging,
            self.textEdit_othercommand_quality_filtering,
            self.textEdit_othercommand_identify_unique,
            self.textEdit_othercommand_clustering,
            self.textEdit_othercommand_remove_chimeric,
        ]:
            te.clear()
        self.selected_forward_file = None
        self.selected_reverse_file = None
        self.selected_database_path = None
        self.progressBar_blast.setValue(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = AllInOneMain()
    sys.exit(app.exec())