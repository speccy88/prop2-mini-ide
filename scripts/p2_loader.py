#!/usr/bin/env python3
"""Propeller 2 mini IDE + loader wrapper (CLI + GUI) using flexspin and loadp2."""

from __future__ import annotations

import argparse
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import serial  # type: ignore
    import serial.tools.list_ports  # type: ignore
except ImportError:  # pyserial is optional for manual port entry
    serial = None


def get_default_loadp2_path() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidate = exe_dir / "bin" / "loadp2.exe"
        if candidate.exists():
            return candidate
        candidate = exe_dir.parent / "bin" / "loadp2.exe"
        if candidate.exists():
            return candidate
        return exe_dir / "loadp2.exe"

    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "bin" / "loadp2.exe"


def get_default_flexspin_path() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidate = exe_dir / "bin" / "flexspin.exe"
        if candidate.exists():
            return candidate
        candidate = exe_dir.parent / "bin" / "flexspin.exe"
        if candidate.exists():
            return candidate
        return exe_dir / "flexspin.exe"

    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "bin" / "flexspin.exe"


DEFAULT_LOADP2 = get_default_loadp2_path()
DEFAULT_FLEXSPIN = get_default_flexspin_path()
REPO_ROOT = Path(__file__).resolve().parent.parent


def get_prop_png_path() -> Path | None:
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / "prop.png",
        REPO_ROOT / "scripts" / "prop.png",
        Path.cwd() / "prop.png",
        Path.cwd() / "scripts" / "prop.png",
    ]

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates = [
            exe_dir / "prop.png",
            exe_dir / "scripts" / "prop.png",
            exe_dir.parent / "scripts" / "prop.png",
            *candidates,
        ]

    for path in candidates:
        if path.exists():
            return path
    return None


def list_com_ports() -> list[str]:
    if serial is None:
        return []
    return [p.device for p in serial.tools.list_ports.comports()]


def autodetect_propeller_port() -> str | None:
    """Heuristic: prefer COM6, then the highest COM number, then first available port."""
    if serial is None:
        return None

    ports = list_com_ports()
    if not ports:
        return None

    # Prefer COM6 (common for Propeller 2 boards)
    if "COM6" in ports:
        return "COM6"

    # Otherwise, prefer the highest numbered COM port
    try:
        return sorted(ports, key=lambda p: int(p.replace("COM", "")), reverse=True)[0]
    except (ValueError, IndexError):
        return ports[0] if ports else None


def build_loadp2_command(
    loadp2_path: Path,
    binary_path: Path,
    mode: str,
    port: str | None,
    verbose: bool,
) -> list[str]:
    cmd = [str(loadp2_path)]
    if port:
        cmd += ["-p", port]
    if mode == "flash":
        # This is the mode that succeeded on this hardware.
        cmd += ["-SINGLE", "-FLASH"]
    if verbose:
        cmd.append("-v")
    cmd.append(str(binary_path))
    return cmd


def run_loader_command(cmd: list[str]) -> int:
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        print(line.rstrip())
    return process.wait()


def compile_spin2(flexspin_path: Path, source_path: Path) -> tuple[int, str]:
    """Compile SPIN2 file and return (exit_code, output)."""
    if not flexspin_path.exists():
        return 1, f"[ERROR] flexspin not found: {flexspin_path}\n"
    if not source_path.exists():
        return 1, f"[ERROR] source file not found: {source_path}\n"

    cmd = [str(flexspin_path), "-2", "-O2", str(source_path)]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return 1, "[ERROR] Compilation timed out\n"
    except Exception as e:
        return 1, f"[ERROR] Compilation failed: {e}\n"


def run_cli(args: argparse.Namespace) -> int:
    loadp2_path = Path(args.loadp2).resolve()
    binary_path = Path(args.binary).resolve()

    if not loadp2_path.exists():
        print(f"[ERROR] loadp2 executable not found: {loadp2_path}")
        return 1
    if not binary_path.exists():
        print(f"[ERROR] binary file not found: {binary_path}")
        return 1

    cmd = build_loadp2_command(
        loadp2_path=loadp2_path,
        binary_path=binary_path,
        mode=args.mode,
        port=args.port,
        verbose=args.verbose,
    )
    print("[INFO] Running:", " ".join(cmd))
    return run_loader_command(cmd)


class Spin2IDE:
    # SPIN2 syntax highlighting keywords
    KEYWORDS = {
        "pub", "pri", "var", "dat", "obj", "con", "if", "else", "elseif",
        "repeat", "while", "until", "case", "from", "to", "step", "abort",
        "return", "quit", "next", "byte", "word", "long", "float"
    }
    
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Propeller 2 Mini IDE")
        self.root.geometry("1200x700")
        self._icon_image = None
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.worker_thread: threading.Thread | None = None
        
        self.current_file: Path | None = None
        self.current_binary: Path | None = None
        self.file_modified = False
        
        self.mode_var = tk.StringVar(value="flash")
        self.port_var = tk.StringVar(value="")
        self.verbose_var = tk.BooleanVar(value=True)
        self.loadp2_var = tk.StringVar(value=str(DEFAULT_LOADP2))
        self.flexspin_var = tk.StringVar(value=str(DEFAULT_FLEXSPIN))
        
        self._set_app_icon()
        self._build_ui()
        self.refresh_ports()
        self.root.after(100, self._pump_output)
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
    def _set_app_icon(self) -> None:
        png_path = get_prop_png_path()
        if png_path is None:
            return
        try:
            icon = tk.PhotoImage(file=str(png_path))
            self._icon_image = icon
            self.root.iconphoto(True, icon)
        except Exception:
            pass
    
    def _build_ui(self) -> None:
        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open SPIN2...", command=self._file_open)
        file_menu.add_command(label="Save", command=self._file_save)
        file_menu.add_command(label="Save As...", command=self._file_save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_closing)
        
        edit_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Clear Output", command=self._clear_output)
        
        # Notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Tab 1: Editor
        self._build_editor_tab()
        
        # Tab 2: Loader
        self._build_loader_tab()
        
    def _build_editor_tab(self) -> None:
        editor_frame = ttk.Frame(self.notebook)
        self.notebook.add(editor_frame, text="Editor")
        editor_frame.columnconfigure(0, weight=1)
        editor_frame.rowconfigure(1, weight=1)
        
        # Toolbar
        toolbar = ttk.Frame(editor_frame)
        toolbar.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        ttk.Button(toolbar, text="Open", command=self._file_open).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Save", command=self._file_save).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", padx=5, fill="y")
        
        ttk.Button(toolbar, text="Compile", command=self._compile_clicked).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Compile & Run", command=self._compile_and_run).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Show Prop_Hex", command=self._show_prop_hex).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", padx=5, fill="y")
        
        ttk.Button(toolbar, text="Reset Target", command=self._reset_target).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Enter TAQOZ", command=self._enter_taqoz_mode).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Load to RAM", command=lambda: self._load_clicked("ram")).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Load to FLASH", command=lambda: self._load_clicked("flash")).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Erase FLASH", command=self.erase_clicked).pack(side="left", padx=2)
        
        self.file_label = ttk.Label(toolbar, text="No file opened", foreground="gray")
        self.file_label.pack(side="left", padx=20)
        
        # Text editor with syntax highlighting
        text_frame = ttk.Frame(editor_frame)
        text_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        self.editor = tk.Text(text_frame, wrap="word", font=("Courier", 10), undo=True, maxundo=-1)
        self.editor.grid(row=0, column=0, sticky="nsew")
        self.editor.bind("<KeyRelease>", self._on_editor_change)
        self.editor.bind("<Control-s>", lambda e: self._file_save())
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.editor.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.editor.config(yscrollcommand=scrollbar.set)
        
        # Configure syntax highlighting tags
        self.editor.tag_config("keyword", foreground="#0066cc", font=("Courier", 10, "bold"))
        self.editor.tag_config("comment", foreground="#666666", font=("Courier", 10, "italic"))
        self.editor.tag_config("string", foreground="#cc0000")
        
        # Output panel
        output_label = ttk.Label(editor_frame, text="Compilation Output:")
        output_label.grid(row=2, column=0, sticky="w", padx=5, pady=(10, 2))
        
        self.output = tk.Text(editor_frame, height=8, wrap="word", font=("Courier", 9))
        self.output.grid(row=3, column=0, sticky="nsew", padx=5, pady=5)
        editor_frame.rowconfigure(3, weight=0)
        
        output_scrollbar = ttk.Scrollbar(editor_frame, orient="vertical", command=self.output.yview)
        output_scrollbar.grid(row=3, column=1, sticky="ns", padx=(0, 5))
        self.output.config(yscrollcommand=output_scrollbar.set, state="disabled")
        
    def _build_loader_tab(self) -> None:
        loader_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(loader_frame, text="Loader")
        loader_frame.columnconfigure(1, weight=1)
        
        ttk.Label(loader_frame, text="Binary file:").grid(row=0, column=0, sticky="w")
        binary_entry = ttk.Entry(loader_frame, state="readonly")
        binary_entry.grid(row=0, column=1, sticky="ew", padx=6)
        self.binary_var = tk.StringVar()
        binary_entry.config(textvariable=self.binary_var)
        ttk.Button(loader_frame, text="Browse...", command=self._browse_binary).grid(row=0, column=2)
        
        ttk.Label(loader_frame, text="loadp2.exe:").grid(row=1, column=0, sticky="w")
        ttk.Entry(loader_frame, textvariable=self.loadp2_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(loader_frame, text="Browse...", command=self._browse_loadp2).grid(row=1, column=2)
        
        ttk.Label(loader_frame, text="COM port:").grid(row=2, column=0, sticky="w")
        self.port_combo = ttk.Combobox(loader_frame, textvariable=self.port_var, values=[], width=20)
        self.port_combo.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Button(loader_frame, text="Refresh", command=self.refresh_ports).grid(row=2, column=2)
        
        ttk.Checkbutton(loader_frame, text="Verbose (-v)", variable=self.verbose_var).grid(row=3, column=1, sticky="w", padx=6)
        
        button_frame = ttk.Frame(loader_frame)
        button_frame.grid(row=3, column=2, sticky="e")
        self.run_button = ttk.Button(button_frame, text="Load to RAM", command=lambda: self._load_clicked("ram"))
        self.run_button.pack(side="left", padx=2)
        self.flash_button = ttk.Button(button_frame, text="Load to FLASH", command=lambda: self._load_clicked("flash"))
        self.flash_button.pack(side="left", padx=2)
        self.erase_button = ttk.Button(button_frame, text="Erase Flash", command=self.erase_clicked)
        self.erase_button.pack(side="left", padx=2)
        
        info = ttk.Label(loader_frame, text="Note: Use the Editor toolbar for quick access to Load, Reset, and Erase buttons.", foreground="gray")
        info.grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 0))
        
        loader_frame.rowconfigure(5, weight=1)
    
    def _on_editor_change(self, event: tk.Event | None = None) -> None:
        if not self.file_modified and self.current_file:
            self.file_modified = True
            self._update_title()
    
    def _update_title(self) -> None:
        if self.current_file:
            title = f"Propeller 2 Mini IDE - {self.current_file.name}"
            if self.file_modified:
                title += " *"
            self.root.title(title)
    
    def _file_open(self) -> None:
        if self.file_modified:
            resp = messagebox.askyesnocancel("Unsaved Changes", "Save changes before opening?")
            if resp is None:
                return
            if resp:
                self._file_save()
        
        path = filedialog.askopenfilename(
            title="Open SPIN2 file",
            filetypes=[("SPIN2 files", "*.spin2"), ("All files", "*.*")],
            initialdir=str(REPO_ROOT),
        )
        if path:
            self.current_file = Path(path)
            try:
                content = self.current_file.read_text()
                self.editor.delete("1.0", "end")
                self.editor.insert("1.0", content)
                self.file_modified = False
                self._update_title()
                self.file_label.config(text=f"Opened: {self.current_file.name}")
                self._syntax_highlight()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open file: {e}")
    
    def _file_save(self) -> None:
        if not self.current_file:
            self._file_save_as()
            return
        
        try:
            content = self.editor.get("1.0", "end-1c")
            self.current_file.write_text(content)
            self.file_modified = False
            self._update_title()
            self._append_output(f"[INFO] File saved: {self.current_file.name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {e}")
    
    def _file_save_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save SPIN2 file",
            filetypes=[("SPIN2 files", "*.spin2"), ("All files", "*.*")],
            initialdir=str(REPO_ROOT),
        )
        if path:
            self.current_file = Path(path)
            self._file_save()
    
    def _syntax_highlight(self) -> None:
        """Apply syntax highlighting to editor."""
        self.editor.tag_remove("keyword", "1.0", "end")
        self.editor.tag_remove("comment", "1.0", "end")
        self.editor.tag_remove("string", "1.0", "end")
        
        content = self.editor.get("1.0", "end")
        
        # Highlight comments
        for match in re.finditer(r"'[^\n]*", content):
            start = self.editor.index(f"1.0 + {match.start()} chars")
            end = self.editor.index(f"1.0 + {match.end()} chars")
            self.editor.tag_add("comment", start, end)
        
        # Highlight strings
        for match in re.finditer(r'"[^"]*"', content):
            start = self.editor.index(f"1.0 + {match.start()} chars")
            end = self.editor.index(f"1.0 + {match.end()} chars")
            self.editor.tag_add("string", start, end)
        
        # Highlight keywords
        for match in re.finditer(r"\b([a-zA-Z_]\w*)\b", content):
            word = match.group(1).lower()
            if word in self.KEYWORDS:
                start = self.editor.index(f"1.0 + {match.start()} chars")
                end = self.editor.index(f"1.0 + {match.end()} chars")
                self.editor.tag_add("keyword", start, end)
    
    def _compile_clicked(self) -> None:
        if not self.current_file:
            messagebox.showwarning("Warning", "No file opened. Please open a SPIN2 file first.")
            return
        
        # Auto-save before compile
        self._file_save()
        
        self._append_output(f"\n[INFO] Compiling {self.current_file.name}...")
        self.run_button.configure(state="disabled")
        self.flash_button.configure(state="disabled")
        
        def worker() -> None:
            flexspin_path = Path(self.flexspin_var.get()).resolve()
            code, output = compile_spin2(flexspin_path, self.current_file)
            
            self.output_queue.put(output)
            
            if code == 0:
                # Find the generated .binary file
                binary_path = self.current_file.with_suffix(".binary")
                if binary_path.exists():
                    self.current_binary = binary_path
                    # Auto-populate binary field in Loader tab
                    self.binary_var.set(str(binary_path))
                    self.output_queue.put(f"[OK] Compilation successful: {binary_path.name}")
                    self.output_queue.put(f"[INFO] Binary ready to load: {binary_path.name}")
                else:
                    self.output_queue.put(f"[WARN] Binary file not found at {binary_path}")
            else:
                self.output_queue.put(f"[ERROR] Compilation failed with code {code}")
            
            self.root.after(0, lambda: (
                self.run_button.configure(state="normal"),
                self.flash_button.configure(state="normal"),
            ))
        
        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()
    
    def _compile_and_run(self) -> None:
        """Compile and immediately load to RAM."""
        if not self.current_file:
            messagebox.showwarning("Warning", "No file opened. Please open a SPIN2 file first.")
            return
        
        # First compile
        self._append_output(f"\n[INFO] Compiling and running {self.current_file.name}...")
        self._compile_clicked()
        
        # After compile succeeds, schedule load to RAM
        def check_and_load():
            if self.current_binary and self.current_binary.exists():
                self._append_output("[INFO] Starting program on board...")
                self._load_clicked("ram")
            else:
                self._append_output("[WARN] Compilation may have failed, skipping run")
            self.root.after_cancel(check_id)
        
        check_id = self.root.after(2000, check_and_load)
    
    def _show_prop_hex(self) -> None:
        """Generate and display a Prop_Hex command for the latest compiled binary."""
        binary_path = Path(self.binary_var.get()).resolve() if self.binary_var.get() else None
        if not binary_path or not binary_path.exists():
            messagebox.showerror("Error", "No valid binary file. Compile a SPIN2 file first.")
            return
        try:
            data = binary_path.read_bytes()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read binary: {e}")
            return
        if not data:
            messagebox.showwarning("Warning", "Binary is empty")
            return
        # Format bytes as hex pairs
        hex_pairs = " ".join(f"{b:02x}" for b in data)
        prop_hex = f"Prop_Hex 0 0 0 0 {hex_pairs} ~"
        self._show_hex_dialog(prop_hex, binary_path.name)
    
    def _show_hex_dialog(self, hex_cmd: str, filename: str) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Prop_Hex - {filename}")
        dlg.geometry("900x420")
        
        lbl = ttk.Label(dlg, text=f"Prop_Hex command for {filename}", font=("Segoe UI", 10, "bold"))
        lbl.pack(pady=6)
        
        frame = ttk.Frame(dlg)
        frame.pack(fill="both", expand=True, padx=8, pady=6)
        
        txt = tk.Text(frame, wrap="word", font=("Courier", 9))
        txt.insert("1.0", hex_cmd)
        txt.config(state="disabled")
        txt.pack(side="left", fill="both", expand=True)
        
        scr = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        scr.pack(side="right", fill="y")
        txt.config(yscrollcommand=scr.set)
        
        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(pady=8)
        
        def copy():
            try:
                dlg.clipboard_clear()
                dlg.clipboard_append(hex_cmd)
                messagebox.showinfo("Copied", "Prop_Hex command copied to clipboard")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy to clipboard: {e}")
        
        ttk.Button(btn_frame, text="Copy to Clipboard", command=copy).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Close", command=dlg.destroy).pack(side="left", padx=6)
    
    def _reset_target(self) -> None:
        """Reset the Propeller 2 target board."""
        loadp2_path = Path(self.loadp2_var.get()).resolve()
        port = self.port_var.get().strip() or None
        
        if not port:
            messagebox.showerror("Error", "No COM port selected")
            return
        
        if not loadp2_path.exists():
            messagebox.showerror("Error", f"loadp2 not found:\n{loadp2_path}")
            return
        
        self._append_output("[INFO] Resetting target...")
        # Use loadp2 with -p option only (triggers DTR reset)
        cmd = [str(loadp2_path), "-p", port]
        self._start_command(cmd)
    
    def _enter_taqoz_mode(self) -> None:
        """Enter TAQOZ mode: reset chip and send TAQOZ entry sequence."""
        if not serial:
            messagebox.showerror("Error", "pyserial not installed. Cannot enter TAQOZ mode.")
            return
        
        port = self.port_var.get().strip() or None
        if not port:
            messagebox.showerror("Error", "No COM port selected")
            return
        
        try:
            self._append_output("[INFO] Entering TAQOZ mode...")
            
            # Open serial port
            ser = serial.Serial(port, 115200, timeout=1)
            
            # Reset: toggle DTR to trigger reset
            self._append_output("[INFO] Resetting chip...")
            ser.dtr = True
            time.sleep(0.1)
            ser.dtr = False
            time.sleep(0.5)
            
            # Send TAQOZ entry sequence: $3E,$20,$1B
            taqoz_seq = bytes([0x3E, 0x20, 0x1B])
            self._append_output(f"[INFO] Sending TAQOZ sequence: {taqoz_seq.hex().upper()}...")
            ser.write(taqoz_seq)
            
            time.sleep(0.2)
            ser.close()
            
            self._append_output("[OK] TAQOZ mode entered - board is ready for TAQOZ commands")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to enter TAQOZ mode: {e}")
            self._append_output(f"[ERROR] {e}")
    

    def _load_clicked(self, mode: str) -> None:
        """Load binary to RAM or FLASH."""
        if self.worker_thread and self.worker_thread.is_alive():
            return
        
        binary_path = Path(self.binary_var.get()).resolve() if self.binary_var.get() else None
        if not binary_path or not binary_path.exists():
            messagebox.showerror("Error", "No valid binary file. Compile a SPIN2 file first or browse to a binary.")
            return
        
        loadp2_path = Path(self.loadp2_var.get()).resolve()
        port = self.port_var.get().strip() or None
        verbose = self.verbose_var.get()
        
        if not loadp2_path.exists():
            messagebox.showerror("Error", f"loadp2 not found:\n{loadp2_path}")
            return
        
        cmd = build_loadp2_command(
            loadp2_path=loadp2_path,
            binary_path=binary_path,
            mode=mode,
            port=port,
            verbose=verbose,
        )
        self._start_command(cmd)
    
    def _browse_binary(self) -> None:
        path = filedialog.askopenfilename(
            title="Select program binary",
            filetypes=[("Binary files", "*.binary *.bin *.elf"), ("All files", "*.*")],
            initialdir=str(REPO_ROOT),
        )
        if path:
            self.binary_var.set(path)
            self.current_binary = Path(path)
    
    def _browse_loadp2(self) -> None:
        path = filedialog.askopenfilename(
            title="Select loadp2 executable",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
            initialdir=str(REPO_ROOT / "bin"),
        )
        if path:
            self.loadp2_var.set(path)
    
    def refresh_ports(self) -> None:
        ports = list_com_ports()
        self.port_combo["values"] = ports
        if not self.port_var.get() and ports:
            detected = autodetect_propeller_port()
            if detected:
                self.port_var.set(detected)
            else:
                self.port_var.set(ports[0])
    
    def _append_output(self, text: str) -> None:
        self.output.config(state="normal")
        self.output.insert("end", text + "\n")
        self.output.see("end")
        self.output.config(state="disabled")
    
    def _clear_output(self) -> None:
        self.output.config(state="normal")
        self.output.delete("1.0", "end")
        self.output.config(state="disabled")
    
    def _pump_output(self) -> None:
        while True:
            try:
                line = self.output_queue.get_nowait()
            except queue.Empty:
                break
            self._append_output(line.rstrip())
        self.root.after(100, self._pump_output)
    
    def erase_clicked(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return
        
        loadp2_path = Path(self.loadp2_var.get()).resolve()
        port = self.port_var.get().strip() or None
        verbose = self.verbose_var.get()
        
        if not loadp2_path.exists():
            messagebox.showerror("Error", f"loadp2 not found:\n{loadp2_path}")
            return
        
        confirmed = messagebox.askyesno(
            "Erase Flash",
            "This will overwrite the flash boot image with an erased pattern.\nContinue?",
        )
        if not confirmed:
            return
        
        with tempfile.NamedTemporaryFile(prefix="p2_erase_", suffix=".binary", delete=False) as tmp:
            tmp.write(b"\xFF" * 512)
            erase_path = Path(tmp.name)
        
        cmd = build_loadp2_command(
            loadp2_path=loadp2_path,
            binary_path=erase_path,
            mode="flash",
            port=port,
            verbose=verbose,
        )
        self._start_command(cmd, cleanup_path=erase_path)
    
    def _start_command(self, cmd: list[str], cleanup_path: Path | None = None) -> None:
        self._append_output("[INFO] Running: " + " ".join(cmd))
        self.run_button.configure(state="disabled")
        self.flash_button.configure(state="disabled")
        self.erase_button.configure(state="disabled")
        
        def worker() -> None:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                self.output_queue.put(line.rstrip())
            code = process.wait()
            self.output_queue.put(f"[INFO] Exit code: {code}")
            if cleanup_path is not None:
                try:
                    os.remove(cleanup_path)
                except OSError:
                    pass
            self.root.after(0, lambda: (
                self.run_button.configure(state="normal"),
                self.flash_button.configure(state="normal"),
                self.erase_button.configure(state="normal"),
            ))
        
        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()
    
    def _on_closing(self) -> None:
        if self.file_modified:
            resp = messagebox.askyesnocancel("Unsaved Changes", "Save changes before closing?")
            if resp is None:
                return
            if resp:
                self._file_save()
        self.root.destroy()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Propeller 2 loadp2 wrapper with CLI and GUI modes."
    )
    parser.add_argument("--gui", action="store_true", help="Launch GUI mode")
    parser.add_argument(
        "--mode",
        choices=["ram", "flash"],
        default="flash",
        help="Load mode for CLI (default: flash)",
    )
    parser.add_argument("--binary", help="Path to .binary/.bin/.elf file for CLI mode")
    parser.add_argument("--port", help="COM port (e.g., COM6). If omitted, loadp2 auto-detects.")
    parser.add_argument("--verbose", action="store_true", help="Pass -v to loadp2")
    parser.add_argument(
        "--loadp2",
        default=str(DEFAULT_LOADP2),
        help=f"Path to loadp2 executable (default: {DEFAULT_LOADP2})",
    )
    return parser


def main() -> int:
    if len(sys.argv) == 1:
        root = tk.Tk()
        Spin2IDE(root)
        root.mainloop()
        return 0

    parser = build_parser()
    args = parser.parse_args()

    if args.gui:
        root = tk.Tk()
        Spin2IDE(root)
        root.mainloop()
        return 0

    if not args.binary:
        parser.error("CLI mode requires --binary (or use --gui).")

    return run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
