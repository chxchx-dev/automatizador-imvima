from __future__ import annotations

import os
import threading
import tkinter as tk
import webbrowser
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .config import Settings, load_settings, save_settings
from .constants import APP_NAME, APP_VERSION
from .repository import AlertRepository
from .service import SigaviService


class SigaviApp(tk.Tk):
    COLORS = {
        "ink": "#122238",
        "muted": "#64748b",
        "teal": "#087f8c",
        "teal_dark": "#066875",
        "teal_light": "#e6f4f5",
        "bg": "#f3f6fa",
        "white": "#ffffff",
        "line": "#e1e8ef",
        "sidebar": "#102a43",
        "sidebar_hover": "#1c3f5d",
        "green": "#138a61",
        "orange": "#c26a16",
        "red": "#bc4545",
    }

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} · Vigilancia sanitaria")
        self.geometry("1360x860")
        self.minsize(1050, 700)
        self.configure(bg=self.COLORS["bg"])
        self.settings = load_settings()
        Path(self.settings.data_dir).mkdir(parents=True, exist_ok=True)
        self.repository = AlertRepository(self.settings.database_path)
        self._busy = False
        self._current_page = "Resumen"
        self._setup_style()
        self._build_shell()
        self._show_page("Resumen")
        self._refresh_dashboard()

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Treeview", background=self.COLORS["white"], fieldbackground=self.COLORS["white"],
                        foreground=self.COLORS["ink"], rowheight=34, borderwidth=0, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#edf2f7", foreground=self.COLORS["muted"],
                        relief="flat", font=("Segoe UI Semibold", 9))
        style.map("Treeview", background=[("selected", "#d8eef0")], foreground=[("selected", self.COLORS["ink"])])
        style.configure("Horizontal.TProgressbar", troughcolor="#e2eaf1", background=self.COLORS["teal"], thickness=9)
        style.configure("TEntry", padding=(9, 8), fieldbackground=self.COLORS["white"])
        style.configure("TCombobox", padding=(9, 7))

    def _build_shell(self) -> None:
        shell = tk.Frame(self, bg=self.COLORS["bg"])
        shell.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(shell, bg=self.COLORS["sidebar"], width=226)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=self.COLORS["sidebar"])
        brand.pack(fill="x", padx=22, pady=(27, 30))
        mark = tk.Label(brand, text="S", bg="#0e8d96", fg="white", font=("Segoe UI Semibold", 18), width=2, height=1)
        mark.pack(side="left", padx=(0, 11))
        brand_text = tk.Frame(brand, bg=self.COLORS["sidebar"])
        brand_text.pack(side="left")
        tk.Label(brand_text, text="SIGAVI", bg=self.COLORS["sidebar"], fg="white", font=("Segoe UI Semibold", 16)).pack(anchor="w")
        tk.Label(brand_text, text="VIGILANCIA INVIMA", bg=self.COLORS["sidebar"], fg="#a9c3d8", font=("Segoe UI", 8)).pack(anchor="w", pady=(1, 0))

        tk.Label(self.sidebar, text="ESPACIO DE TRABAJO", bg=self.COLORS["sidebar"], fg="#86a4bd",
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=22, pady=(0, 11))
        self.nav_buttons: dict[str, tk.Button] = {}
        for title, icon in (("Resumen", "▦"), ("Alertas", "◉"), ("Configuración", "⚙")):
            button = tk.Button(self.sidebar, text=f"  {icon}    {title}", anchor="w", relief="flat", bd=0,
                               bg=self.COLORS["sidebar"], fg="#d5e2ed", activebackground=self.COLORS["sidebar_hover"],
                               activeforeground="white", font=("Segoe UI", 10), padx=15, pady=12,
                               command=lambda page=title: self._show_page(page))
            button.pack(fill="x", padx=11, pady=2)
            self.nav_buttons[title] = button

        spacer = tk.Frame(self.sidebar, bg=self.COLORS["sidebar"])
        spacer.pack(fill="both", expand=True)
        tk.Frame(self.sidebar, bg="#25445f", height=1).pack(fill="x", padx=19, pady=(0, 15))
        tk.Label(self.sidebar, text="FUENTE OFICIAL", bg=self.COLORS["sidebar"], fg="#86a4bd",
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=22)
        source_button = tk.Button(self.sidebar, text="↗  Portal INVIMA", anchor="w", relief="flat", bd=0,
                                  bg=self.COLORS["sidebar"], fg="#e4edf4", activebackground=self.COLORS["sidebar_hover"],
                                  activeforeground="white", font=("Segoe UI", 9), padx=20, pady=10,
                                  command=lambda: webbrowser.open(self.settings.listing_url))
        source_button.pack(fill="x", padx=11, pady=(2, 20))

        self.content = tk.Frame(shell, bg=self.COLORS["bg"])
        self.content.pack(side="left", fill="both", expand=True)
        self.page_container = tk.Frame(self.content, bg=self.COLORS["bg"])
        self.page_container.pack(fill="both", expand=True, padx=30, pady=27)
        self.status_var = tk.StringVar(value="Listo para actualizar")
        status = tk.Frame(self.content, bg=self.COLORS["white"], height=34, highlightbackground=self.COLORS["line"], highlightthickness=1)
        status.pack(side="bottom", fill="x")
        tk.Label(status, textvariable=self.status_var, bg=self.COLORS["white"], fg=self.COLORS["muted"],
                 font=("Segoe UI", 9), anchor="w").pack(side="left", padx=18, pady=8)
        tk.Label(status, text=f"Versión {APP_VERSION}", bg=self.COLORS["white"], fg=self.COLORS["muted"],
                 font=("Segoe UI", 8)).pack(side="right", padx=18)

    def _show_page(self, page: str) -> None:
        self._current_page = page
        for widget in self.page_container.winfo_children():
            widget.destroy()
        for title, button in self.nav_buttons.items():
            active = title == page
            button.configure(bg=self.COLORS["sidebar_hover"] if active else self.COLORS["sidebar"],
                             fg="white" if active else "#d5e2ed")
        if page == "Resumen":
            self._build_dashboard()
        elif page == "Alertas":
            self._build_alerts_page()
        else:
            self._build_settings_page()
        if page == "Resumen" and hasattr(self, "repository"):
            self.after_idle(self._refresh_dashboard)

    def _header(self, eyebrow: str, title: str, subtitle: str) -> tk.Frame:
        row = tk.Frame(self.page_container, bg=self.COLORS["bg"])
        row.pack(fill="x", pady=(0, 21))
        text = tk.Frame(row, bg=self.COLORS["bg"])
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text=eyebrow.upper(), bg=self.COLORS["bg"], fg=self.COLORS["teal"],
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", pady=(0, 4))
        tk.Label(text, text=title, bg=self.COLORS["bg"], fg=self.COLORS["ink"],
                 font=("Segoe UI Semibold", 22)).pack(anchor="w")
        tk.Label(text, text=subtitle, bg=self.COLORS["bg"], fg=self.COLORS["muted"],
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))
        return row

    def _card(self, parent: tk.Widget, title: str, value: str, hint: str, accent: str | None = None) -> tk.Frame:
        card = tk.Frame(parent, bg=self.COLORS["white"], highlightbackground=self.COLORS["line"], highlightthickness=1)
        stripe = tk.Frame(card, bg=accent or self.COLORS["teal"], width=4)
        stripe.pack(side="left", fill="y")
        body = tk.Frame(card, bg=self.COLORS["white"])
        body.pack(side="left", fill="both", expand=True, padx=15, pady=13)
        tk.Label(body, text=title, bg=self.COLORS["white"], fg=self.COLORS["muted"], font=("Segoe UI", 9)).pack(anchor="w")
        val = tk.Label(body, text=value, bg=self.COLORS["white"], fg=self.COLORS["ink"], font=("Segoe UI Semibold", 19))
        val.pack(anchor="w", pady=(7, 1))
        hint_label = tk.Label(body, text=hint, bg=self.COLORS["white"], fg=self.COLORS["muted"], font=("Segoe UI", 8))
        hint_label.pack(anchor="w")
        card.value_label = val  # type: ignore[attr-defined]
        card.hint_label = hint_label  # type: ignore[attr-defined]
        return card

    def _build_dashboard(self) -> None:
        header = self._header("Panel de control", "Vigilancia sanitaria", "Consulta novedades del INVIMA y actualiza la matriz institucional.")
        self.update_button = tk.Button(header, text="⟳  ACTUALIZAR ALERTAS INVIMA", relief="flat", bd=0,
                                       bg=self.COLORS["teal"], fg="white", activebackground=self.COLORS["teal_dark"],
                                       activeforeground="white", padx=19, pady=13, font=("Segoe UI Semibold", 9),
                                       cursor="hand2", command=self._start_update)
        self.update_button.pack(side="right", anchor="center", padx=(18, 0))

        top = tk.Frame(self.page_container, bg=self.COLORS["bg"])
        top.pack(fill="x", pady=(0, 17))
        self.metric_cards = {}
        metrics = (
            ("Última actualización", "—", "Sin ejecuciones registradas", self.COLORS["teal"]),
            ("Alertas encontradas", "0", "En la consulta más reciente", "#3676b8"),
            ("Nuevas en matriz", "0", "Agregadas sin repetir", self.COLORS["green"]),
            ("Ya registradas", "0", "Omitidas para evitar repetición", "#58768f"),
            ("PDF conservados", "0", "Descargados o reutilizados", "#7758a8"),
            ("Alertas por revisar", "0", "Errores y clasificación pendiente", self.COLORS["orange"]),
        )
        for i, (label, value, hint, color) in enumerate(metrics):
            card = self._card(top, label, value, hint, color)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0 if i == 4 else 8))
            top.grid_columnconfigure(i, weight=1, uniform="metrics")
            self.metric_cards[label] = card

        progress_card = tk.Frame(self.page_container, bg=self.COLORS["white"], highlightbackground=self.COLORS["line"], highlightthickness=1)
        progress_card.pack(fill="x", pady=(0, 17))
        progress_inner = tk.Frame(progress_card, bg=self.COLORS["white"])
        progress_inner.pack(fill="x", padx=18, pady=14)
        progress_top = tk.Frame(progress_inner, bg=self.COLORS["white"])
        progress_top.pack(fill="x")
        self.stage_var = tk.StringVar(value="Listo para actualizar")
        self.progress_detail_var = tk.StringVar(value=f"Desde {self.settings.start_date} · Todas las categorías · Revisión incremental")
        tk.Label(progress_top, textvariable=self.stage_var, bg=self.COLORS["white"], fg=self.COLORS["ink"],
                 font=("Segoe UI Semibold", 10)).pack(side="left")
        self.progress_value = tk.StringVar(value="0 %")
        tk.Label(progress_top, textvariable=self.progress_value, bg=self.COLORS["white"], fg=self.COLORS["teal"],
                 font=("Segoe UI Semibold", 9)).pack(side="right")
        self.progress_bar = ttk.Progressbar(progress_inner, mode="determinate", maximum=100, style="Horizontal.TProgressbar")
        self.progress_bar.pack(fill="x", pady=(10, 8))
        tk.Label(progress_inner, textvariable=self.progress_detail_var, bg=self.COLORS["white"], fg=self.COLORS["muted"],
                 font=("Segoe UI", 8)).pack(anchor="w")

        grid = tk.Frame(self.page_container, bg=self.COLORS["bg"])
        grid.pack(fill="both", expand=True)
        left = tk.Frame(grid, bg=self.COLORS["white"], highlightbackground=self.COLORS["line"], highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = tk.Frame(grid, bg=self.COLORS["white"], width=260, highlightbackground=self.COLORS["line"], highlightthickness=1)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        title_bar = tk.Frame(left, bg=self.COLORS["white"])
        title_bar.pack(fill="x", padx=16, pady=(14, 10))
        tk.Label(title_bar, text="Alertas recientes", bg=self.COLORS["white"], fg=self.COLORS["ink"],
                 font=("Segoe UI Semibold", 11)).pack(side="left")
        tk.Button(title_bar, text="Ver todas  →", relief="flat", bg=self.COLORS["white"], fg=self.COLORS["teal"],
                  font=("Segoe UI Semibold", 8), command=lambda: self._show_page("Alertas")).pack(side="right")
        self.recent_tree_frame = self._make_tree(left, ("fecha", "codigo", "producto", "tipo", "estado"),
                                                 ("Fecha", "Código", "Producto", "Documento", "Estado"),
                                                 (98, 110, 320, 135, 125))
        self.recent_tree_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.recent_tree = self.recent_tree_frame.tree

        tk.Label(right, text="Accesos rápidos", bg=self.COLORS["white"], fg=self.COLORS["ink"],
                 font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=16, pady=(15, 12))
        self._quick_button(right, "Abrir matriz actualizada", "↗", self._open_matrix)
        self._quick_button(right, "Abrir carpeta de evidencia", "▣", self._open_evidence)
        self._quick_button(right, "Configurar plantilla", "⚙", lambda: self._show_page("Configuración"))
        tk.Frame(right, bg=self.COLORS["line"], height=1).pack(fill="x", padx=16, pady=(13, 13))
        tk.Label(right, text="Flujo SIGAVI", bg=self.COLORS["white"], fg=self.COLORS["ink"],
                 font=("Segoe UI Semibold", 10)).pack(anchor="w", padx=16)
        for step in ("01  Captura paginada INVIMA", "02  Descarga y organiza PDF", "03  Extrae y clasifica", "04  Guarda en SQLite", "05  Actualiza la matriz"):
            tk.Label(right, text=step, bg=self.COLORS["white"], fg=self.COLORS["muted"],
                     font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=(7, 0))

    def _quick_button(self, parent: tk.Widget, title: str, icon: str, command) -> None:
        button = tk.Button(parent, text=f"{icon}    {title}", anchor="w", relief="flat", bd=0,
                           bg=self.COLORS["white"], fg=self.COLORS["muted"], activebackground=self.COLORS["teal_light"],
                           activeforeground=self.COLORS["teal"], font=("Segoe UI", 9), padx=16, pady=10, command=command)
        button.pack(fill="x", padx=4)

    def _make_tree(self, parent: tk.Widget, columns: tuple[str, ...], labels: tuple[str, ...], widths: tuple[int, ...]) -> tk.Frame:
        frame = tk.Frame(parent, bg=self.COLORS["white"])
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        for column, label, width in zip(columns, labels, widths):
            tree.heading(column, text=label, anchor="w")
            tree.column(column, width=width, minwidth=70, anchor="w", stretch=column == "producto")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        frame.tree = tree  # type: ignore[attr-defined]
        return frame

    def _build_alerts_page(self) -> None:
        header = self._header("Registro local", "Alertas procesadas", "Alertas observadas, estado documental y trazabilidad en SQLite.")
        tk.Button(header, text="⟳  ACTUALIZAR", relief="flat", bd=0, bg=self.COLORS["teal"], fg="white",
                  activebackground=self.COLORS["teal_dark"], activeforeground="white", padx=17, pady=11,
                  font=("Segoe UI Semibold", 9), command=self._start_update).pack(side="right")
        panel = tk.Frame(self.page_container, bg=self.COLORS["white"], highlightbackground=self.COLORS["line"], highlightthickness=1)
        panel.pack(fill="both", expand=True)
        title = tk.Frame(panel, bg=self.COLORS["white"])
        title.pack(fill="x", padx=16, pady=14)
        tk.Label(title, text="Histórico de alertas", bg=self.COLORS["white"], fg=self.COLORS["ink"],
                 font=("Segoe UI Semibold", 11)).pack(side="left")
        self.alerts_tree_frame = self._make_tree(panel,
            ("fecha", "codigo", "producto", "clasificacion", "tipo", "estado", "portal", "pdf"),
            ("Fecha", "Código", "Producto", "Tipo de producto", "Documento", "Estado", "Portal", "PDF"),
            (90, 95, 220, 205, 120, 115, 145, 55))
        self.alerts_tree_frame.pack(fill="both", expand=True, padx=13, pady=(0, 13))
        tree = self.alerts_tree_frame.tree
        tree.bind("<Double-1>", self._open_selected_pdf)
        self.alerts_tree = tree
        self._refresh_alerts()

    def _build_settings_page(self) -> None:
        self._header("Preferencias", "Configuración SIGAVI", "Rutas y fecha de inicio configurables para este equipo.")
        panel = tk.Frame(self.page_container, bg=self.COLORS["white"], highlightbackground=self.COLORS["line"], highlightthickness=1)
        panel.pack(fill="x", anchor="n")
        inner = tk.Frame(panel, bg=self.COLORS["white"])
        inner.pack(fill="x", padx=23, pady=22)
        self.template_var = tk.StringVar(value=self.settings.template_path)
        self.data_dir_var = tk.StringVar(value=self.settings.data_dir)
        self.start_date_var = tk.StringVar(value=self.settings.start_date)

        tk.Label(inner, text="Plantilla institucional XLSX", bg=self.COLORS["white"], fg=self.COLORS["ink"],
                 font=("Segoe UI Semibold", 10)).pack(anchor="w")
        template_row = tk.Frame(inner, bg=self.COLORS["white"])
        template_row.pack(fill="x", pady=(7, 18))
        ttk.Entry(template_row, textvariable=self.template_var).pack(side="left", fill="x", expand=True)
        tk.Button(template_row, text="Buscar…", relief="flat", bg="#eaf1f6", fg=self.COLORS["ink"],
                  padx=15, pady=9, command=self._choose_template).pack(side="left", padx=(9, 0))

        tk.Label(inner, text="Carpeta local de datos", bg=self.COLORS["white"], fg=self.COLORS["ink"],
                 font=("Segoe UI Semibold", 10)).pack(anchor="w")
        data_row = tk.Frame(inner, bg=self.COLORS["white"])
        data_row.pack(fill="x", pady=(7, 18))
        ttk.Entry(data_row, textvariable=self.data_dir_var).pack(side="left", fill="x", expand=True)
        tk.Button(data_row, text="Buscar…", relief="flat", bg="#eaf1f6", fg=self.COLORS["ink"],
                  padx=15, pady=9, command=self._choose_data_dir).pack(side="left", padx=(9, 0))

        tk.Label(inner, text="Incluir alertas publicadas desde (inclusive)", bg=self.COLORS["white"], fg=self.COLORS["ink"],
                 font=("Segoe UI Semibold", 10)).pack(anchor="w")
        ttk.Entry(inner, textvariable=self.start_date_var, width=22).pack(anchor="w", pady=(7, 5))
        tk.Label(inner, text="Formato AAAA-MM-DD. Valor inicial del piloto: 2026-08-20.",
                 bg=self.COLORS["white"], fg=self.COLORS["muted"], font=("Segoe UI", 8)).pack(anchor="w")

        tk.Frame(inner, bg=self.COLORS["line"], height=1).pack(fill="x", pady=(21, 17))
        tk.Label(inner, text="La matriz se guarda como una copia de trabajo. El archivo plantilla no se sobrescribe.",
                 bg=self.COLORS["white"], fg=self.COLORS["muted"], font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(inner, text="La base de datos, los PDFs y el registro de actividad quedan dentro de la carpeta local seleccionada.",
                 bg=self.COLORS["white"], fg=self.COLORS["muted"], font=("Segoe UI", 9)).pack(anchor="w", pady=(5, 0))
        self.settings_message = tk.StringVar(value="")
        save_row = tk.Frame(inner, bg=self.COLORS["white"])
        save_row.pack(fill="x", pady=(20, 0))
        tk.Label(save_row, textvariable=self.settings_message, bg=self.COLORS["white"], fg=self.COLORS["green"],
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Button(save_row, text="Guardar configuración", relief="flat", bg=self.COLORS["teal"], fg="white",
                  activebackground=self.COLORS["teal_dark"], activeforeground="white", padx=18, pady=11,
                  font=("Segoe UI Semibold", 9), command=self._save_settings).pack(side="right")

    def _choose_template(self) -> None:
        selected = filedialog.askopenfilename(title="Seleccionar plantilla institucional", filetypes=[("Excel XLSX", "*.xlsx"), ("Todos los archivos", "*.*")])
        if selected:
            self.template_var.set(selected)

    def _choose_data_dir(self) -> None:
        selected = filedialog.askdirectory(title="Seleccionar carpeta local de datos", mustexist=False)
        if selected:
            self.data_dir_var.set(selected)

    def _save_settings(self) -> None:
        template = Path(self.template_var.get().strip())
        data_text = self.data_dir_var.get().strip()
        data_dir = Path(data_text).expanduser()
        try:
            datetime.strptime(self.start_date_var.get().strip(), "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Fecha no válida", "Usa el formato AAAA-MM-DD, por ejemplo 2026-08-20.")
            return
        if not template.is_file():
            messagebox.showerror("Plantilla no encontrada", "Selecciona un archivo XLSX existente.")
            return
        if not data_text:
            messagebox.showerror("Carpeta requerida", "Selecciona la carpeta local de datos.")
            return
        self.settings.template_path = str(template.resolve())
        self.settings.data_dir = str(data_dir.resolve())
        self.settings.start_date = self.start_date_var.get().strip()
        data_dir.mkdir(parents=True, exist_ok=True)
        save_settings(self.settings)
        self.repository = AlertRepository(self.settings.database_path)
        self.settings_message.set("Configuración guardada.")
        self.status_var.set("Configuración actualizada")
        self.after(3500, lambda: self.settings_message.set(""))

    def _start_update(self) -> None:
        if self._busy:
            return
        if self._current_page != "Resumen":
            self._show_page("Resumen")
        if not Path(self.settings.template_path).is_file():
            messagebox.showerror("Falta la plantilla", "Abre Configuración y selecciona la plantilla institucional XLSX.")
            self._show_page("Configuración")
            return
        try:
            datetime.strptime(self.settings.start_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Fecha no válida", "Corrige la fecha inicial en Configuración.")
            return
        self._busy = True
        if hasattr(self, "update_button") and self.update_button.winfo_exists():
            self.update_button.configure(state="disabled", text="  ACTUALIZANDO…  ")
        if hasattr(self, "progress_bar") and self.progress_bar.winfo_exists():
            self.progress_bar.configure(value=0)
        self.progress_value.set("0 %")
        self.stage_var.set("Iniciando consulta")
        self.status_var.set("Consultando el portal oficial del INVIMA…")

        def worker() -> None:
            try:
                settings_snapshot = replace(self.settings)
                repository_snapshot = self.repository
                service = SigaviService(settings_snapshot, repository=repository_snapshot)
                result = service.update(progress=lambda stage, current, total, message: self.after(0, self._on_progress, stage, current, total, message))
                self.after(0, self._on_update_done, result, None)
            except Exception as exc:
                self.after(0, self._on_update_done, None, exc)

        threading.Thread(target=worker, name="sigavi-update", daemon=True).start()

    def _on_progress(self, stage: str, current: int, total: int, message: str) -> None:
        if not self.winfo_exists():
            return
        percentage = int(current / max(total, 1) * 100)
        if hasattr(self, "progress_bar") and self.progress_bar.winfo_exists():
            self.progress_bar.configure(value=percentage)
            self.progress_value.set(f"{percentage} %")
            self.stage_var.set(stage)
            self.progress_detail_var.set(message)
        self.status_var.set(message)

    def _on_update_done(self, result: dict | None, error: Exception | None) -> None:
        self._busy = False
        if hasattr(self, "update_button") and self.update_button.winfo_exists():
            self.update_button.configure(state="normal", text="⟳  ACTUALIZAR ALERTAS INVIMA")
        self._refresh_dashboard()
        if error:
            self.status_var.set(f"Actualización interrumpida: {error}")
            messagebox.showerror("No se completó la actualización", str(error))
            return
        if result:
            self.status_var.set(str(result["summary"]))
            if result.get("errors"):
                messagebox.showwarning("Actualización terminada con pendientes", str(result["summary"]))
            else:
                messagebox.showinfo("Actualización terminada", str(result["summary"]))

    def _refresh_dashboard(self) -> None:
        stats = self.repository.dashboard()
        run = self.repository.latest_run()
        if self._current_page != "Resumen" or not hasattr(self, "metric_cards"):
            return
        if run:
            finished = run.get("finished_at") or run.get("started_at", "")
            display = finished.replace("T", " ")[:16] or "—"
            self.metric_cards["Última actualización"].value_label.configure(text=display)
            self.metric_cards["Última actualización"].hint_label.configure(text=run.get("status", ""))
            self.metric_cards["Alertas encontradas"].value_label.configure(text=str(run.get("alerts_found", 0)))
            self.metric_cards["Alertas encontradas"].hint_label.configure(text=f"{run.get('pages_scanned', 0)} páginas recorridas")
            self.metric_cards["Nuevas en matriz"].value_label.configure(text=str(run.get("matrix_added", 0)))
            self.metric_cards["Nuevas en matriz"].hint_label.configure(text=f"{run.get('alerts_new', 0)} alertas nuevas guardadas")
            self.metric_cards["Ya registradas"].value_label.configure(text=str(run.get("alerts_existing", 0)))
            self.metric_cards["Ya registradas"].hint_label.configure(text="Omitidas en esta actualización")
            self.metric_cards["PDF conservados"].value_label.configure(text=str(run.get("pdf_downloaded", 0) + run.get("pdf_reused", 0)))
            self.metric_cards["PDF conservados"].hint_label.configure(text="Descargados o reutilizados")
            self.metric_cards["Alertas por revisar"].value_label.configure(text=str(stats["pending_review"]))
            self.metric_cards["Alertas por revisar"].hint_label.configure(text=f"{run.get('errors', 0)} errores en la ejecución")
        else:
            self.metric_cards["PDF conservados"].value_label.configure(text=str(stats["pdf_ready"]))
            self.metric_cards["Alertas por revisar"].value_label.configure(text=str(stats["pending_review"]))
            self.metric_cards["Alertas por revisar"].hint_label.configure(text=f"{stats['errors']} errores registrados")
        if hasattr(self, "recent_tree") and self.recent_tree.winfo_exists():
            self._fill_tree(self.recent_tree, self.repository.get_alerts(12), recent=True)

    def _refresh_alerts(self) -> None:
        if hasattr(self, "alerts_tree"):
            self._fill_tree(self.alerts_tree, self.repository.get_alerts(1000), recent=False)

    def _fill_tree(self, tree: ttk.Treeview, records: list[dict], recent: bool) -> None:
        tree.delete(*tree.get_children())
        for item in records:
            values = (
                (item.get("alert_date") or "")[:10], item.get("code") or "—", item.get("product_name") or "Sin nombre",
                item.get("document_type") or "—", item.get("status") or "—",
            ) if recent else (
                (item.get("alert_date") or "")[:10], item.get("code") or "—", item.get("product_name") or "Sin nombre",
                item.get("classification") or "Pendiente", item.get("document_type") or "—",
                item.get("status") or "—",
                "No visible en última consulta" if item.get("portal_presence") == "not_seen" else ("Visible" if item.get("portal_presence") == "visible" else "Sin dato"),
                "Abrir" if item.get("pdf_path") else "Pendiente",
            )
            iid = str(item.get("id"))
            review = item.get("duplicate_status") == "review" or item.get("classification_confidence") == "pending" or item.get("portal_presence") == "not_seen"
            tag = "error" if "error" in str(item.get("status")) else ("review" if review else "normal")
            tree.insert("", "end", iid=iid, values=values, tags=(tag,))
        tree.tag_configure("error", foreground=self.COLORS["red"])
        tree.tag_configure("review", foreground=self.COLORS["orange"])

    def _open_matrix(self) -> None:
        path = self.settings.matrix_output_path
        if not path.exists():
            path = Path(self.settings.template_path)
        self._open_path(path)

    def _open_evidence(self) -> None:
        path = self.settings.evidence_dir
        path.mkdir(parents=True, exist_ok=True)
        self._open_path(path)

    def _open_path(self, path: Path) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                webbrowser.open(path.resolve().as_uri())
        except Exception as exc:
            messagebox.showerror("No se pudo abrir", f"{path}\n\n{exc}")

    def _open_selected_pdf(self, _event=None) -> None:
        selection = self.alerts_tree.selection()
        if not selection:
            return
        record = self.repository.get_alert(int(selection[0]))
        if record and record.get("pdf_path") and Path(record["pdf_path"]).exists():
            self._open_path(Path(record["pdf_path"]))
        elif record and record.get("pdf_url"):
            webbrowser.open(record["pdf_url"])


def run_app() -> None:
    SigaviApp().mainloop()
