import sys
import os
import re
import sqlite3
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QScrollArea, QFrame, QFileDialog, QMessageBox, QInputDialog,
    QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor


STYLE = """
QMainWindow, QWidget {
    background-color: #f5f5f0;
    color: #1a1a1a;
    font-family: 'Segoe UI', 'SF Pro Text', sans-serif;
    font-size: 13px;
}
QScrollBar:vertical {
    width: 5px;
    background: transparent;
}
QScrollBar::handle:vertical {
    background: #d0cfc8;
    border-radius: 3px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #b8b7b0; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QPushButton {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #d8d7d0;
    border-radius: 8px;
    padding: 6px 16px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #f0efe8;
    border-color: #c0bfb8;
}
QPushButton:pressed { background-color: #e8e7e0; }

QLineEdit {
    background-color: #ffffff;
    border: 1px solid #d8d7d0;
    border-radius: 8px;
    padding: 7px 12px;
    color: #1a1a1a;
    font-size: 13px;
    selection-background-color: #c8dff8;
}
QLineEdit:focus { border-color: #6b9fd4; }

QStatusBar {
    background-color: #eeede8;
    color: #888888;
    border-top: 1px solid #d8d7d0;
    font-size: 12px;
    min-height: 28px;
}
QStatusBar::item { border: none; }

QToolTip {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #d0cfc8;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
}
"""


class SampleRow(QWidget):
    edit_requested   = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.setFixedHeight(52)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            SampleRow { background-color: transparent; border-radius: 6px; }
            SampleRow:hover { background-color: #ededea; }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(10)

        icon = QLabel("⬡")
        icon.setStyleSheet("color: #b0afa8; font-size: 14px;")
        icon.setFixedWidth(20)
        layout.addWidget(icon)

        lbl = QLabel(name)
        lbl.setStyleSheet("font-weight: 600; font-size: 13px; color: #1a1a1a;")
        layout.addWidget(lbl, 1)

        btn_edit = QPushButton("Edit")
        btn_edit.setFixedSize(68, 30)
        btn_edit.setToolTip("Rename this sample")
        btn_edit.setStyleSheet("""
            QPushButton {
                background-color: #ffffff; color: #444444;
                border: 1px solid #d0cfd8; border-radius: 7px;
                font-size: 12px; font-weight: 500;
            }
            QPushButton:hover {
                background-color: #f0f0f8; border-color: #9090c0; color: #2a2a8a;
            }
            QPushButton:pressed { background-color: #e8e8f4; }
        """)
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(self.name))
        layout.addWidget(btn_edit)

        btn_del = QPushButton("Delete")
        btn_del.setFixedSize(68, 30)
        btn_del.setToolTip("Delete this sample")
        btn_del.setStyleSheet("""
            QPushButton {
                background-color: #ffffff; color: #444444;
                border: 1px solid #d8d0d0; border-radius: 7px;
                font-size: 12px; font-weight: 500;
            }
            QPushButton:hover {
                background-color: #fff0f0; border-color: #c08080; color: #8a2020;
            }
            QPushButton:pressed { background-color: #f8e8e8; }
        """)
        btn_del.clicked.connect(lambda: self.delete_requested.emit(self.name))
        layout.addWidget(btn_del)


class SamplesMain(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sample Repository Manager")
        self.setMinimumSize(600, 460)
        self.resize(760, 540)
        self.setStyleSheet(STYLE)

        self.default_DB_directory = os.getcwd()
        self.selected_db_file = os.path.join(self.default_DB_directory, "MetaResultDB.db")

        self._build_ui()
        self._build_statusbar()

        if os.path.exists(self.selected_db_file):
            self.populate_table_list()
        else:
            QMessageBox.warning(self, "Warning",
                "Default database 'MetaResultDB.db' not found.\n"
                "Use 'Import Database' to load one.")
            self._update_status()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setFixedHeight(60)
        toolbar.setStyleSheet(
            "QWidget { background-color: #faf9f5; border-bottom: 1px solid #e0dfd8; }"
        )
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(14, 0, 14, 0)
        tl.setSpacing(10)

        btn_import = QPushButton("⬆  Import Database")
        btn_import.setFixedHeight(36)
        btn_import.setMinimumWidth(155)
        btn_import.setToolTip("Merge another SQLite database into the main database")
        btn_import.setStyleSheet("""
            QPushButton {
                background-color: #e8f0fb; color: #2a5ca8;
                border: 1px solid #b8cef0; border-radius: 8px;
                font-size: 13px; font-weight: 600; padding: 0 16px;
            }
            QPushButton:hover { background-color: #d8e8f8; border-color: #7aaae8; }
            QPushButton:pressed { background-color: #c8d8f0; }
        """)
        btn_import.clicked.connect(self.import_and_merge_db)
        tl.addWidget(btn_import)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍  Search samples…")
        self.search_edit.setFixedHeight(36)
        self.search_edit.textChanged.connect(self._filter_samples)
        tl.addWidget(self.search_edit, 1)

        root.addWidget(toolbar)

        # Column header
        col_header = QWidget()
        col_header.setFixedHeight(34)
        col_header.setStyleSheet(
            "QWidget { background-color: #eeeee8; border-bottom: 1px solid #e0dfd8; }"
        )
        ch = QHBoxLayout(col_header)
        ch.setContentsMargins(46, 0, 12, 0)
        ch.setSpacing(0)

        lbl_name = QLabel("SAMPLE NAME")
        lbl_name.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #aaa9a0; letter-spacing: 0.8px;"
        )
        ch.addWidget(lbl_name, 1)

        for txt in ("EDIT", "DELETE"):
            lbl = QLabel(txt)
            lbl.setFixedWidth(78)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                "font-size: 10px; font-weight: 700; color: #aaa9a0; letter-spacing: 0.8px;"
            )
            ch.addWidget(lbl)

        root.addWidget(col_header)

        # Scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background-color: #f5f5f0;")

        self.samples_container = QWidget()
        self.samples_container.setStyleSheet("background-color: #f5f5f0;")
        self.samples_layout = QVBoxLayout(self.samples_container)
        self.samples_layout.setContentsMargins(8, 6, 8, 6)
        self.samples_layout.setSpacing(1)
        self.samples_layout.addStretch()

        self.scroll.setWidget(self.samples_container)
        root.addWidget(self.scroll, 1)

    def _build_statusbar(self):
        sb = self.statusBar()
        self.status_conn   = QLabel("No database loaded")
        self.status_conn.setStyleSheet("color: #aaa9a0; padding: 0 8px;")
        self.status_counts = QLabel("")
        self.status_counts.setStyleSheet("color: #aaa9a0;")
        self.status_counts.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sb.addWidget(self.status_conn)
        sb.addWidget(self.status_counts, 1)

    # ── Import & merge ────────────────────────────────────────────────────────

    def import_and_merge_db(self):
        """Open a second .db file and copy all its tables into the main DB."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Database to Import", "",
            "SQLite Databases (*.db *.sqlite *.sqlite3);;All Files (*.*)"
        )
        if not path:
            return

        # If no main DB exists yet, treat the imported file AS the main DB
        if not os.path.exists(self.selected_db_file):
            self.selected_db_file = path
            self.populate_table_list()
            return

        if os.path.abspath(path) == os.path.abspath(self.selected_db_file):
            QMessageBox.warning(self, "Same File",
                "The selected file is already the main database.")
            return

        try:
            # ── Step 1: read everything from source, then close it ────────────
            src_conn = sqlite3.connect(path)
            src_cur  = src_conn.cursor()
            src_cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
            src_tables = src_cur.fetchall()   # list of (name, create_sql)
            src_conn.close()

            if not src_tables:
                QMessageBox.information(self, "Empty Database",
                    "The selected database contains no tables.")
                return

            # ── Step 2: check existing tables in destination ──────────────────
            dst_conn = sqlite3.connect(self.selected_db_file)
            dst_cur  = dst_conn.cursor()
            dst_cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            existing = {r[0] for r in dst_cur.fetchall()}

            # ── Step 3: resolve name conflicts before touching any data ───────
            # taken = destination names + any target names already planned this run
            taken = set(existing)
            plan  = []   # list of (src_name, target_name)
            imported, skipped, renamed = [], [], []

            for tbl, _create_sql in src_tables:
                target_name = tbl
                if tbl in taken:
                    choice = QMessageBox.question(
                        self, "Name Conflict",
                        f"Table '{tbl}' already exists in the main database.\n\n"
                        "What would you like to do?",
                        QMessageBox.StandardButton.Ignore |   # Skip
                        QMessageBox.StandardButton.Retry,     # Rename
                        QMessageBox.StandardButton.Retry
                    )
                    if choice == QMessageBox.StandardButton.Ignore:
                        skipped.append(tbl)
                        continue
                    # Keep prompting until user picks a name not already taken
                    suggested = f"{tbl}_imported"
                    while True:
                        new_name, ok = QInputDialog.getText(
                            self, "Rename Sample",
                            f"Enter a new name for '{tbl}':", text=suggested
                        )
                        if not ok or not new_name:
                            skipped.append(tbl)
                            target_name = None
                            break
                        if new_name in taken:
                            QMessageBox.warning(self, "Name Taken",
                                f"'{new_name}' already exists. Please choose another name.")
                            suggested = new_name
                            continue
                        target_name = new_name
                        renamed.append(f"{tbl} → {target_name}")
                        break

                if target_name is None:
                    continue

                taken.add(target_name)   # reserve so later tables can't collide with it
                plan.append((tbl, target_name))

            # ── Step 4: attach source once, copy all planned tables, detach ───
            # Use CREATE TABLE … AS SELECT — no SQL rewriting needed at all.
            if plan:
                dst_conn.execute(f"ATTACH DATABASE '{path}' AS src_db")
                for src_name, target_name in plan:
                    dst_conn.execute(
                        f'CREATE TABLE "{target_name}" AS '
                        f'SELECT * FROM src_db."{src_name}"'
                    )
                    imported.append(target_name)
                dst_conn.execute("DETACH DATABASE src_db")
                dst_conn.commit()

            dst_conn.close()

            # Summary message
            parts = []
            if imported:
                parts.append(f"✓ Imported {len(imported)} table(s): {', '.join(imported)}")
            if renamed:
                parts.append(f"✎ Renamed: {', '.join(renamed)}")
            if skipped:
                parts.append(f"– Skipped {len(skipped)} table(s): {', '.join(skipped)}")

            QMessageBox.information(self, "Import Complete", "\n".join(parts))
            self.populate_table_list()

        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"An error occurred:\n{e}")

    # ── Sample list ───────────────────────────────────────────────────────────

    def populate_table_list(self):
        while self.samples_layout.count() > 1:
            item = self.samples_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.selected_db_file or not os.path.exists(self.selected_db_file):
            self._update_status()
            return

        try:
            conn   = sqlite3.connect(self.selected_db_file)
            cur    = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            tables = [r[0] for r in cur.fetchall()]
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load tables:\n{e}")
            return

        for i, name in enumerate(tables):
            row = SampleRow(name)
            row.edit_requested.connect(self.edit_table_name)
            row.delete_requested.connect(self.delete_table)
            self.samples_layout.insertWidget(self.samples_layout.count() - 1, row)

            if i < len(tables) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet(
                    "background-color: #e8e7e2; border: none; max-height: 1px;"
                )
                self.samples_layout.insertWidget(self.samples_layout.count() - 1, sep)

        self._update_status()

    def _filter_samples(self, text: str):
        for i in range(self.samples_layout.count()):
            w = self.samples_layout.itemAt(i).widget()
            if isinstance(w, SampleRow):
                w.setVisible(text.lower() in w.name.lower())

    def _update_status(self):
        if self.selected_db_file and os.path.exists(self.selected_db_file):
            n = self._count_tables(self.selected_db_file)
            db_name = os.path.basename(self.selected_db_file)
            self.status_conn.setText(f"● {db_name}")
            self.status_conn.setStyleSheet(
                "color: #5aaa70; padding: 0 8px; font-size: 12px;"
            )
            self.status_counts.setText(f"{n} sample{'s' if n != 1 else ''}")
        else:
            self.status_conn.setText("No database loaded")
            self.status_conn.setStyleSheet(
                "color: #aaa9a0; padding: 0 8px; font-size: 12px;"
            )
            self.status_counts.setText("")

    def _count_tables(self, path: str) -> int:
        try:
            conn = sqlite3.connect(path)
            cur  = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            n = cur.fetchone()[0]
            conn.close()
            return n
        except Exception:
            return 0

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def edit_table_name(self, old_name: str):
        new_name, ok = QInputDialog.getText(
            self, "Edit Sample Name", "Enter new sample name:", text=old_name
        )
        if ok and new_name and new_name != old_name:
            try:
                conn = sqlite3.connect(self.selected_db_file)
                conn.execute(f'ALTER TABLE "{old_name}" RENAME TO "{new_name}"')
                conn.commit()
                conn.close()
                self.populate_table_list()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to rename:\n{e}")

    def delete_table(self, name: str):
        reply = QMessageBox.question(
            self, "Delete Sample",
            f"Are you sure you want to delete '{name}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                conn = sqlite3.connect(self.selected_db_file)
                conn.execute(f'DROP TABLE IF EXISTS "{name}"')
                conn.commit()
                conn.close()
                self.populate_table_list()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = SamplesMain()
    window.show()
    sys.exit(app.exec())
