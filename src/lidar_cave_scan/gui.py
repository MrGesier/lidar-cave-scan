"""Desktop GUI for LiDAR Cave Scan."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk


class CaveScanApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("LiDAR Cave Scan")
        self.geometry("1180x760")
        self.minsize(980, 640)
        self.configure(bg="#eef1ed")

        self.project_root = Path(__file__).resolve().parents[2]
        self.python = sys.executable
        self.log_queue: queue.Queue[str] = queue.Queue()

        self.dem_path = tk.StringVar()
        self.out_dir = tk.StringVar(value=str(self.project_root / "outputs" / "gui_run"))
        self.bbox = tk.StringVar()
        self.min_depth = tk.DoubleVar(value=0.5)
        self.min_area = tk.DoubleVar(value=10.0)
        self.max_area = tk.DoubleVar(value=10000.0)
        self.catalog_bbox = tk.StringVar(value="-0.25 43.0 -0.05 43.15")
        self.catalog_start = tk.StringVar(value="2025-01-01")
        self.catalog_end = tk.StringVar(value="2025-02-01")
        self.status_text = tk.StringVar(value="Prêt")

        self._build_styles()
        self._build_ui()

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background="#eef1ed", foreground="#13201b")
        style.configure("Root.TFrame", background="#eef1ed")
        style.configure("Header.TFrame", background="#173b35")
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), background="#173b35", foreground="#ffffff")
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), background="#173b35", foreground="#dbe8df")
        style.configure("Panel.TFrame", padding=16, background="#f8f7f2", relief="flat")
        style.configure("Card.TFrame", padding=12, background="#ffffff", relief="solid", borderwidth=1)
        style.configure("Accent.TButton", padding=(14, 9), font=("Segoe UI", 10, "bold"))
        style.configure("Quiet.TButton", padding=(10, 8))
        style.configure("TNotebook", background="#eef1ed", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 8))
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")])

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14, style="Root.TFrame")
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root, padding=(18, 16), style="Header.TFrame")
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="LiDAR Cave Scan", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Console exploratoire pour repérer, classer et documenter des dépressions de surface.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 0))

        body = ttk.PanedWindow(root, orient="horizontal")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, style="Panel.TFrame")
        right = ttk.Frame(body, style="Panel.TFrame")
        body.add(left, weight=3)
        body.add(right, weight=2)

        notebook = ttk.Notebook(left)
        notebook.pack(fill="both", expand=True)
        notebook.add(self._lidar_tab(notebook), text="Analyse LiDAR")
        notebook.add(self._demo_tab(notebook), text="Démo")
        notebook.add(self._catalog_tab(notebook), text="Catalogue SAR")

        ttk.Label(right, text="Aperçu", font=("Segoe UI", 13, "bold"), background="#f8f7f2").pack(anchor="w")
        self.preview = tk.Canvas(right, height=310, bg="#fbfaf5", highlightthickness=1, highlightbackground="#c9c1b2")
        self.preview.pack(fill="x", pady=(8, 14))
        self._draw_preview()

        quick = ttk.Frame(right, style="Panel.TFrame")
        quick.pack(fill="x", pady=(0, 12))
        ttk.Button(quick, text="Rapport HTML", command=self._open_report, style="Quiet.TButton").pack(side="left")
        ttk.Button(quick, text="Carte PNG", command=self._open_map, style="Quiet.TButton").pack(side="left", padx=8)
        ttk.Button(quick, text="Dossier résultats", command=self._open_output, style="Quiet.TButton").pack(side="left")

        ttk.Label(right, text="Journal", font=("Segoe UI", 13, "bold"), background="#f8f7f2").pack(anchor="w")
        self.log = tk.Text(
            right,
            height=16,
            wrap="word",
            borderwidth=0,
            relief="flat",
            bg="#111916",
            fg="#e8f0ea",
            insertbackground="#e8f0ea",
            font=("Cascadia Mono", 9),
        )
        self.log.pack(fill="both", expand=True, pady=(8, 0))

        status = ttk.Label(root, textvariable=self.status_text, anchor="w")
        status.pack(fill="x", pady=(10, 0))
        self._log("Interface prête. Choisis un MNT GeoTIFF ou lance la démo synthétique.")
        self.after(100, self._drain_log_queue)

    def _lidar_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14)
        self._path_row(frame, "MNT GeoTIFF", self.dem_path, self._choose_dem, 0)
        self._path_row(frame, "Dossier de sortie", self.out_dir, self._choose_out_dir, 1)

        ttk.Label(frame, text="BBox optionnelle (XMIN YMIN XMAX YMAX)").grid(row=2, column=0, sticky="w", pady=8)
        ttk.Entry(frame, textvariable=self.bbox).grid(row=2, column=1, sticky="ew", padx=(10, 6), pady=8)

        params = ttk.Frame(frame)
        params.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 12))
        self._number_field(params, "Profondeur min. (m)", self.min_depth, 0)
        self._number_field(params, "Surface min. (m²)", self.min_area, 1)
        self._number_field(params, "Surface max. (m²)", self.max_area, 2)

        actions = ttk.Frame(frame)
        actions.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Lancer l'analyse", command=self._run_lidar, style="Accent.TButton").pack(side="left")
        ttk.Button(actions, text="Ouvrir les résultats", command=self._open_output, style="Quiet.TButton").pack(side="left", padx=8)
        ttk.Button(actions, text="Rapport HTML", command=self._open_report, style="Quiet.TButton").pack(side="left")

        frame.columnconfigure(1, weight=1)
        return frame

    def _demo_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14)
        ttk.Label(
            frame,
            text=(
                "La démo crée un petit MNT synthétique avec plusieurs cuvettes, "
                "puis lance l'analyse LiDAR dessus."
            ),
            wraplength=600,
        ).pack(anchor="w", pady=(0, 12))
        ttk.Button(frame, text="Créer et analyser un MNT de test", command=self._run_demo_dem, style="Accent.TButton").pack(anchor="w")
        ttk.Button(frame, text="Lancer la démo micro-Doppler", command=self._run_microdoppler_demo, style="Quiet.TButton").pack(anchor="w", pady=8)
        ttk.Button(frame, text="Ouvrir les résultats", command=self._open_output, style="Quiet.TButton").pack(anchor="w")
        return frame

    def _catalog_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14)
        ttk.Label(frame, text="BBox WGS84 (WEST SOUTH EAST NORTH)").grid(row=0, column=0, sticky="w", pady=8)
        ttk.Entry(frame, textvariable=self.catalog_bbox).grid(row=0, column=1, sticky="ew", padx=10, pady=8)
        ttk.Label(frame, text="Date début").grid(row=1, column=0, sticky="w", pady=8)
        ttk.Entry(frame, textvariable=self.catalog_start).grid(row=1, column=1, sticky="ew", padx=10, pady=8)
        ttk.Label(frame, text="Date fin").grid(row=2, column=0, sticky="w", pady=8)
        ttk.Entry(frame, textvariable=self.catalog_end).grid(row=2, column=1, sticky="ew", padx=10, pady=8)
        ttk.Button(frame, text="Rechercher les acquisitions", command=self._run_catalog, style="Accent.TButton").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )
        frame.columnconfigure(1, weight=1)
        return frame

    def _path_row(self, frame, label, variable, command, row):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=8)
        ttk.Entry(frame, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=(10, 6), pady=8)
        ttk.Button(frame, text="Parcourir", command=command).grid(row=row, column=2, sticky="e", pady=8)

    def _number_field(self, frame, label, variable, column):
        group = ttk.Frame(frame)
        group.grid(row=0, column=column, sticky="ew", padx=(0, 10))
        ttk.Label(group, text=label).pack(anchor="w")
        ttk.Entry(group, textvariable=variable, width=14).pack(anchor="w", pady=(4, 0))
        frame.columnconfigure(column, weight=1)

    def _draw_preview(self) -> None:
        self.preview.delete("all")
        w = 620
        h = 300
        self.preview.create_rectangle(0, 0, w, h, fill="#fbfaf5", outline="")
        for i in range(30):
            color = "#e4dfd4" if i % 2 == 0 else "#d8d0c0"
            self.preview.create_line(-20, 20 + i * 9, w, 2 + i * 10, fill=color)
        self.preview.create_rectangle(18, 20, 180, 54, fill="#173b35", outline="")
        self.preview.create_text(32, 37, anchor="w", text="Score exploratoire", fill="white", font=("Segoe UI", 10, "bold"))
        depressions = [
            (120, 142, 58, "#d7191c", "A 82"),
            (300, 175, 44, "#f28e2b", "B 61"),
            (415, 105, 32, "#2c7bb6", "C 43"),
        ]
        for x, y, r, color, label in depressions:
            self.preview.create_oval(x - r + 5, y - r + 5, x + r + 5, y + r + 5, outline="", fill="#e5ded0")
            self.preview.create_oval(x - r, y - r, x + r, y + r, outline=color, width=3)
            self.preview.create_text(x, y, text=label, fill=color, font=("Segoe UI", 12, "bold"))
        self.preview.create_text(
            16,
            h - 26,
            anchor="w",
            text="Les vrais résultats: report.html, map.png, candidates.csv, candidates.geojson",
            fill="#3f3a33",
            font=("Segoe UI", 9),
        )

    def _choose_dem(self) -> None:
        path = filedialog.askopenfilename(
            title="Choisir un MNT GeoTIFF",
            filetypes=[("GeoTIFF", "*.tif *.tiff"), ("Tous les fichiers", "*.*")],
        )
        if path:
            self.dem_path.set(path)

    def _choose_out_dir(self) -> None:
        path = filedialog.askdirectory(title="Choisir le dossier de sortie")
        if path:
            self.out_dir.set(path)

    def _run_lidar(self) -> None:
        if not self.dem_path.get().strip():
            messagebox.showwarning("MNT manquant", "Choisis d'abord un GeoTIFF de MNT.")
            return
        cmd = [
            self.python,
            str(self.project_root / "app.py"),
            "lidar",
            "--dem",
            self.dem_path.get(),
            "--out",
            self.out_dir.get(),
            "--min-depth",
            str(self.min_depth.get()),
            "--min-area",
            str(self.min_area.get()),
            "--max-area",
            str(self.max_area.get()),
        ]
        bbox = self.bbox.get().strip()
        if bbox:
            values = bbox.split()
            if len(values) != 4:
                messagebox.showwarning("BBox invalide", "La bbox doit contenir 4 nombres.")
                return
            cmd.extend(["--bbox", *values])
        self._run_command(cmd)

    def _run_demo_dem(self) -> None:
        demo_dem = self.project_root / "examples" / "demo_dem.tif"
        demo_out = self.project_root / "outputs" / "demo_lidar"
        cmd = [self.python, str(self.project_root / "examples" / "create_demo_dem.py"), "--out", str(demo_dem)]
        self._run_command(cmd, next_command=[self.python, str(self.project_root / "app.py"), "lidar", "--dem", str(demo_dem), "--out", str(demo_out)])
        self.dem_path.set(str(demo_dem))
        self.out_dir.set(str(demo_out))

    def _run_microdoppler_demo(self) -> None:
        out = self.project_root / "outputs" / "microdoppler_demo"
        self.out_dir.set(str(out))
        self._run_command([self.python, str(self.project_root / "app.py"), "microdoppler", "--demo", "--out", str(out)])

    def _run_catalog(self) -> None:
        bbox = self.catalog_bbox.get().split()
        if len(bbox) != 4:
            messagebox.showwarning("BBox invalide", "La bbox doit contenir 4 nombres.")
            return
        out = self.project_root / "outputs" / "sar_catalog.json"
        self.out_dir.set(str(out.parent))
        self._run_command(
            [
                self.python,
                str(self.project_root / "app.py"),
                "catalog",
                "--bbox",
                *bbox,
                "--start",
                self.catalog_start.get(),
                "--end",
                self.catalog_end.get(),
                "--out",
                str(out),
            ]
        )

    def _run_command(self, cmd: list[str], next_command: list[str] | None = None) -> None:
        self._log("")
        self._log("> " + " ".join(f'"{part}"' if " " in part else part for part in cmd))
        self._set_status("Analyse en cours...")
        thread = threading.Thread(target=self._worker, args=(cmd, next_command), daemon=True)
        thread.start()

    def _worker(self, cmd: list[str], next_command: list[str] | None) -> None:
        code = self._execute(cmd)
        if code == 0 and next_command:
            self._log("> " + " ".join(f'"{part}"' if " " in part else part for part in next_command))
            code = self._execute(next_command)
        if code == 0:
            self._log("Terminé.")
            self._set_status("Terminé - résultats disponibles")
        else:
            self._log(f"Commande arrêtée avec le code {code}.")
            self._set_status("Erreur pendant l'exécution")

    def _execute(self, cmd: list[str]) -> int:
        env = os.environ.copy()
        pythonpath = str(self.project_root / "src")
        env["PYTHONPATH"] = pythonpath + os.pathsep + env.get("PYTHONPATH", "")
        process = subprocess.Popen(
            cmd,
            cwd=self.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        assert process.stdout is not None
        for line in process.stdout:
            self._log(line.rstrip())
        return process.wait()

    def _open_output(self) -> None:
        path = Path(self.out_dir.get())
        if path.suffix:
            path = path.parent
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)

    def _open_report(self) -> None:
        path = self._output_file("report.html")
        if path.exists():
            webbrowser.open(path.resolve().as_uri())
        else:
            messagebox.showinfo("Rapport absent", "Lance une analyse LiDAR pour générer report.html.")

    def _open_map(self) -> None:
        path = self._output_file("map.png")
        if path.exists():
            os.startfile(path)
        else:
            messagebox.showinfo("Carte absente", "Lance une analyse LiDAR pour générer map.png.")

    def _output_file(self, name: str) -> Path:
        path = Path(self.out_dir.get())
        if path.suffix:
            path = path.parent
        return path / name

    def _log(self, text: str) -> None:
        self.log_queue.put(text)

    def _set_status(self, text: str) -> None:
        self.after(0, lambda: self.status_text.set(text))

    def _drain_log_queue(self) -> None:
        while True:
            try:
                text = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log.insert("end", text + "\n")
            self.log.see("end")
        self.after(100, self._drain_log_queue)


def main() -> None:
    app = CaveScanApp()
    app.mainloop()


if __name__ == "__main__":
    main()
