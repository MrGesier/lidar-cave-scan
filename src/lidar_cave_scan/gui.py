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

from .science import SCIENCE_SECTIONS, STUDIES


class Tooltip:
    def __init__(self, widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None) -> None:
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip,
            text=self.text,
            justify="left",
            wraplength=360,
            bg="#10201b",
            fg="#ffffff",
            padx=10,
            pady=8,
            font=("Segoe UI", 9),
        )
        label.pack()

    def _hide(self, _event=None) -> None:
        if self.tip:
            self.tip.destroy()
            self.tip = None


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

        demo_dem = self.project_root / "examples" / "demo_dem.tif"
        demo_out = self.project_root / "outputs" / "demo_lidar"
        self.dem_path = tk.StringVar(value=str(demo_dem) if demo_dem.exists() else "")
        self.out_dir = tk.StringVar(value=str(demo_out))
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
        notebook.add(self._lidar_tab(notebook), text="1. Analyser")
        notebook.add(self._demo_tab(notebook), text="2. Tester")
        notebook.add(self._understand_tab(notebook), text="Comprendre")
        notebook.add(self._catalog_tab(notebook), text="SAR")

        ttk.Label(right, text="Ce que tu dois regarder", font=("Segoe UI", 13, "bold"), background="#f8f7f2").pack(anchor="w")
        guide = ttk.Frame(right, style="Card.TFrame")
        guide.pack(fill="x", pady=(8, 12))
        for text in [
            "1. Lance une analyse ou la démo.",
            "2. Ouvre la carte interactive pour te situer.",
            "3. Clique un candidat pour voir coordonnées et liens.",
            "4. Lis candidate_locations.csv pour trier les lieux.",
        ]:
            ttk.Label(guide, text=text, background="#ffffff").pack(anchor="w", pady=2)

        ttk.Label(right, text="Aperçu simplifié", font=("Segoe UI", 13, "bold"), background="#f8f7f2").pack(anchor="w")
        self.preview = tk.Canvas(right, height=310, bg="#fbfaf5", highlightthickness=1, highlightbackground="#c9c1b2")
        self.preview.pack(fill="x", pady=(8, 14))
        self._draw_preview()

        quick = ttk.Frame(right, style="Panel.TFrame")
        quick.pack(fill="x", pady=(0, 12))
        map_button = ttk.Button(quick, text="Carte interactive", command=self._open_interactive_map, style="Accent.TButton")
        map_button.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 8))
        Tooltip(map_button, "Ouvre interactive_map.html: c'est la carte à utiliser pour zoomer, dézoomer et cliquer sur les candidats.")
        locations_button = ttk.Button(quick, text="Liste des lieux", command=self._open_locations, style="Quiet.TButton")
        locations_button.grid(row=0, column=1, sticky="ew", pady=(0, 8))
        Tooltip(locations_button, "Ouvre candidate_locations.csv avec latitude, longitude et liens Google Maps/OpenStreetMap.")
        report_button = ttk.Button(quick, text="Rapport HTML", command=self._open_report, style="Quiet.TButton")
        report_button.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        Tooltip(report_button, "Ouvre un rapport lisible avec carte, tableau, interprétation et limites.")
        folder_button = ttk.Button(quick, text="Dossier résultats", command=self._open_output, style="Quiet.TButton")
        folder_button.grid(row=1, column=1, sticky="ew")
        Tooltip(folder_button, "Ouvre le dossier qui contient tous les fichiers produits par l'analyse.")
        quick.columnconfigure(0, weight=1)
        quick.columnconfigure(1, weight=1)

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
        self._log("Interface prête. La démo est déjà chargée si examples/demo_dem.tif existe.")
        self._log("Clique sur 'Carte interactive' après une analyse pour zoomer et obtenir les coordonnées GPS.")
        self.after(100, self._drain_log_queue)

    def _lidar_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14)
        intro = ttk.Frame(frame, style="Card.TFrame")
        intro.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 12))
        ttk.Label(
            intro,
            text="Analyse LiDAR en 3 étapes",
            font=("Segoe UI", 12, "bold"),
            background="#ffffff",
        ).pack(anchor="w")
        ttk.Label(
            intro,
            text="Choisis un MNT GeoTIFF, lance l'analyse, puis ouvre la carte interactive pour localiser les candidats.",
            wraplength=640,
            background="#ffffff",
        ).pack(anchor="w", pady=(4, 0))
        self._path_row(frame, "MNT GeoTIFF", self.dem_path, self._choose_dem, 1, "Le MNT est une grille d'altitudes. Il doit être géoréférencé pour obtenir de vraies coordonnées GPS.")
        self._path_row(frame, "Dossier de sortie", self.out_dir, self._choose_out_dir, 2, "Le dossier où seront générés la carte, le rapport, les CSV et les rasters.")

        bbox_label = ttk.Label(frame, text="BBox optionnelle (XMIN YMIN XMAX YMAX)")
        bbox_label.grid(row=3, column=0, sticky="w", pady=8)
        Tooltip(bbox_label, "Zone à découper dans les coordonnées du raster, souvent Lambert-93 en France. Laisse vide pour analyser tout le GeoTIFF.")
        bbox_entry = ttk.Entry(frame, textvariable=self.bbox)
        bbox_entry.grid(row=3, column=1, sticky="ew", padx=(10, 6), pady=8)
        Tooltip(bbox_entry, "Exemple Lambert-93: 420000 6242800 420240 6243000. Ne mets pas latitude/longitude ici.")

        params = ttk.Frame(frame)
        params.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 12))
        self._number_field(params, "Profondeur min. (m)", self.min_depth, 0, "Ignore les cuvettes moins profondes que ce seuil.")
        self._number_field(params, "Surface min. (m²)", self.min_area, 1, "Ignore les micro-formes trop petites ou bruyantes.")
        self._number_field(params, "Surface max. (m²)", self.max_area, 2, "Ignore les très grands bassins qui sont rarement des indices locaux.")

        actions = ttk.Frame(frame)
        actions.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        run_btn = ttk.Button(actions, text="Lancer l'analyse", command=self._run_lidar, style="Accent.TButton")
        run_btn.pack(side="left")
        Tooltip(run_btn, "Calcule les dépressions candidates et génère tous les fichiers de sortie.")
        ttk.Button(actions, text="Carte interactive", command=self._open_interactive_map, style="Quiet.TButton").pack(side="left", padx=8)
        ttk.Button(actions, text="Liste des lieux", command=self._open_locations, style="Quiet.TButton").pack(side="left")
        ttk.Button(actions, text="Rapport HTML", command=self._open_report, style="Quiet.TButton").pack(side="left", padx=8)
        ttk.Button(actions, text="Dossier", command=self._open_output, style="Quiet.TButton").pack(side="left")

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
        ttk.Button(frame, text="Ouvrir la carte interactive de démo", command=self._open_interactive_map, style="Quiet.TButton").pack(anchor="w", pady=8)
        ttk.Button(frame, text="Ouvrir la liste des lieux", command=self._open_locations, style="Quiet.TButton").pack(anchor="w")
        ttk.Button(frame, text="Lancer la démo micro-Doppler", command=self._run_microdoppler_demo, style="Quiet.TButton").pack(anchor="w", pady=8)
        ttk.Button(frame, text="Ouvrir le dossier résultats", command=self._open_output, style="Quiet.TButton").pack(anchor="w")
        return frame

    def _understand_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14)
        canvas = tk.Canvas(frame, bg="#f8f7f2", highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas, style="Panel.TFrame")
        content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(content, text="Comprendre l'outil", font=("Segoe UI", 15, "bold"), background="#f8f7f2").pack(anchor="w", pady=(0, 8))
        for item in SCIENCE_SECTIONS:
            box = ttk.Frame(content, style="Card.TFrame")
            box.pack(fill="x", pady=6)
            ttk.Label(box, text=item["title"], font=("Segoe UI", 11, "bold"), background="#ffffff").pack(anchor="w")
            ttk.Label(box, text=item["body"], wraplength=680, background="#ffffff").pack(anchor="w", pady=(3, 0))

        sources = ttk.Frame(content, style="Card.TFrame")
        sources.pack(fill="x", pady=(12, 6))
        ttk.Label(sources, text="Études et sources", font=("Segoe UI", 11, "bold"), background="#ffffff").pack(anchor="w")
        for study in STUDIES:
            ttk.Label(sources, text=f"- {study['label']}", wraplength=680, background="#ffffff").pack(anchor="w", pady=(6, 0))
            ttk.Label(sources, text=study["note"], wraplength=680, background="#ffffff", foreground="#4a5550").pack(anchor="w")
        ttk.Button(sources, text="Ouvrir le guide complet", command=self._open_science_guide, style="Quiet.TButton").pack(anchor="w", pady=(10, 0))
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

    def _path_row(self, frame, label, variable, command, row, tip):
        label_widget = ttk.Label(frame, text=label)
        label_widget.grid(row=row, column=0, sticky="w", pady=8)
        Tooltip(label_widget, tip)
        entry = ttk.Entry(frame, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 6), pady=8)
        Tooltip(entry, tip)
        button = ttk.Button(frame, text="Parcourir", command=command)
        button.grid(row=row, column=2, sticky="e", pady=8)
        Tooltip(button, "Choisir le fichier ou dossier sur ton PC.")

    def _number_field(self, frame, label, variable, column, tip):
        group = ttk.Frame(frame)
        group.grid(row=0, column=column, sticky="ew", padx=(0, 10))
        label_widget = ttk.Label(group, text=label)
        label_widget.pack(anchor="w")
        Tooltip(label_widget, tip)
        entry = ttk.Entry(group, textvariable=variable, width=14)
        entry.pack(anchor="w", pady=(4, 0))
        Tooltip(entry, tip)
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
            text="La carte interactive donne zoom, coordonnées GPS et liens Google Maps",
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

    def _open_interactive_map(self) -> None:
        path = self._output_file("interactive_map.html")
        if path.exists():
            webbrowser.open(path.resolve().as_uri())
        else:
            messagebox.showinfo("Carte absente", "Lance une analyse LiDAR pour générer interactive_map.html.")

    def _open_locations(self) -> None:
        path = self._output_file("candidate_locations.csv")
        if path.exists():
            os.startfile(path)
        else:
            messagebox.showinfo("Liste absente", "Lance une analyse LiDAR pour générer candidate_locations.csv.")

    def _open_science_guide(self) -> None:
        path = self._output_file("science_guide.html")
        if not path.exists():
            try:
                from .science import write_science_guide

                target = Path(self.out_dir.get())
                if target.suffix:
                    target = target.parent
                target.mkdir(parents=True, exist_ok=True)
                write_science_guide(target)
            except Exception as exc:
                messagebox.showerror("Guide absent", f"Impossible de créer le guide : {exc}")
                return
        webbrowser.open(path.resolve().as_uri())

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
