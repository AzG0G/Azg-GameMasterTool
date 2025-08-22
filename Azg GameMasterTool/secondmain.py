import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import font, colorchooser # NEW
from tkinter import messagebox, filedialog, simpledialog
import os
import colorsys
import json
import uuid
import copy
import shutil
import re
from datetime import datetime
try:
    import requests
except ImportError:
    requests = None
from io import BytesIO

# --- Constantes et Variables Globales ---
QUEST_DATA_DIR = os.path.join("data", "quests")
all_quests = [] # Liste pour stocker les quêtes chargées
current_quest_id = None # Pour savoir quelle quête est en cours d'édition

QUEST_IMAGE_DIR = os.path.join("data", "quest_images")

# Déclarer le dictionnaire, mais le laisser vide pour l'instant.
# Il sera peuplé dans setup_quest_page une fois la fenêtre root créée.
quest_details_vars = {} # Sera initialisé dans setup_quest_page

def lighten_color(hex_color, amount=0.1):
    """
    Éclaircit une couleur hexadécimale d'un certain montant.
    """
    try:
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        # Convertir RGB en HLS, modifier la luminosité, et reconvertir en RGB
        h, l, s = colorsys.rgb_to_hls(rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0)
        l += (1 - l) * amount
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'
    except Exception:
        return hex_color # Retourner la couleur originale en cas d'erreur
# --- Fonctions de gestion des données ---

def save_quest_data(quest_data):
    """Sauvegarde les données d'une quête dans son propre fichier JSON."""
    quest_id = quest_data.get('id')
    if not quest_id:
        print("Erreur : Impossible de sauvegarder une quête sans ID.")
        return

    quest_file_path = os.path.join(QUEST_DATA_DIR, f"{quest_id}.json")
    os.makedirs(os.path.dirname(quest_file_path), exist_ok=True)
    try:
        with open(quest_file_path, "w", encoding="utf-8") as f:
            json.dump(quest_data, f, indent=2, sort_keys=True)
            # print(f"Quest saved: {quest_file_path}") # Debugging
    except IOError as e:
        messagebox.showerror("Erreur de sauvegarde", f"Impossible de sauvegarder la quête {quest_id}: {e}")

def load_quests():
    """Charge toutes les quêtes depuis le dossier data/quests/."""
    global all_quests
    os.makedirs(QUEST_DATA_DIR, exist_ok=True)
    all_quests = []

    for filename in os.listdir(QUEST_DATA_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(QUEST_DATA_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    quest_data = json.load(f)
                    all_quests.append(quest_data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Erreur lors du chargement du fichier quête {filename}: {e}")
    
    # Trier par date de création par défaut
    all_quests.sort(key=lambda q: q.get('creation_timestamp', ''), reverse=True)


# --- Fonctions de l'interface ---

def setup_quest_page(root_window, pages_dict, base_font_family_val, retour_menu_principal_func, register_scalable_widget_func, style_obj, Image=None, ImageTk=None, webbrowser=None):
    """
    Configure la page de gestion des quêtes avec toutes ses fonctionnalités.
    """
    global frame_quetes, base_font_family, quest_details_vars

    # Initialiser le dictionnaire de variables une seule fois, après la création de la fenêtre root.
    if not quest_details_vars:
        quest_details_vars.update({
            "id": tk.StringVar(),
            "name": tk.StringVar(),
            "status": tk.StringVar(),
            "type": tk.StringVar(),
            "description": tk.StringVar(),
            "quest_flow_data": {} # Remplacera quest_flow_content et quest_flow_tags
        })
    base_font_family = base_font_family_val # Store it globally for this module
    frame_quetes = ttk.Frame(root_window)
    pages_dict["quetes"] = frame_quetes

    # --- Widgets globaux de la page ---
    quest_tree = None
    editor_widgets = {}

    # Store Image/ImageTk/webbrowser for use in this module
    _Image = Image
    _ImageTk = ImageTk
    _webbrowser = webbrowser
    # --- Fonctions de mise à jour de l'UI ---

    def update_quest_list():
        """Vide et repeuple le Treeview avec les quêtes actuelles."""
        for item in quest_tree.get_children():
            quest_tree.delete(item)
        
        for quest in all_quests:
            status = quest.get('status', 'N/A')
            tag = status.lower().replace(' ', '_')
            quest_tree.insert("", "end", iid=quest['id'], values=(quest.get('name', 'Sans nom'), status, quest.get('type', 'N/A')), tags=(tag,))
        
        clear_editor()

    def clear_editor():
        """Vide les champs de l'éditeur de quête."""
        global current_quest_id
        current_quest_id = None
        editor_widgets['name_var'].set("")
        editor_widgets['status_var'].set("Disponible") # Default value
        editor_widgets['type_var'].set("Secondaire") # Default value
        for name in ['description', 'objectives', 'rewards']:
            widget = editor_widgets[name]
            widget.config(state="normal")
            widget.delete("1.0", "end")
            widget.config(state="disabled")        
        quest_details_vars["quest_flow_data"] = {}
        editor_widgets['save_button'].config(state="disabled")

    def populate_editor(quest_data):
        """Remplit les champs de l'éditeur avec les données d'une quête."""
        global current_quest_id
        current_quest_id = quest_data['id']
        
        editor_widgets['name_var'].set(quest_data.get('name', 'Nouvelle Quête'))
        editor_widgets['status_var'].set(quest_data.get('status', 'Disponible'))
        editor_widgets['type_var'].set(quest_data.get('type', 'Secondaire'))

        # Activer tous les widgets pour l'édition
        for widget in editor_widgets.values():
            if isinstance(widget, (tk.Text, ttk.Entry, ttk.Combobox)):
                widget.config(state="normal")

        for name in ['description', 'objectives', 'rewards']:
            widget = editor_widgets[name]
            widget.delete("1.0", "end")
            widget.insert("1.0", quest_data.get(name, ''))
        
        # Charger le contenu et les tags du déroulement de la quête
        quest_details_vars["quest_flow_data"] = quest_data.get("quest_flow_data", {})
        editor_widgets['save_button'].config(state="normal")

    def on_quest_select(event):
        """Gère la sélection d'une quête dans le Treeview."""
        selected_item = quest_tree.focus()
        if selected_item:
            quest_data = next((q for q in all_quests if q['id'] == selected_item), None)
            if quest_data:
                populate_editor(quest_data)

    # --- Fonctions CRUD (Create, Read, Update, Delete) ---

    def create_new_quest():
        new_name = simpledialog.askstring("Nouvelle Quête", "Entrez le nom de la nouvelle quête :", parent=frame_quetes)
        if not new_name or not new_name.strip(): return

        new_quest = {'id': f"quest_{uuid.uuid4().hex[:8]}", 'name': new_name.strip(), 'status': 'Disponible', 'type': 'Secondaire', 'description': '', 'objectives': '', 'rewards': '', 'quest_flow_data': {}, 'creation_timestamp': datetime.now().isoformat(timespec="seconds")}
        all_quests.append(new_quest) # Add to end, then sort
        save_quest_data(new_quest)
        update_quest_list()
        quest_tree.selection_set(new_quest['id'])
        quest_tree.focus(new_quest['id'])

    def save_current_quest():
        if not current_quest_id: return
        quest_to_save = next((q for q in all_quests if q['id'] == current_quest_id), None)
        if not quest_to_save: return

        quest_to_save.update({
            'name': editor_widgets['name_var'].get(),
            'status': editor_widgets['status_var'].get(),
            'type': editor_widgets['type_var'].get(),
            'description': editor_widgets['description'].get("1.0", "end-1c"),
            'objectives': editor_widgets['objectives'].get("1.0", "end-1c"),
            'rewards': editor_widgets['rewards'].get("1.0", "end-1c"),
            'quest_flow_data': quest_details_vars["quest_flow_data"]
        })
        save_quest_data(quest_to_save)
        quest_tree.item(current_quest_id, values=(quest_to_save['name'], quest_to_save['status'], quest_to_save['type']))
        
        save_btn = editor_widgets['save_button']
        save_btn.config(text="Sauvegardé !", bootstyle=SUCCESS)
        save_btn.after(2000, lambda: save_btn.config(text="💾 Sauvegarder les modifications", bootstyle=PRIMARY))

    def delete_selected_quest():
        selected_item = quest_tree.focus()
        if not selected_item: return
        quest_to_delete = next((q for q in all_quests if q['id'] == selected_item), None)
        if not quest_to_delete: return

        if messagebox.askyesno("Confirmation", f"Voulez-vous vraiment supprimer la quête '{quest_to_delete['name']}' ?"):
            os.remove(os.path.join(QUEST_DATA_DIR, f"{selected_item}.json"))
            all_quests.remove(quest_to_delete)
            update_quest_list()

    # --- Construction de l'interface ---
    ttk.Button(frame_quetes, text="⬅ Menu principal", bootstyle=SECONDARY, command=retour_menu_principal_func).pack(side="top", anchor="nw", padx=10, pady=10)
    title_quetes = ttk.Label(frame_quetes, text="📜 Gestion des Quêtes", font=(base_font_family_val, 18, "bold"), bootstyle=PRIMARY)
    title_quetes.pack(pady=10)
    register_scalable_widget_func(title_quetes, 18)

    paned_window = ttk.PanedWindow(frame_quetes, orient=HORIZONTAL)
    paned_window.pack(fill=BOTH, expand=True, padx=10, pady=10)

    left_pane = ttk.Frame(paned_window, padding=10); paned_window.add(left_pane, weight=1) # Poids réduit pour la liste
    left_pane.rowconfigure(0, weight=1); left_pane.columnconfigure(0, weight=1)

    columns = ("name", "status", "type")
    quest_tree = ttk.Treeview(left_pane, columns=columns, show="headings")
    quest_tree.heading("name", text="Nom"); quest_tree.heading("status", text="Statut"); quest_tree.heading("type", text="Type")
    quest_tree.column("name", width=250); quest_tree.column("status", width=100, anchor="center"); quest_tree.column("type", width=100, anchor="center")
    quest_tree.grid(row=0, column=0, sticky="nsew"); quest_tree.bind("<<TreeviewSelect>>", on_quest_select)
    
    tree_scrollbar = ttk.Scrollbar(left_pane, orient="vertical", command=quest_tree.yview); quest_tree.configure(yscrollcommand=tree_scrollbar.set)
    tree_scrollbar.grid(row=0, column=1, sticky="ns")
    quest_tree.config(height=10) # Hauteur initiale pour le Treeview

    quest_tree.tag_configure('disponible', foreground=style_obj.colors.info); quest_tree.tag_configure('en_cours', foreground=style_obj.colors.warning)
    quest_tree.tag_configure('terminée', foreground=style_obj.colors.success); quest_tree.tag_configure('échouée', foreground=style_obj.colors.danger)

    list_actions_frame = ttk.Frame(left_pane); list_actions_frame.grid(row=1, column=0, columnspan=2, pady=(10, 0), sticky="ew")
    ttk.Button(list_actions_frame, text="➕ Créer", bootstyle=SUCCESS, command=create_new_quest).pack(side="left", expand=True, fill="x", padx=(0, 5))
    ttk.Button(list_actions_frame, text="🗑️ Supprimer", bootstyle=DANGER, command=delete_selected_quest).pack(side="left", expand=True, fill="x", padx=(5, 0))

    right_pane = ttk.Labelframe(paned_window, text="Détails de la quête", padding=15); paned_window.add(right_pane, weight=3) # Poids augmenté pour l'éditeur
    right_pane.columnconfigure(1, weight=1)

    name_var = tk.StringVar(); ttk.Label(right_pane, text="Nom :").grid(row=0, column=0, sticky="w", pady=2); ttk.Entry(right_pane, textvariable=name_var).grid(row=0, column=1, columnspan=3, sticky="ew", pady=2)
    status_var = tk.StringVar(); ttk.Label(right_pane, text="Statut :").grid(row=1, column=0, sticky="w", pady=2); ttk.Combobox(right_pane, textvariable=status_var, values=["Disponible", "En cours", "Terminée", "Échouée"], state="readonly").grid(row=1, column=1, sticky="ew", pady=2)
    type_var = tk.StringVar(); ttk.Label(right_pane, text="Type :").grid(row=1, column=2, sticky="w", padx=(10,0), pady=2); ttk.Combobox(right_pane, textvariable=type_var, values=["Principale", "Secondaire", "Contrat", "Personnelle"], state="readonly").grid(row=1, column=3, sticky="ew", pady=2)
    
    # --- Zones de texte avec Scrollbars ---
    
    # Objectifs (maintenant à la ligne 2)
    ttk.Label(right_pane, text="Objectifs :").grid(row=2, column=0, sticky="nw", pady=2)
    objectives_frame = ttk.Frame(right_pane)
    objectives_frame.grid(row=2, column=1, columnspan=3, sticky="nsew", pady=2)
    right_pane.rowconfigure(2, weight=2)
    
    obj_text = tk.Text(objectives_frame, height=8, wrap="word", font=(base_font_family_val, 10))
    obj_text.pack(side="left", fill="both", expand=True)
    obj_scrollbar = ttk.Scrollbar(objectives_frame, orient="vertical", command=obj_text.yview)
    obj_scrollbar.pack(side="right", fill="y")
    obj_text.config(yscrollcommand=obj_scrollbar.set)
    
    # Description (maintenant à la ligne 3)
    ttk.Label(right_pane, text="Description :").grid(row=3, column=0, sticky="nw", pady=2)
    description_frame = ttk.Frame(right_pane)
    description_frame.grid(row=3, column=1, columnspan=3, sticky="nsew", pady=2)
    right_pane.rowconfigure(3, weight=2)
    
    desc_text = tk.Text(description_frame, height=10, wrap="word", font=(base_font_family_val, 10))
    desc_text.pack(side="left", fill="both", expand=True)
    desc_scrollbar = ttk.Scrollbar(description_frame, orient="vertical", command=desc_text.yview)
    desc_scrollbar.pack(side="right", fill="y")
    desc_text.config(yscrollcommand=desc_scrollbar.set)

    # Récompenses (à la ligne 4, avec une hauteur réduite)
    ttk.Label(right_pane, text="Récompenses :").grid(row=4, column=0, sticky="nw", pady=2)
    rewards_frame = ttk.Frame(right_pane)
    rewards_frame.grid(row=4, column=1, columnspan=3, sticky="nsew", pady=2)
    right_pane.rowconfigure(4, weight=1) # Poids réduit pour les récompenses
    
    rew_text = tk.Text(rewards_frame, height=5, wrap="word", font=(base_font_family_val, 10)) # Hauteur réduite
    rew_text.pack(side="left", fill="both", expand=True)
    rew_scrollbar = ttk.Scrollbar(rewards_frame, orient="vertical", command=rew_text.yview)
    rew_scrollbar.pack(side="right", fill="y")
    rew_text.config(yscrollcommand=rew_scrollbar.set)

    # NEW: Bouton "Déroulement de la quête"
    ttk.Button(right_pane, text="Déroulement de la quête", bootstyle=INFO, command=lambda: open_quest_flow_editor(quest_details_vars)).grid(row=5, column=1, columnspan=3, sticky="ew", pady=5)
    right_pane.rowconfigure(5, weight=0) # Le bouton n'a pas besoin de s'étendre

    save_button = ttk.Button(right_pane, text="💾 Sauvegarder les modifications", bootstyle=PRIMARY, command=save_current_quest); save_button.grid(row=6, column=0, columnspan=4, pady=(10, 0), sticky="e")

    editor_widgets.update({
        'name_var': name_var, 'status_var': status_var, 'type_var': type_var,
        'description': desc_text, 'objectives': obj_text, 'rewards': rew_text,
        'save_button': save_button
    })

    class Table(ttk.Frame):
        def __init__(self, parent_text_widget, rows, cols, data=None, col_widths=None, style_obj=None, **kwargs):
            # On extrait notre argument personnalisé avant d'appeler le constructeur parent
            self.undo_manager = kwargs.pop('undo_manager', None)
            super().__init__(parent_text_widget, **kwargs)
            self.parent_text_widget = parent_text_widget
            self.cell_widgets = {}
            self.data = data
            self.style_obj = style_obj

            # Logique de sélection
            self._selection_anchor = None
            self.selected_cells = set()
            
            # Logique de redimensionnement
            self._resize_col_index = None
            self._resize_start_x = 0
            self.bind("<Motion>", self._update_cursor)
            self.bind("<ButtonPress-1>", self._on_press)
            self.bind("<B1-Motion>", self._on_drag)
            self.bind("<ButtonRelease-1>", self._on_release)

            if not self.data:
                self.data = [[{'text': '', 'rowspan': 1, 'colspan': 1, 'visible': True} for _ in range(cols)] for _ in range(rows)]
            
            self._create_table(col_widths)

        def _create_table(self, col_widths=None):
            """Crée ou recrée l'interface du tableau à partir du modèle self.data."""
            for widget in self.cell_widgets.values():
                widget.destroy()
            self.cell_widgets.clear()

            cell_font = font.Font(font=(base_font_family, 9))
            # Hauteur de 2 lignes de texte + un peu de marge pour les bordures/padding
            row_height_px = cell_font.metrics('linespace') * 2 + 6 

            rows = len(self.data)
            if rows == 0: return
            cols = len(self.data[0])

            for c in range(cols):
                width_char = col_widths[c] if col_widths and c < len(col_widths) else 15
                self.grid_columnconfigure(c, weight=0, minsize=width_char * 8)

            for r in range(rows):
                self.grid_rowconfigure(r, weight=1, minsize=row_height_px)
                for c in range(cols):
                    cell_data = self.data[r][c]
                    if cell_data.get('visible', True):
                        cell = tk.Text(self, width=15, height=2, wrap="word", font=(base_font_family, 9), 
                                     relief="solid", borderwidth=1, undo=True,
                                     # Style pour le focus (outline coloré)
                                     highlightthickness=2, 
                                     highlightbackground=self.style_obj.colors.bg, 
                                     highlightcolor=self.style_obj.colors.primary)
                        cell.insert("1.0", cell_data.get('text', ''))
                        
                        rowspan_val = cell_data.get('rowspan', 1)
                        colspan_val = cell_data.get('colspan', 1)
                        cell.grid(row=r, column=c, rowspan=rowspan_val, columnspan=colspan_val, sticky="nsew")
                        
                        # Lier les événements de la cellule aux gestionnaires du conteneur parent (Table)
                        # pour centraliser la logique de sélection, redimensionnement et menu contextuel.
                        cell.bind("<Button-3>", lambda e, r_bind=r, c_bind=c: self._show_cell_context_menu(e, r_bind, c_bind))
                        cell.bind("<ButtonPress-1>", self._on_cell_press)
                        cell.bind("<B1-Motion>", self._on_cell_drag)
                        self.cell_widgets[(r, c)] = cell
            self._update_selection_visuals()

        def get_data(self):
            """Sauvegarde le texte des widgets dans le modèle de données avant de le retourner."""
            for (r, c), widget in self.cell_widgets.items():
                if widget.winfo_exists():
                    self.data[r][c]['text'] = widget.get("1.0", "end-1c")
            return self.data

        def get_col_widths(self):
            widths = []
            if not self.data: return []
            for c in range(len(self.data[0])):
                # Trouve le premier widget visible dans la colonne pour obtenir sa largeur
                for r in range(len(self.data)):
                    if (r, c) in self.cell_widgets:
                        widths.append(self.cell_widgets[(r, c)].cget('width'))
                        break
                else:
                    widths.append(15) # Largeur par défaut
            return widths

        def _start_selection(self, event, row, col):
            self._selection_anchor = (row, col)
            self.selected_cells = {(row, col)}
            self._update_selection_visuals()

        def _update_selection_visuals(self):
            # Définition des couleurs pour les différents états
            default_bg = self.style_obj.colors.bg if self.style_obj else 'white'
            default_fg = self.style_obj.colors.fg if self.style_obj else 'black'
            sel_bg = self.style_obj.colors.primary if self.style_obj else 'blue'
            sel_fg = 'white' # Couleur de texte à fort contraste pour la sélection
            selection_bg = lighten_color(default_bg, 0.2)
            for (r, c), widget in self.cell_widgets.items():
                if not widget.winfo_exists(): continue
                master_cell_coords = self._find_master_cell(r, c)
                base_bg = self.data[r][c].get('bg') or default_bg

                if master_cell_coords and master_cell_coords in self.selected_cells:
                    widget.config(bg=selection_bg, fg=default_fg)
                else:
                    widget.config(bg=base_bg, fg=default_fg)

        def _show_cell_context_menu(self, event, row, col):
            is_in_selection = False
            master_cell_coords = self._find_master_cell(row, col)
            if master_cell_coords:
                if master_cell_coords in self.selected_cells and len(self.selected_cells) > 1:
                    is_in_selection = True
            
            if not is_in_selection:
                self.selected_cells = {master_cell_coords} if master_cell_coords else set()
                self._update_selection_visuals()

            menu = tk.Menu(self, tearoff=0)
            menu.add_command(label="Changer la couleur de fond", command=self.change_cell_color)

            if len(self.selected_cells) > 1:
                menu.add_command(label="Fusionner la sélection", command=self.merge_selection)
            
            master_cell_coords = self._find_master_cell(row, col)
            if master_cell_coords:
                master_r, master_c = master_cell_coords
                master_cell_data = self.data[master_r][master_c]
                if master_cell_data.get('rowspan', 1) > 1 or master_cell_data.get('colspan', 1) > 1:
                    menu.add_command(label="Diviser la cellule", command=lambda: self.split_cell(master_r, master_c))

            if menu.index('end') is not None: menu.add_separator()

            menu.add_command(label="Insérer une ligne au-dessus", command=lambda: self.add_row(row, above=True))
            menu.add_command(label="Insérer une ligne en-dessous", command=lambda: self.add_row(row, above=False))
            menu.add_command(label="Supprimer cette ligne", command=lambda: self.delete_row(row))
            menu.add_separator()
            menu.add_command(label="Insérer une colonne à gauche", command=lambda: self.add_col(col, left=True))
            menu.add_command(label="Insérer une colonne à droite", command=lambda: self.add_col(col, left=False))
            menu.add_command(label="Supprimer cette colonne", command=lambda: self.delete_col(col))
            menu.add_separator()
            menu.add_command(label="Supprimer le tableau", command=self._delete_self)
            menu.tk_popup(event.x_root, event.y_root)

        def change_cell_color(self):
            if not self.selected_cells: return
            # Cette méthode sera enveloppée par le gestionnaire d'undo/redo de l'éditeur principal
            # pour prendre un snapshot avant et après.
            new_color = colorchooser.askcolor(parent=self)[1]
            if new_color:
                for r_sel, c_sel in self.selected_cells:
                    master_coords = self._find_master_cell(r_sel, c_sel)
                    if master_coords: self.data[master_coords[0]][master_coords[1]]['bg'] = new_color
                self._update_selection_visuals()

        def _find_master_cell(self, row, col):
            for r in range(row, -1, -1):
                for c in range(col, -1, -1):
                    cell_data = self.data[r][c]
                    if cell_data.get('visible', True):
                        if r + cell_data.get('rowspan', 1) > row and c + cell_data.get('colspan', 1) > col:
                            return (r, c)
            return None

        def merge_selection(self):
            if len(self.selected_cells) < 2: return
            min_r, max_r = min(r for r,c in self.selected_cells), max(r for r,c in self.selected_cells)
            min_c, max_c = min(c for r,c in self.selected_cells), max(c for r,c in self.selected_cells)

            for r in range(min_r, max_r + 1):
                for c in range(min_c, max_c + 1):
                    if (r, c) not in self.selected_cells:
                        messagebox.showwarning("Fusion impossible", "La sélection doit être un rectangle plein.", parent=self); return
                    master_coords = self._find_master_cell(r, c)
                    if master_coords != (r, c):
                         messagebox.showwarning("Fusion impossible", "La sélection ne peut pas chevaucher des cellules déjà fusionnées.", parent=self); return

            self.get_data() # Sauvegarder le texte actuel
            new_rowspan, new_colspan = max_r - min_r + 1, max_c - min_c + 1
            master_text = "\n".join(self.data[r][c]['text'].strip() for r in range(min_r, max_r + 1) for c in range(min_c, max_c + 1) if self.data[r][c]['text'].strip())

            self.data[min_r][min_c].update({'rowspan': new_rowspan, 'colspan': new_colspan, 'text': master_text})
            for r in range(min_r, max_r + 1):
                for c in range(min_c, max_c + 1):
                    if r != min_r or c != min_c:
                        self.data[r][c].update({'visible': False, 'text': ''})
            
            self.selected_cells.clear()
            self._create_table(self.get_col_widths())

        def split_cell(self, row, col):
            cell_data = self.data[row][col]
            rowspan, colspan = cell_data.get('rowspan', 1), cell_data.get('colspan', 1)
            cell_data.update({'rowspan': 1, 'colspan': 1})
            for r in range(row, row + rowspan):
                for c in range(col, col + colspan):
                    if r != row or c != col:
                        self.data[r][c]['visible'] = True
            self.selected_cells.clear()
            self._create_table(self.get_col_widths())

        def add_row(self, index, above=True):
            if not self.data: return
            cols = len(self.data[0]) if self.data else 0
            new_row_index = index if above else index + 1
            self.data.insert(new_row_index, [{'text': '', 'rowspan': 1, 'colspan': 1, 'visible': True} for _ in range(cols)])
            self._create_table(self.get_col_widths())

        def delete_row(self, index):
            if not self.data or len(self.data) <= 1: return
            for c in range(len(self.data[index])):
                master = self._find_master_cell(index, c)
                if master and (self.data[master[0]][master[1]]['rowspan'] > 1 or self.data[master[0]][master[1]]['colspan'] > 1) and master[0] != index:
                    messagebox.showwarning("Action impossible", "Impossible de supprimer une ligne qui coupe une cellule fusionnée.", parent=self); return
            del self.data[index]
            self._create_table(self.get_col_widths())

        def add_col(self, index, left=True):
            if not self.data: return
            new_col_index = index if left else index + 1
            for r in range(len(self.data)):
                self.data[r].insert(new_col_index, {'text': '', 'rowspan': 1, 'colspan': 1, 'visible': True})
            self._create_table(self.get_col_widths())

        def delete_col(self, index):
            if not self.data or len(self.data[0]) <= 1: return
            for r in range(len(self.data)):
                master = self._find_master_cell(r, index)
                if master and (self.data[master[0]][master[1]]['rowspan'] > 1 or self.data[master[0]][master[1]]['colspan'] > 1) and master[1] != index:
                    messagebox.showwarning("Action impossible", "Impossible de supprimer une colonne qui coupe une cellule fusionnée.", parent=self); return
            for r in range(len(self.data)):
                del self.data[r][index]
            self._create_table(self.get_col_widths())

        def _save_state_for_undo(self):
            """Helper to save current table state."""
            self.get_data() # Ensure data model is up-to-date with text in widgets
            return {
                'data': copy.deepcopy(self.data),
                'col_widths': self.get_col_widths()
            }

        def _restore_state_from_undo(self, state):
            """Helper to restore table state."""
            self.data = copy.deepcopy(state['data'])
            self._create_table(state['col_widths'])

        # Les méthodes de redimensionnement restent les mêmes
        def _update_cursor(self, event):
            if not self.cell_widgets: self.config(cursor=""); return
            x = event.x; on_separator = False
            for (r, c), widget in self.cell_widgets.items():
                if r == 0 and c < len(self.data[0]) - 1:
                    separator_x = widget.winfo_x() + widget.winfo_width()
                    if abs(x - separator_x) < 5:
                        self.config(cursor="sb_h_double_arrow"); self._resize_col_index = c; on_separator = True; break
            if not on_separator: self.config(cursor=""); self._resize_col_index = None

        def _on_press(self, event):
            if self._resize_col_index is not None:
                self._resize_start_x = event.x
                if self.undo_manager:
                    self._undo_state_before_resize = self._save_state_for_undo()

        def _extend_selection(self, event, from_drag=False):
            if not self._selection_anchor: return
            current_cell = self._get_cell_at_event(event)
            if not current_cell: return
            row, col = current_cell
            self.selected_cells.clear()
            r_anchor, c_anchor = self._selection_anchor
            r_min, r_max = sorted((r_anchor, row)); c_min, c_max = sorted((c_anchor, col))
            for r_iter in range(r_min, r_max + 1):
                for c_iter in range(c_min, c_max + 1):
                    self.selected_cells.add((r_iter, c_iter))
            self._update_selection_visuals()

        def _on_drag(self, event):
            if self._resize_col_index is not None:
                col_widget = self.cell_widgets.get((0, self._resize_col_index))
                if not col_widget: return
                delta_x = event.x - self._resize_start_x
                new_width_px = max(20, col_widget.winfo_width() + delta_x)
                self.grid_columnconfigure(self._resize_col_index, minsize=new_width_px)
                new_width_char = max(2, int(new_width_px / 8))
                for r in range(len(self.data)):
                    widget = self.cell_widgets.get((r, self._resize_col_index))
                    if widget: widget.config(width=new_width_char)
                self._resize_start_x = event.x
            elif self._selection_anchor: # Ne faire glisser la sélection que si elle a commencé
                self._extend_selection(event, from_drag=True)

        def _on_release(self, event):
            if self._resize_col_index is not None and self.undo_manager and hasattr(self, '_undo_state_before_resize'):
                old_state = self._undo_state_before_resize
                new_state = self._save_state_for_undo()
                self.undo_manager.register(lambda: self._restore_state_from_undo(old_state), lambda: self._restore_state_from_undo(new_state))
                del self._undo_state_before_resize
            self._resize_col_index = None
            self._selection_anchor = None # Réinitialiser l'ancre de sélection

        def _on_cell_press(self, event):
            cell_coords = self._get_cell_at_event(event)
            if cell_coords:
                self._start_selection(event, *cell_coords)

        def _on_cell_drag(self, event):
            self._extend_selection(event, from_drag=True)

        def _get_cell_at_event(self, event):
            # event.x_root, event.y_root sont les coordonnées absolues de l'écran
            widget_under_cursor = self.winfo_containing(event.x_root, event.y_root)
            if widget_under_cursor:
                # Le widget trouvé peut être la cellule Text ou le cadre Table lui-même
                for (r, c), widget in self.cell_widgets.items():
                    if widget == widget_under_cursor:
                        return self._find_master_cell(r, c)
            return None

        def _delete_self(self):
            if messagebox.askyesno("Confirmation", "Voulez-vous vraiment supprimer ce tableau ?", parent=self):                
                if hasattr(self.parent_text_widget, 'embedded_tables') and self in self.parent_text_widget.embedded_tables:
                    self.parent_text_widget.embedded_tables.remove(self)
                self.parent_text_widget.delete(self)

    class ImageCreationDialog(simpledialog.Dialog):
        def __init__(self, parent, title=None):
            self.image_source = None
            self.photo_preview = None
            super().__init__(parent, title=title)

        def body(self, master):
            self.result = None
            main_frame = ttk.Frame(master)
            main_frame.pack(padx=10, pady=10)

            self.image_preview = ttk.Label(main_frame, text="🖼️\nNouvelle image", font=(base_font_family, 12), bootstyle=SECONDARY, padding=20, width=20, anchor="center", relief="solid", borderwidth=1)
            self.image_preview.pack(pady=(0, 15))

            ttk.Button(main_frame, text="Choisir depuis le PC...", command=self.select_local_image).pack(pady=2, fill='x')
            ttk.Button(main_frame, text="Importer depuis une URL...", command=self.import_from_url).pack(pady=2, fill='x')

        def select_local_image(self):
            file_path = filedialog.askopenfilename(title="Sélectionner une image", filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Tous les fichiers", "*.*")], parent=self)
            if file_path:
                self.image_source = file_path
                self.update_preview(file_path)

        def import_from_url(self):
            if not requests:
                messagebox.showerror("Module manquant", "Le module 'requests' est nécessaire pour télécharger depuis une URL.\n\nVeuillez l'installer avec : pip install requests", parent=self)
                return
            url = simpledialog.askstring("Importer depuis une URL", "Collez le lien direct de l'image.", parent=self)
            if url and url.strip():
                try:
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    response = requests.get(url.strip(), timeout=10, headers=headers)
                    response.raise_for_status()
                    image_content = BytesIO(response.content)
                    self.image_source = image_content
                    self.update_preview(image_content)
                except Exception as e:
                    messagebox.showerror("Erreur de téléchargement", f"Impossible de charger l'image depuis l'URL.\nErreur: {e}", parent=self)
                    self.image_source = None

        def update_preview(self, source):
            try:
                with _Image.open(source) as img:
                    img.thumbnail((128, 128))
                    self.photo_preview = _ImageTk.PhotoImage(img)
                    self.image_preview.config(image=self.photo_preview, text="")
            except Exception as e:
                messagebox.showerror("Erreur d'image", f"Impossible de charger l'image : {e}", parent=self)
                self.image_source = None

        def buttonbox(self):
            box = ttk.Frame(self)
            ttk.Button(box, text="Annuler", command=self.cancel, bootstyle=SECONDARY).pack(side="right", padx=5, pady=5)
            ttk.Button(box, text="Valider", command=self.ok, bootstyle=SUCCESS, default="active").pack(side="right", padx=5, pady=5)
            self.bind("<Return>", self.ok)
            self.bind("<Escape>", self.cancel)
            box.pack()

        def apply(self):
            self.result = self.image_source

    class ResizableImage(ttk.Frame):
        def __init__(self, parent_editor, photo_image, original_path):
            super().__init__(parent_editor)
            self.parent_editor = parent_editor
            self.photo = photo_image
            self.original_path = original_path
            self.width = photo_image.width()
            self.height = photo_image.height()

            self.label = ttk.Label(self, image=self.photo)
            self.label.pack(fill=BOTH, expand=True)

            self.handles = {}
            self.handle_positions = ['nw', 'ne', 'sw', 'se']
            for pos in self.handle_positions:
                handle = ttk.Frame(self, width=8, height=8, relief="raised", borderwidth=1)
                self.handles[pos] = handle
                handle.bind("<B1-Motion>", lambda e, p=pos: self._on_drag(e, p))
                handle.bind("<ButtonPress-1>", self._on_press)
                handle.bind("<ButtonRelease-1>", self._on_release)

            self.bind("<Enter>", self.show_handles)
            self.bind("<Leave>", self.hide_handles)
            self.label.bind("<Enter>", self.show_handles)
            self.label.bind("<Leave>", self.hide_handles)

        def show_handles(self, event=None):
            self.handles['nw'].place(x=0, y=0, anchor='center')
            self.handles['ne'].place(x=self.winfo_width(), y=0, anchor='center')
            self.handles['sw'].place(x=0, y=self.winfo_height(), anchor='center')
            self.handles['se'].place(x=self.winfo_width(), y=self.winfo_height(), anchor='center')

        def hide_handles(self, event=None):
            for handle in self.handles.values():
                handle.place_forget()

        def _on_press(self, event):
            self.start_w = self.winfo_width()
            self.start_h = self.winfo_height()

        def _on_drag(self, event, handle_pos):
            dx = event.x_root - self.winfo_rootx()
            dy = event.y_root - self.winfo_rooty()
            
            if 'e' in handle_pos: self.width = max(20, dx)
            if 'w' in handle_pos: self.width = max(20, self.start_w - dx)
            if 's' in handle_pos: self.height = max(20, dy)
            if 'n' in handle_pos: self.height = max(20, self.start_h - dy)
            
            self.resize_image(int(self.width), int(self.height))

        def _on_release(self, event):
            pass # Rien à faire à la relâche

        def resize_image(self, width, height, register_undo=True):
            self.width, self.height = width, height
            with _Image.open(self.original_path) as img:
                img.thumbnail((self.width, self.height))
                self.photo = _ImageTk.PhotoImage(img)
                self.label.config(image=self.photo)

    def open_quest_flow_editor(details_vars):
        """Ouvre une fenêtre d'édition pour le déroulement de la quête avec des outils de formatage."""
        editor_popup = ttk.Toplevel(root_window)
        editor_popup.title("Déroulement de la quête")
        editor_popup.transient(root_window)
        editor_popup.grab_set() # Rendre la fenêtre modale
        editor_popup.geometry("1920x1080")
        editor_popup.minsize(600, 400)

        main_frame = ttk.Frame(editor_popup, padding=10)
        main_frame.pack(fill=BOTH, expand=True)
        main_frame.rowconfigure(1, weight=1) # La zone de texte s'étend
        main_frame.columnconfigure(0, weight=1)

        # Barre d'outils
        toolbar = ttk.Frame(main_frame)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        # Zone de texte
        quest_flow_text = tk.Text(main_frame, wrap="word", font=(base_font_family_val, 10), undo=False) # Undo est géré manuellement
        quest_flow_text.grid(row=1, column=0, sticky="nsew")

        # Barre de défilement pour la zone de texte
        text_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=quest_flow_text.yview)
        text_scrollbar.grid(row=1, column=1, sticky="ns")
        quest_flow_text.config(yscrollcommand=text_scrollbar.set)

        def apply_text_tag(tag_name, config, tag_type=None):
            """
            Applique un tag de texte à la sélection.
            tag_type: 'font', 'color', 'highlight', 'alignment' pour gérer les conflits.
            """
            try:
                start, end = quest_flow_text.tag_ranges("sel")
                
                # Supprimer les tags conflictuels basés sur le type
                if tag_type == 'font':
                    if tag_name.startswith('size_'):
                        for existing_tag in quest_flow_text.tag_names(start):
                            if existing_tag.startswith('size_'):
                                quest_flow_text.tag_remove(existing_tag, start, end)
                elif tag_type == 'color':
                    for existing_tag in quest_flow_text.tag_names(start):
                        if existing_tag.startswith('fg_'):
                            quest_flow_text.tag_remove(existing_tag, start, end)
                elif tag_type == 'highlight':
                    for existing_tag in quest_flow_text.tag_names(start):
                        if existing_tag.startswith('bg_'):
                            quest_flow_text.tag_remove(existing_tag, start, end)
                elif tag_type == 'alignment':
                    for existing_tag in quest_flow_text.tag_names(start):
                        if existing_tag in ['left', 'center', 'right']:
                            quest_flow_text.tag_remove(existing_tag, start, end)
                
                quest_flow_text.tag_configure(tag_name, **config)
                quest_flow_text.tag_add(tag_name, start, end)
            except ValueError:
                pass # Pas de sélection

        def toggle_bold():
            try:
                current_tags = quest_flow_text.tag_names("sel.first")
                font_details = font.Font(font=quest_flow_text.cget("font"))
                if 'bold' in current_tags:
                    font_details.configure(weight='normal')
                    quest_flow_text.tag_remove('bold', "sel.first", "sel.last")
                else:
                    font_details.configure(weight='bold')
                    quest_flow_text.tag_add('bold', "sel.first", "sel.last")
                quest_flow_text.tag_configure('bold', font=font_details)
            except tk.TclError:
                pass # Pas de sélection

        def toggle_underline():
            try:
                current_tags = quest_flow_text.tag_names("sel.first")
                font_details = font.Font(font=quest_flow_text.cget("font"))
                if 'underline' in current_tags:
                    font_details.configure(underline=False)
                    quest_flow_text.tag_remove('underline', "sel.first", "sel.last")
                else:
                    font_details.configure(underline=True)
                    quest_flow_text.tag_add('underline', "sel.first", "sel.last")
                quest_flow_text.tag_configure('underline', font=font_details)
            except tk.TclError:
                pass # Pas de sélection

        def change_text_color():
            color = colorchooser.askcolor(parent=editor_popup)[1]
            if color:
                apply_text_tag(f'fg_{color.replace("#", "")}', {'foreground': color}, tag_type='color')

        def change_highlight_color():
            color = colorchooser.askcolor(parent=editor_popup)[1]
            if color:
                apply_text_tag(f'bg_{color.replace("#", "")}', {'background': color}, tag_type='highlight')

        def change_font_size(size):
            try:
                size = int(size)
                if size > 0:
                    font_details = font.Font(font=quest_flow_text.cget("font")); font_details.configure(size=size)
                    apply_text_tag(f'size_{size}', {'font': font_details}, tag_type='font')
            except ValueError:
                pass # Taille invalide

        def align_text(alignment):
            quest_flow_text.tag_configure(alignment, justify=alignment)
            quest_flow_text.tag_add(alignment, "sel.first linestart", "sel.last lineend")

        def insert_image():
            dialog = ImageCreationDialog(editor_popup, title="Insérer une image")
            if dialog.result:
                source = dialog.result
                img_dir = os.path.join("data", "quest_images")
                os.makedirs(img_dir, exist_ok=True)
                try:
                    with _Image.open(source) as img:
                        ext = f".{img.format.lower()}" if img.format else ".png"
                        filename = f"q_img_{uuid.uuid4().hex[:8]}{ext}"
                        new_path = os.path.join(img_dir, filename)
                        img.save(new_path)
                    
                    with _Image.open(new_path) as saved_img:
                        saved_img.thumbnail((250, 250)); photo = _ImageTk.PhotoImage(saved_img)
                    resizable_image = ResizableImage(quest_flow_text, photo, new_path)
                    if not hasattr(quest_flow_text, 'embedded_images'): quest_flow_text.embedded_images = []
                    quest_flow_text.embedded_images.append(resizable_image)
                    quest_flow_text.window_create(tk.INSERT, window=resizable_image)

                except Exception as e:
                    messagebox.showerror("Erreur", f"Impossible de traiter l'image : {e}", parent=editor_popup)

        def insert_link():
            link_text = simpledialog.askstring("Lien", "Texte à afficher :", parent=editor_popup)
            if not link_text: return
            url = simpledialog.askstring("Lien", "URL (lien web) :", parent=editor_popup)
            if not url: return
            if not url.startswith(('http://', 'https://')): url = 'http://' + url

            tag_name = f"link_{uuid.uuid4().hex[:8]}"
            if not hasattr(quest_flow_text, 'hyperlinks'): quest_flow_text.hyperlinks = {}
            quest_flow_text.hyperlinks[tag_name] = url

            quest_flow_text.insert(tk.INSERT, link_text, (tag_name, "hyperlink_style"))

        class TableCreationDialog(simpledialog.Dialog):
            def __init__(self, parent, title=None):
                super().__init__(parent, title=title)

            def body(self, master):
                self.result = None
                main_frame = ttk.Frame(master)
                main_frame.pack(padx=10, pady=10)
                ttk.Label(main_frame, text="Lignes:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
                self.rows_var = tk.StringVar(value="3")
                self.rows_spinbox = ttk.Spinbox(main_frame, from_=1, to=20, textvariable=self.rows_var, width=5)
                self.rows_spinbox.grid(row=0, column=1, padx=5, pady=5)
                ttk.Label(main_frame, text="Colonnes:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
                self.cols_var = tk.StringVar(value="3")
                self.cols_spinbox = ttk.Spinbox(main_frame, from_=1, to=10, textvariable=self.cols_var, width=5)
                self.cols_spinbox.grid(row=1, column=1, padx=5, pady=5)
                return self.rows_spinbox

            def validate(self):
                try:
                    rows, cols = int(self.rows_var.get()), int(self.cols_var.get())
                    if not (1 <= rows <= 20 and 1 <= cols <= 10):
                        messagebox.showwarning("Valeurs invalides", "Veuillez respecter les limites :\nLignes (1-20)\nColonnes (1-10)", parent=self)
                        return 0
                    return 1
                except ValueError:
                    messagebox.showwarning("Entrée invalide", "Veuillez entrer des nombres entiers.", parent=self)
                    return 0

            def apply(self):
                self.result = (int(self.rows_var.get()), int(self.cols_var.get()))

        def insert_table():
            dialog = TableCreationDialog(editor_popup, title="Créer un Tableau")
            if dialog.result:
                rows, cols = dialog.result
                table = Table(quest_flow_text, rows, cols, style_obj=style_obj)
                if not hasattr(quest_flow_text, 'embedded_tables'): quest_flow_text.embedded_tables = []
                quest_flow_text.embedded_tables.append(table)
                quest_flow_text.window_create(tk.INSERT, window=table)

        # --- Boutons de la barre d'outils ---
        ttk.Button(toolbar, text="B", command=toggle_bold, width=3).pack(side="left", padx=2)
        ttk.Button(toolbar, text="U", command=toggle_underline, width=3).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Couleur", command=change_text_color).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Surligner", command=change_highlight_color).pack(side="left", padx=2)
        
        size_var = tk.StringVar(value="10")
        size_spinbox = ttk.Spinbox(toolbar, from_=8, to=32, textvariable=size_var, width=4, command=lambda: change_font_size(size_var.get()))
        size_spinbox.pack(side="left", padx=2)

        ttk.Button(toolbar, text=" Gauche", command=lambda: align_text('left')).pack(side="left", padx=2)
        ttk.Button(toolbar, text=" Centré", command=lambda: align_text('center')).pack(side="left", padx=2)
        ttk.Button(toolbar, text=" Droite", command=lambda: align_text('right')).pack(side="left", padx=2)

        ttk.Separator(toolbar, orient=VERTICAL).pack(side="left", padx=10, fill='y')
        ttk.Button(toolbar, text="🖼️ Image", command=insert_image).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🔗 Lien", command=insert_link).pack(side="left", padx=2)
        ttk.Button(toolbar, text="▦ Tableau", command=insert_table).pack(side="left", padx=2)

        # --- Boutons Sauvegarder et Fermer ---
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        button_frame.columnconfigure(0, weight=1) # Pousser les boutons vers la droite

        def save_and_close_editor():
            # 1. Sauvegarder le texte brut et les tags de style
            dump_data = quest_flow_text.dump("1.0", "end-1c", all=True)

            # 2. Sauvegarder les liens
            links_data = getattr(quest_flow_text, 'hyperlinks', {})

            # 3. Sauvegarder les images
            images_data = []
            if hasattr(quest_flow_text, 'embedded_images'):
                for resizable_img in quest_flow_text.embedded_images:
                    if resizable_img.winfo_exists():
                        try:
                            images_data.append({
                                'index': quest_flow_text.index(resizable_img), 'path': resizable_img.original_path,
                                'width': resizable_img.width, 'height': resizable_img.height
                            })
                        except tk.TclError: pass

            # 4. Sauvegarder les tableaux
            tables_data = []
            if hasattr(quest_flow_text, 'embedded_tables'):
                for table in quest_flow_text.embedded_tables:
                    if table.winfo_exists():
                        try:
                            tables_data.append({
                                'index': quest_flow_text.index(table), 'data': table.get_data(),
                                'col_widths': table.get_col_widths()
                            })
                        except tk.TclError: pass
            
            details_vars["quest_flow_data"] = {
                'dump': dump_data, 'hyperlinks': links_data,
                'images': images_data, 'tables': tables_data
            }
            editor_popup.destroy()

        ttk.Button(button_frame, text="Annuler", command=editor_popup.destroy, bootstyle=SECONDARY).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Sauvegarder et Fermer", command=save_and_close_editor, bootstyle=SUCCESS).pack(side="right")

        # --- Logique de chargement ---
        flow_data = details_vars.get("quest_flow_data", {})
        if flow_data:
            # Restaurer les images
            if not hasattr(quest_flow_text, 'embedded_images'): quest_flow_text.embedded_images = []
            for img_info in flow_data.get("images", []):
                path = img_info['path']
                if os.path.exists(path) and _Image and _ImageTk:
                    width, height = img_info.get('width', 250), img_info.get('height', 250)
                    with _Image.open(path) as img:
                        img.thumbnail((width, height)); photo = _ImageTk.PhotoImage(img)
                    resizable_image = ResizableImage(quest_flow_text, photo, path)
                    quest_flow_text.window_create(img_info['index'], window=resizable_image)
                    quest_flow_text.embedded_images.append(resizable_image)
            
            # Restaurer les tableaux
            if not hasattr(quest_flow_text, 'embedded_tables'): quest_flow_text.embedded_tables = []
            for table_info in flow_data.get("tables", []):
                table = Table(quest_flow_text, 0, 0, data=table_info['data'], col_widths=table_info['col_widths'], style_obj=style_obj)
                quest_flow_text.window_create(table_info['index'], window=table)
                quest_flow_text.embedded_tables.append(table)

            # Restaurer le texte et les tags
            for key, value, index in flow_data.get('dump', []):
                if key == "text": quest_flow_text.insert(index, value)
                elif key == "tagon": quest_flow_text.tag_add(value, index)
                elif key == "tagoff": quest_flow_text.tag_remove(value, index)
                elif key == "mark": quest_flow_text.mark_set(value, index)

            quest_flow_text.tag_configure("hyperlink_style", foreground=style_obj.colors.info, underline=True)
            if not hasattr(quest_flow_text, 'hyperlinks'): quest_flow_text.hyperlinks = {}
            quest_flow_text.hyperlinks.update(flow_data.get("hyperlinks", {}))
            for tag_name in quest_flow_text.tag_names():
                if tag_name in quest_flow_text.hyperlinks:
                    quest_flow_text.tag_bind(tag_name, "<Enter>", lambda e, t=tag_name: quest_flow_text.config(cursor="hand2"))
                    quest_flow_text.tag_bind(tag_name, "<Leave>", lambda e, t=tag_name: quest_flow_text.config(cursor=""))
                    quest_flow_text.tag_bind(tag_name, "<Button-1>", lambda e, t=tag_name: _webbrowser.open_new(quest_flow_text.hyperlinks[t]))

        # --- Logique de Glisser-Déposer (Drag and Drop) ---
        drag_data = {'widget': None, 'index': None, 'type': None}
        
        def dnd_start(event):
            index = quest_flow_text.index(f"@{event.x},{event.y}")
            widget_under_cursor = quest_flow_text.winfo_containing(event.x_root, event.y_root)
            
            found_widget = None
            if isinstance(widget_under_cursor, ResizableImage) or (hasattr(widget_under_cursor, 'master') and isinstance(widget_under_cursor.master, ResizableImage)):
                found_widget = widget_under_cursor if isinstance(widget_under_cursor, ResizableImage) else widget_under_cursor.master
                drag_data['type'] = 'image'
            elif isinstance(widget_under_cursor, Table) or (hasattr(widget_under_cursor, 'master') and isinstance(widget_under_cursor.master, Table)):
                found_widget = widget_under_cursor if isinstance(widget_under_cursor, Table) else widget_under_cursor.master
                drag_data['type'] = 'table'

            if found_widget:
                drag_data['widget'] = found_widget
                drag_data['index'] = quest_flow_text.index(found_widget)
                quest_flow_text.config(cursor="fleur")

        def dnd_end(event):
            if not drag_data['widget']: return
            
            old_index = drag_data['index']
            new_index = quest_flow_text.index(f"@{event.x},{event.y}")
            widget_to_move = drag_data['widget']

            if old_index != new_index:
                quest_flow_text.delete(old_index)
                quest_flow_text.window_create(new_index, window=widget_to_move)
                
            drag_data.update({'widget': None, 'index': None, 'type': None})
            quest_flow_text.config(cursor="")

        quest_flow_text.bind("<ButtonPress-1>", dnd_start, add='+') # Le '+' est crucial pour ne pas écraser les autres bindings
        quest_flow_text.bind("<ButtonRelease-1>", dnd_end, add='+')

        # --- Menu contextuel pour les images ---
        def show_image_context_menu(event):
            widget_under_cursor = quest_flow_text.winfo_containing(event.x_root, event.y_root)
            if isinstance(widget_under_cursor, ResizableImage) or (hasattr(widget_under_cursor, 'master') and isinstance(widget_under_cursor.master, ResizableImage)):
                menu = tk.Menu(editor_popup, tearoff=0)
                image_index = quest_flow_text.index(widget_under_cursor if isinstance(widget_under_cursor, ResizableImage) else widget_under_cursor.master)
                menu.add_command(label="Aligner à gauche", command=lambda: quest_flow_text.tag_add("left", f"{image_index} linestart", f"{image_index} lineend"))
                menu.add_command(label="Aligner au centre", command=lambda: quest_flow_text.tag_add("center", f"{image_index} linestart", f"{image_index} lineend"))
                menu.add_command(label="Aligner à droite", command=lambda: quest_flow_text.tag_add("right", f"{image_index} linestart", f"{image_index} lineend"))
                menu.tk_popup(event.x_root, event.y_root)

        quest_flow_text.bind("<Button-3>", show_image_context_menu, add='+')

        # Centrer la popup
        editor_popup.update_idletasks()
        root_x, root_y, root_width, root_height = root_window.winfo_x(), root_window.winfo_y(), root_window.winfo_width(), root_window.winfo_height()
        popup_width, popup_height = editor_popup.winfo_width(), editor_popup.winfo_height()
        center_x = int(root_x + (root_width / 2) - (popup_width / 2))
        center_y = int(root_y + (root_height / 2) - (popup_height / 2))
        editor_popup.geometry(f"+{center_x}+{center_y}")
        editor_popup.protocol("WM_DELETE_WINDOW", save_and_close_editor) # Sauvegarder à la fermeture

    load_quests()
    update_quest_list()