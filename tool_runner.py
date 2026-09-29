"""
Shared helpers for running external tools (vsearch, blastn) safely.

Key rule: commands are built as LISTS of arguments and executed with
subprocess WITHOUT shell=True. That way spaces (and &, parentheses, etc.)
in any path -- including 'OneDrive - Cranfield University' or
'MetaBioDetect 23 8 2026' -- never break the command, and no manual
quoting is needed anywhere.
"""

import os
import shlex
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal


def split_extra_args(text):
    """Split the free-text 'other commands' box into arguments.

    Uses shlex so users can quote values that contain spaces,
    e.g.:  --log "C:/My Folder/run.log"
    Falls back to a plain split if the quoting is unbalanced.
    """
    text = (text or "").strip()
    if not text:
        return []
    try:
        return shlex.split(text, posix=True)
    except ValueError:
        return text.split()


def display_command(args):
    """Return a copy-pasteable, properly quoted version of the command
    (for printing/logging only -- never execute this string)."""
    return subprocess.list2cmdline(args)


class ToolWorker(QThread):
    """Run an external tool (args list) in a background thread.

    Streams every output line via output_signal, reports failure via
    error_signal, and always emits finished_signal at the end.
    """
    output_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, args):
        super().__init__()
        if isinstance(args, str):
            raise TypeError(
                "ToolWorker expects a list of arguments, not a command string. "
                "Build the command as a list so paths with spaces work."
            )
        self.args = list(args)

    def run(self):
        try:
            self.output_signal.emit(f"Command: {display_command(self.args)}\n")
            # stderr merged into stdout: avoids pipe deadlocks and keeps
            # vsearch's progress messages (which go to stderr) in order.
            process = subprocess.Popen(
                self.args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            for line in process.stdout:
                self.output_signal.emit(line)
            process.wait()

            if process.returncode == 0:
                self.output_signal.emit("Command executed successfully.\n")
            else:
                self.error_signal.emit(
                    f"Command failed with return code {process.returncode}\n"
                )
        except FileNotFoundError:
            self.error_signal.emit(
                f"Executable not found:\n{self.args[0]}\n"
                "Please set the correct path in Settings.\n"
            )
        except Exception as e:
            self.error_signal.emit(f"Exception: {e}\n")
        finally:
            self.finished_signal.emit()


def tool_exists(path):
    return bool(path) and os.path.exists(path)
