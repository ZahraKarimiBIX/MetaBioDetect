import sys
import os
import json

# base folder differs between dev and PyInstaller build
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
    BASE = os.path.join(APP_DIR, '_internal')
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(APP_DIR, 'config.json')

# Windows uses .exe; Linux/macOS normally don't
if sys.platform == "win32":
    VSEARCH_EXE = "vsearch.exe"
    BLAST_EXE = "blastn.exe"
else:
    VSEARCH_EXE = "vsearch"
    BLAST_EXE = "blastn"

DEFAULTS = {
    "vsearch": os.path.join(BASE, 'apps', 'vsearch', 'bin', VSEARCH_EXE),
    "blast": os.path.join(BASE, 'apps', 'blast', BLAST_EXE),
    "taxdump": os.path.join(BASE, 'resources', 'taxdump'),
}


def _load():
    data = dict(DEFAULTS)

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved = json.load(f)

            for key, value in saved.items():
                if value and str(value).strip():
                    data[key] = value

        except (json.JSONDecodeError, OSError):
            pass

    return data


def _save(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)


def get_vsearch_location():
    return _load()["vsearch"]


def get_blast_location():
    return _load()["blast"]


def get_taxdump_folder():
    return _load()["taxdump"]


def set_vsearch_location(path):
    if path and path.strip():
        data = _load()
        data["vsearch"] = path.strip()
        _save(data)


def set_blast_location(path):
    if path and path.strip():
        data = _load()
        data["blast"] = path.strip()
        _save(data)