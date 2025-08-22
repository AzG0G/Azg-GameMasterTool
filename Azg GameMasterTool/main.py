# © 2025 AzG0G
# Ce logiciel est protégé par le droit d'auteur.
# Tous droits réservés.

import random
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox
import re
import os
import json
from datetime import datetime
from tkinter import font
from tkinter import filedialog
import shutil
from tkinter import simpledialog
import uuid
import colorsys
import threading
import time
import sys
from discord_rpc import DiscordRPCManager
import secondmain # Importation du nouveau module
import webbrowser
import warnings
import asyncio
try:
    from PIL import Image, ImageTk, ImageSequence
except ImportError:
    Image = None
    ImageTk = None
    ImageSequence = None
try:
    import requests
except ImportError:
    requests = None

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

asyncio.proactor_events._ProactorBasePipeTransport.__del__ = lambda self: None

# === Constantes et Variables globales ===
# Pour la sauvegarde des jets
details_lancers = []
# Pour la gestion des personnages et des paramètres
CHAR_DATA_DIR = os.path.join("data", "char")
SETTINGS_FILE = os.path.join("data", "settings.json")
CUSTOM_ROLLS_FILE = os.path.join("data", "custom_rolls.json")
saved_rolls = {} # Dictionnaire pour les jets personnalisés sauvegardés {nom: expression}
DEFAULT_SETTINGS = {
    "resolution": "1920x1080", "mode": "Fenêtré", "last_geometry": "",
    "skill_column_visibility": {
        "type": True, "jet_associe": True, "cout": True, "pa": True, "description": True
    }
}
app_settings = {} # Dictionnaire pour les paramètres chargés
RESOLUTIONS = ["800x600", "1280x720", "1440x900", "1920x1080", "2560x1440"]
# Pour Discord Rich Presence
DISCORD_CLIENT_ID = "1408373393388208169" # IMPORTANT: À REMPLACER
rpc_manager = None
# Pour le scaling de l'UI
BASE_WIDTH = 800.0
scaled_widgets = []
character_card_widgets = {} # Map char_id to its card widget for animations
all_characters = {"pjs": [], "pnjs": []} # Global variable to hold loaded characters
# Pour la navigation animée
current_page_name = None
is_animating = False

# Configuration des champs d'information de la fiche personnage
INFO_FIELDS_CONFIG = {
    "char_name": "Nom du personnage",
    "nickname": "Surnom",
    "age": "Âge",
    "race": "Race",
    "gender": "Sexe",
    "sexuality": "Orientation sexuelle",
    "rank": "Rang",
    "level": "Niveau",
    "xp": "XP",
    "money": "Argent",
    "height": "Taille"
}

# Textes pour Discord Rich Presence
page_details_map = {
    "menu": ("Dans le menu principal", "Prêt à jouer"),
    "des": ("Lanceur de dés", "Prépare un jet..."),
    "quetes": ("Gestion des Quêtes", "Organise l'aventure"),
    "persos": ("Fiches Personnages", "Consulte les PJ et PNJ"),
    "ia": ("IA Assistante", "Demande conseil au MJ virtuel"),
    "calendrier": ("Calendrier & Journal", "Note les événements"),
    "parametres": ("Dans les paramètres", "Configure l'application")
}

# === Fonctions de navigation ===
def animate_page_transition(new_page_name):
    """Gère l'animation de fondu vers le noir entre les pages."""
    global is_animating, current_page_name
    if is_animating or new_page_name == current_page_name:
        return
    is_animating = True

    # Créer un Toplevel noir qui couvre toute la fenêtre
    overlay = tk.Toplevel(root)
    overlay.configure(bg='black')
    overlay.overrideredirect(True)
    overlay.attributes('-alpha', 0.0)
    # Pour s'assurer que l'overlay couvre parfaitement la fenêtre principale,
    # on récupère ses dimensions et sa position actuelles.
    # Cela résout le problème où l'overlay n'avait pas la bonne taille ou position.
    # On utilise winfo_rootx/y pour obtenir la position de la zone de contenu,
    # et non de la fenêtre avec ses décorations (ce que fait winfo_x/y).
    root_x = root.winfo_rootx()
    root_y = root.winfo_rooty()
    root_width = root.winfo_width()
    root_height = root.winfo_height()
    overlay.geometry(f"{root_width}x{root_height}+{root_x}+{root_y}")
    overlay.lift()

    new_page_frame = pages[new_page_name]

    def fade_to_black(alpha=0.0):
        global current_page_name
        if alpha < 1.0:
            new_alpha = min(alpha + 0.1, 1.0)
            overlay.attributes('-alpha', new_alpha)
            root.after(25, fade_to_black, new_alpha)
        else:
            # Écran noir, on change la page en dessous
            if current_page_name and current_page_name in pages:
                pages[current_page_name].place_forget()
            
            new_page_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            new_page_frame.lift()
            current_page_name = new_page_name # Mettre à jour le nom de la page ici

            # Mettre à jour la présence Discord
            if rpc_manager:
                details, state = page_details_map.get(current_page_name, ("Quelque part...", "Explore l'outil"))
                rpc_manager.update_presence(details=details, state=state)
            
            # Démarrer le fondu depuis le noir
            fade_from_black()

    def fade_from_black(alpha=1.0):
        global is_animating
        if alpha > 0.0:
            new_alpha = max(alpha - 0.1, 0.0)
            overlay.attributes('-alpha', new_alpha)
            root.after(25, fade_from_black, new_alpha)
        else:
            # Animation terminée, on détruit l'overlay
            overlay.destroy()
            is_animating = False

    fade_to_black()

def afficher_page(page_name):
    """Affiche une page, avec animation si ce n'est pas la première."""
    global current_page_name
    
    if current_page_name is None: # Première page, pas d'animation
        if current_page_name and current_page_name in pages:
            pages[current_page_name].place_forget()
        pages[page_name].place(relx=0, rely=0, relwidth=1, relheight=1)
        current_page_name = page_name
        # Mettre à jour la présence Discord pour la première page
        if rpc_manager:
            details, state = page_details_map.get(page_name, ("Quelque part...", "Explore l'outil"))
            rpc_manager.update_presence(details=details, state=state)
    else:
        animate_page_transition(page_name)

def retour_menu_principal():
    """Affiche la page du menu principal."""
    afficher_page("menu")

def afficher_page_parametres():
    """Charge les paramètres actuels dans l'UI et affiche la page."""
    load_settings_to_ui()
    afficher_page("parametres")

def set_appwindow(main_window):
    """
    Astuce pour forcer une fenêtre (notamment en overrideredirect)
    à apparaître dans la barre des tâches sur Windows.
    """
    # Cette fonction est spécifique à Windows
    if os.name != 'nt':
        return
        
    try:
        import ctypes
        from ctypes import wintypes

        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080

        hwnd = wintypes.HWND(ctypes.windll.user32.GetParent(main_window.winfo_id()))
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = style & ~WS_EX_TOOLWINDOW
        style = style | WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        
        # Forcer une réévaluation de la fenêtre pour que le changement soit pris en compte
        main_window.wm_withdraw()
        main_window.wm_deiconify()
    except Exception as e:
        # Ne rien faire si ctypes n'est pas disponible ou en cas d'erreur
        print(f"Avertissement : Impossible d'appliquer l'astuce pour la barre des tâches : {e}")

# === Utilitaires de sauvegarde JSON ===
def enregistrer_jet_json(nb_des, nb_faces, resultats, total, moyenne):
    """Enregistre chaque jet dans data/lancers.json (append)."""
    # Dossier et fichier de destination
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    json_path = os.path.join(data_dir, "lancers.json")

    jet = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "nb_des": nb_des,
        "nb_faces": nb_faces,
        "resultats": resultats,
        "total": total,
        "moyenne": moyenne,
    }

    # Chargement existant
    try:
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = []
    except Exception:
        # Si le fichier est corrompu, on repart d'une liste vide
        data = []

    data.insert(0, jet)  # on garde le plus récent en tête

    # Écriture
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# === Gestion des paramètres ===
def register_scalable_widget(widget, base_size):
    """Enregistre un widget pour que sa police puisse être mise à l'échelle."""
    # On crée un objet Font unique pour ce widget pour pouvoir le modifier plus tard
    try:
        widget_font = font.Font(font=widget.cget("font"))
        widget.configure(font=widget_font)
        scaled_widgets.append({
            "widget": widget,
            "base_size": base_size,
            "font_obj": widget_font
        })
    except tk.TclError:
        # Gère le cas où la police n'est pas trouvée ou mal configurée
        print(f"Avertissement : Impossible de créer un objet Font pour le widget {widget}. Le scaling pourrait ne pas s'appliquer.")

def update_font_sizes(scale_factor):
    """Met à jour la taille de police de tous les widgets enregistrés."""
    for item in scaled_widgets:
        new_size = int(item["base_size"] * scale_factor)
        if new_size > 0: # S'assurer que la taille est positive
            item["font_obj"].configure(size=new_size)

def load_settings():
    """Charge les paramètres depuis settings.json, en les fusionnant avec les défauts."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(base_dir, SETTINGS_FILE)

    # On commence avec les paramètres par défaut
    settings = DEFAULT_SETTINGS.copy()

    if not os.path.exists(settings_path):
        return settings

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            user_settings = json.load(f)
            # On met à jour les valeurs par défaut avec celles de l'utilisateur,
            # ce qui ignore les clés inconnues et garde les défauts pour les clés manquantes.
            settings.update(user_settings)

            # Fusionner les dictionnaires imbriqués comme skill_column_visibility
            # pour s'assurer que les nouvelles clés de visibilité sont ajoutées si elles manquent.
            if 'skill_column_visibility' in settings and isinstance(settings['skill_column_visibility'], dict):
                default_vis = DEFAULT_SETTINGS['skill_column_visibility'].copy()
                default_vis.update(settings['skill_column_visibility'])
                settings['skill_column_visibility'] = default_vis
            else:
                settings['skill_column_visibility'] = DEFAULT_SETTINGS['skill_column_visibility'].copy()

            # Validation pour s'assurer que les valeurs sont cohérentes
            if settings.get("resolution") not in RESOLUTIONS:
                settings["resolution"] = DEFAULT_SETTINGS["resolution"]
            if settings.get("mode") not in ["Fenêtré", "Plein écran fenêtré", "Plein écran"]:
                settings["mode"] = DEFAULT_SETTINGS["mode"]
            return settings
    except (json.JSONDecodeError, IOError):
        return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """Sauvegarde les paramètres dans settings.json."""
    # Construit le chemin absolu vers le fichier de paramètres
    settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), SETTINGS_FILE)
    # S'assure que le dossier 'data' existe
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    try:
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except IOError as e:
        messagebox.showerror("Erreur de sauvegarde", f"Impossible de sauvegarder les paramètres : {e}")

def apply_settings(settings):
    """Applique les paramètres de résolution et de mode d'affichage."""
    global app_settings
    app_settings.update(settings) # Met à jour les paramètres globaux en cours d'exécution

    last_geometry = app_settings.get("last_geometry")
    resolution = app_settings.get("resolution", DEFAULT_SETTINGS["resolution"])
    mode = app_settings.get("mode", DEFAULT_SETTINGS["mode"])

    # --- Adaptation de la taille des polices (scaling) ---
    try:
        width, _ = map(int, resolution.split('x'))
        scale_factor = width / BASE_WIDTH
        update_font_sizes(scale_factor)
    except (ValueError, ZeroDivisionError):
        pass # En cas de résolution invalide, on ne fait rien sur le scaling

    is_windows = os.name == 'nt'

    # --- Application du mode d'affichage ---
    if mode == "Plein écran":
        root.overrideredirect(False) # S'assurer que les décorations sont gérées par l'OS
        root.attributes("-fullscreen", True)
        if is_windows:
            # Astuce pour s'assurer que l'icône reste dans la barre des tâches même en plein écran
            set_appwindow(root)
    elif mode == "Plein écran fenêtré":
        root.attributes("-fullscreen", False)
        root.overrideredirect(True) # Supprime les décorations
        root.geometry(resolution)
        if is_windows:
            # Astuce pour forcer l'affichage dans la barre des tâches
            set_appwindow(root)
    else: # "Fenêtré" par défaut
        root.attributes("-fullscreen", False)
        root.overrideredirect(False) # Assure que les décorations sont présentes
        # On applique la dernière géométrie sauvegardée si elle existe et est valide.
        # Sinon, on se rabat sur la résolution des paramètres.
        if last_geometry and re.match(r'^\d+x\d+\+\d+\+\d+$', last_geometry):
            root.geometry(last_geometry)
        else:
            root.geometry(resolution)
 

# === Gestion des données utilisateur (Historique et Jets Personnalisés) ===
def save_custom_rolls():
    """Sauvegarde les jets personnalisés dans custom_rolls.json."""
    rolls_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CUSTOM_ROLLS_FILE)
    os.makedirs(os.path.dirname(rolls_path), exist_ok=True)
    try:
        with open(rolls_path, "w", encoding="utf-8") as f:
            json.dump(saved_rolls, f, indent=2, sort_keys=True)
    except IOError as e:
        messagebox.showerror("Erreur de sauvegarde", f"Impossible de sauvegarder les jets personnalisés : {e}")

def load_custom_rolls():
    """Charge les jets personnalisés depuis custom_rolls.json."""
    global saved_rolls
    rolls_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CUSTOM_ROLLS_FILE)
    if not os.path.exists(rolls_path):
        saved_rolls = {}
        return

    try:
        with open(rolls_path, "r", encoding="utf-8") as f:
            saved_rolls = json.load(f)
        update_custom_rolls_combobox()
    except (json.JSONDecodeError, IOError):
        saved_rolls = {}
        messagebox.showerror("Erreur", "Impossible de charger le fichier des jets personnalisés.")

def save_character_data(character_data):
    """Sauvegarde les données d'un seul personnage dans son propre fichier JSON."""
    char_id = character_data.get('id')
    if not char_id:
        print("Erreur : Impossible de sauvegarder un personnage sans ID.")
        return

    char_file_path = os.path.join(CHAR_DATA_DIR, f"{char_id}.json")
    os.makedirs(os.path.dirname(char_file_path), exist_ok=True)
    try:
        with open(char_file_path, "w", encoding="utf-8") as f:
            json.dump(character_data, f, indent=2, sort_keys=True)
    except IOError as e:
        messagebox.showerror("Erreur de sauvegarde", f"Impossible de sauvegarder le personnage {char_id}: {e}")

def migrate_to_single_files():
    """Migre l'ancien characters.json vers la nouvelle structure de fichiers individuels."""
    old_file = os.path.join("data", "characters.json")
    if not os.path.exists(old_file):
        return

    try:
        with open(old_file, "r", encoding="utf-8") as f:
            old_data = json.load(f)

        os.makedirs(CHAR_DATA_DIR, exist_ok=True)

        for char_type, char_list in old_data.items():
            if char_type not in ["pjs", "pnjs"]:
                continue
            for char_data in char_list:
                char_data['char_type'] = char_type
                save_character_data(char_data)

        # Renommer l'ancien fichier pour éviter une nouvelle migration
        os.rename(old_file, f"{old_file}.bak")
        messagebox.showinfo(
            "Migration Réussie",
            "Les données des personnages ont été migrées vers le nouveau système de fichiers individuels.\n"
            "Votre ancien fichier a été sauvegardé en 'characters.json.bak'."
        )
    except Exception as e:
        messagebox.showerror("Erreur de Migration", f"Une erreur est survenue lors de la migration des données des personnages : {e}")

def load_characters():
    """Charge les personnages depuis le dossier data/char/."""
    global all_characters

    # Vérifier si une migration est nécessaire
    if os.path.exists(os.path.join("data", "characters.json")) and not os.path.exists(CHAR_DATA_DIR):
        migrate_to_single_files()

    os.makedirs(CHAR_DATA_DIR, exist_ok=True)
    all_characters = {"pjs": [], "pnjs": []}

    for filename in os.listdir(CHAR_DATA_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(CHAR_DATA_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    char_data = json.load(f)
                    char_type = char_data.get('char_type', 'pnjs') # Par défaut PNJ
                    if char_type == 'pjs':
                        all_characters['pjs'].append(char_data)
                    else:
                        all_characters['pnjs'].append(char_data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Erreur lors du chargement du fichier personnage {filename}: {e}")

    # Si le dossier est vide, créer des personnages d'exemple
    if not all_characters['pjs'] and not all_characters['pnjs']:
        # Ajout de données d'exemple pour la première utilisation
        example_pjs = [
            {'id': f'pj_{uuid.uuid4().hex[:8]}', 'name': 'Elora, la Brave', 'creation_timestamp': '2024-01-01T10:00:00', 'image_path': '', 'char_type': 'pjs'},
            {'id': f'pj_{uuid.uuid4().hex[:8]}', 'name': 'Boric, le Nain robuste', 'creation_timestamp': '2024-01-15T14:30:00', 'image_path': '', 'char_type': 'pjs'}
        ]
        example_pnjs = [
            {'id': f'pnj_{uuid.uuid4().hex[:8]}', 'name': 'Maître Elara', 'creation_timestamp': '2024-02-01T12:00:00', 'image_path': '', 'char_type': 'pnjs'},
            {'id': f'pnj_{uuid.uuid4().hex[:8]}', 'name': 'Le mystérieux Aubergiste', 'creation_timestamp': '2024-02-02T18:00:00', 'image_path': '', 'char_type': 'pnjs'}
        ]
        for char in example_pjs:
            all_characters['pjs'].append(char)
            save_character_data(char)
        for char in example_pnjs:
            all_characters['pnjs'].append(char)
            save_character_data(char)

def update_custom_rolls_combobox():
    """Met à jour la liste déroulante des jets personnalisés."""
    roll_names = sorted(list(saved_rolls.keys()))
    saved_rolls_combo['values'] = roll_names
    # On ne présélectionne rien pour forcer un choix utilisateur explicite
    saved_rolls_combo.set('')

def on_custom_roll_select(event):
    """Charge automatiquement l'expression quand un jet est sélectionné dans la combobox."""
    on_load_custom_roll()

# === Gestion de l'historique ===
def recharger_historique_json():
    """Recharge l'historique depuis le fichier JSON dans la Listbox."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "data", "lancers.json")

    try:
        if not os.path.exists(json_path):
            # Pas une erreur, le fichier n'a juste pas encore été créé
            return

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Vider l'affichage actuel avant de recharger
        effacer_historique_local()

        # Re-peupler la liste et les détails (le JSON est déjà trié du plus récent au plus ancien)
        for jet in data:
            nb_des = jet.get("nb_des", "?")
            nb_faces = jet.get("nb_faces", "?")
            total = jet.get("total", "?")
            resultats = jet.get("resultats", [])
            moyenne = jet.get("moyenne", 0.0)

            historique.insert("end", f"{nb_des}d{nb_faces} → {total}")
            details_lancers.append((nb_des, nb_faces, resultats, total, moyenne))
    except json.JSONDecodeError:
        messagebox.showerror("Erreur de chargement", "Le fichier d'historique (lancers.json) est corrompu.")
    except Exception as e:
        messagebox.showerror("Erreur de chargement", f"Impossible de lire l'historique : {e}")

def effacer_historique_local():
    """Vide la liste visible et les détails en mémoire, sans toucher au JSON."""
    historique.delete(0, "end")
    details_lancers.clear()


def effacer_historique_total():
    """Vide complètement le fichier JSON après confirmation."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "data", "lancers.json")

    if not messagebox.askyesno("Confirmation", "Voulez-vous VIDER définitivement tout l'historique (JSON) ?"):
        return

    try:
        if os.path.exists(json_path):
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        # on vide aussi l'affichage actuel pour cohérence
        effacer_historique_local()
        messagebox.showinfo("Succès", "Historique JSON vidé.")
    except Exception as e:
        messagebox.showerror("Erreur", f"Impossible de vider le JSON : {e}")


def show_dice_roller_help():
    """Affiche une fenêtre d'aide pour le lanceur de dés."""
    help_popup = ttk.Toplevel(root)
    help_popup.title("Aide - Lanceur de Dés")
    help_popup.transient(root)

    # Dimensions et centrage
    popup_width = 800
    popup_height = 750
    help_popup.minsize(popup_width, popup_height)

    # Centrer la popup par rapport à la fenêtre principale
    try:
        root_x = root.winfo_x()
        root_y = root.winfo_y()
        root_width = root.winfo_width()
        root_height = root.winfo_height()
        center_x = int(root_x + (root_width / 2) - (popup_width / 2))
        center_y = int(root_y + (root_height / 2) - (popup_height / 2))
        help_popup.geometry(f"{popup_width}x{popup_height}+{center_x}+{center_y}")
    except tk.TclError:
        pass

    # Rendre la fenêtre non redimensionnable
    help_popup.resizable(False, False)

    main_frame = ttk.Frame(help_popup, padding=15)
    main_frame.pack(fill="both", expand=True)

    ttk.Label(main_frame, text="❓ Aide du Lanceur de Dés", font=(base_font_family, 16, "bold"), bootstyle=PRIMARY).pack(pady=(0, 15), anchor="center")

    # Utiliser un widget Text pour un meilleur formatage et le défilement
    text_frame = ttk.Frame(main_frame)
    text_frame.pack(fill="both", expand=True)
    
    help_text_widget = tk.Text(text_frame, wrap="word", relief="flat", font=(base_font_family, 10), spacing1=5, spacing3=5, bg=style.colors.bg, fg=style.colors.fg, highlightthickness=0, borderwidth=0)
    help_text_widget.pack(side="left", fill="both", expand=True, padx=(0, 5))

    scrollbar = ttk.Scrollbar(text_frame, command=help_text_widget.yview)
    scrollbar.pack(side="right", fill="y")
    help_text_widget.config(yscrollcommand=scrollbar.set)

    # Définir les tags pour le style
    help_text_widget.tag_configure("h1", font=(base_font_family, 12, "bold"), foreground=style.colors.primary, spacing1=10, spacing3=10)
    help_text_widget.tag_configure("h2", font=(base_font_family, 10, "bold"), foreground=style.colors.info, spacing1=8, spacing3=2)
    help_text_widget.tag_configure("bold", font=(base_font_family, 10, "bold"))
    help_text_widget.tag_configure("bullet", lmargin1=20, lmargin2=20)
    help_text_widget.tag_configure("sub_bullet", lmargin1=40, lmargin2=40)

    # --- Section 1: Lanceur Standard ---
    help_text_widget.insert("end", "Le lanceur de dés standard\n", "h1")
    help_text_widget.insert("end", "Cette section vous permet d'effectuer des jets de dés simples rapidement. Voici le détail de chaque élément :\n\n")
    
    help_text_widget.insert("end", "1. Contrôles du jet\n", "h2")
    help_text_widget.insert("end", "• ", ("bold", "bullet"))
    help_text_widget.insert("end", "Nombre de dés : ", "bold")
    help_text_widget.insert("end", "Choisissez combien de dés vous souhaitez lancer (de 1 à 10).\n", "bullet")
    help_text_widget.insert("end", "• ", ("bold", "bullet"))
    help_text_widget.insert("end", "Nombre de faces : ", "bold")
    help_text_widget.insert("end", "Choisissez le type de dé (d4, d6, d20, etc.).\n", "bullet")
    help_text_widget.insert("end", "• ", ("bold", "bullet"))
    help_text_widget.insert("end", "Trier par : ", "bold")
    help_text_widget.insert("end", "Détermine l'ordre d'affichage des résultats individuels des dés :\n", "bullet")
    help_text_widget.insert("end", "  - ", ("bold", "sub_bullet"))
    help_text_widget.insert("end", "Ordre de jet : ", "bold")
    help_text_widget.insert("end", "Les résultats sont affichés dans l'ordre où ils ont été tirés.\n", "sub_bullet")
    help_text_widget.insert("end", "  - ", ("bold", "sub_bullet"))
    help_text_widget.insert("end", "Ordre croissant : ", "bold")
    help_text_widget.insert("end", "Les résultats sont triés du plus petit au plus grand.\n", "sub_bullet")
    help_text_widget.insert("end", "  - ", ("bold", "sub_bullet"))
    help_text_widget.insert("end", "Ordre décroissant : ", "bold")
    help_text_widget.insert("end", "Les résultats sont triés du plus grand au plus petit.\n", "sub_bullet")
    help_text_widget.insert("end", "• ", ("bold", "bullet"))
    help_text_widget.insert("end", "Bouton 'Lancer !' : ", "bold")
    help_text_widget.insert("end", "Cliquez sur ce bouton (ou appuyez sur Entrée dans un des champs) pour effectuer le jet.\n\n", "bullet")

    help_text_widget.insert("end", "2. Affichage des résultats\n", "h2")
    help_text_widget.insert("end", "Une fois le jet effectué, les résultats s'affichent dans la zone centrale :\n")
    help_text_widget.insert("end", "• ", ("bold", "bullet")); help_text_widget.insert("end", "Zone centrale : ", "bold"); help_text_widget.insert("end", "Affiche la liste de tous les résultats individuels des dés.\n", "bullet")
    help_text_widget.insert("end", "• ", ("bold", "bullet")); help_text_widget.insert("end", "Panneaux latéraux : ", "bold"); help_text_widget.insert("end", "Donnent des statistiques clés sur votre jet :\n", "bullet")
    help_text_widget.insert("end", "  - ", ("bold", "sub_bullet")); help_text_widget.insert("end", "Minimum / Maximum : ", "bold"); help_text_widget.insert("end", "Le plus petit et le plus grand résultat obtenu.\n", "sub_bullet")
    help_text_widget.insert("end", "  - ", ("bold", "sub_bullet")); help_text_widget.insert("end", "Total / Moyenne : ", "bold"); help_text_widget.insert("end", "La somme de tous les dés et la moyenne par dé.\n", "sub_bullet")
    help_text_widget.insert("end", "• ", ("bold", "bullet")); help_text_widget.insert("end", "Bouton 'Vider le jet' : ", "bold"); help_text_widget.insert("end", "Cliquez sur ce bouton pour réinitialiser la zone de résultats et préparer un nouveau jet.\n\n", "bullet")    

    # --- Section 2: Lanceur Personnalisé ---
    help_text_widget.insert("end", "Le lanceur personnalisé\n", "h1")
    help_text_widget.insert("end", "C'est un outil puissant qui vous permet de construire des expressions de jets complexes, bien au-delà d'un simple \"XdY\". Vous pouvez combiner différents types de dés, ajouter des modificateurs, et même effectuer des calculs mathématiques.\n", "bullet")
    help_text_widget.insert("end", "Utilisez le champ de saisie pour taper votre expression, puis cliquez sur le bouton ", "bullet")
    help_text_widget.insert("end", "'Lancer le jet personnalisé !'", "bold")
    help_text_widget.insert("end", " pour voir le résultat détaillé.\n\n", "bullet")

    # --- Section 3: Syntaxe des jets complexes ---
    help_text_widget.insert("end", "Syntaxe des jets complexes\n", "h1")
    help_text_widget.insert("end", "La syntaxe est conçue pour être flexible. Une expression est composée de groupes de dés (ex: 4d6) et d'opérateurs mathématiques.\n\n")
    
    help_text_widget.insert("end", "Modificateurs de groupe\n", "h2")
    help_text_widget.insert("end", "Ces modificateurs s'appliquent directement à un groupe de dés (ex: 2d10s). Ils doivent être collés au groupe.\n")
    help_text_widget.insert("end", "• ", ("bold", "bullet")); help_text_widget.insert("end", "s (sort) : ", "bold"); help_text_widget.insert("end", "Trie les résultats de ce groupe en ordre croissant. Ex: 4d6s\n", "bullet")
    help_text_widget.insert("end", "• ", ("bold", "bullet")); help_text_widget.insert("end", "e (explode) : ", "bold"); help_text_widget.insert("end", "Fait \"exploser\" les dés. Si un dé obtient le résultat maximum, il est relancé et le nouveau résultat est ajouté au total. Ex: 3d6e\n", "bullet")
    help_text_widget.insert("end", "  - ", ("bold", "sub_bullet")); help_text_widget.insert("end", "Condition personnalisée : ", "bold"); help_text_widget.insert("end", "Vous pouvez spécifier la condition d'explosion. Ex: 3d10e[>=8] (explose sur 8, 9 ou 10).\n", "sub_bullet")
    help_text_widget.insert("end", "• ", ("bold", "bullet")); help_text_widget.insert("end", "c (count) : ", "bold"); help_text_widget.insert("end", "Compte le nombre de \"succès\" au lieu de faire la somme. Le résultat du groupe sera le nombre de dés qui remplissent la condition. Ex: 10d6c[>4] (compte le nombre de résultats > 4).\n\n", "bullet")

    help_text_widget.insert("end", "Modificateurs globaux\n", "h2")
    help_text_widget.insert("end", "Ces modificateurs s'appliquent à la fin de l'expression entière et trient l'ensemble de tous les dés lancés.\n")
    help_text_widget.insert("end", "• ", ("bold", "bullet")); help_text_widget.insert("end", "sl (sort low) : ", "bold"); help_text_widget.insert("end", "Trie tous les résultats de dés de l'expression en ordre croissant. Ex: 2d6+1d8 sl\n", "bullet")
    help_text_widget.insert("end", "• ", ("bold", "bullet")); help_text_widget.insert("end", "sk (sort keep/high) : ", "bold"); help_text_widget.insert("end", "Trie tous les résultats de dés de l'expression en ordre décroissant. Ex: 2d6+1d8 sk\n\n", "bullet")

    help_text_widget.insert("end", "Opérateurs et exemples\n", "h2")
    help_text_widget.insert("end", "Vous pouvez utiliser les opérateurs +, -, *, / et les parenthèses ().\n")
    help_text_widget.insert("end", "• ", ("bold", "bullet")); help_text_widget.insert("end", "Exemple simple : ", "bold"); help_text_widget.insert("end", "2d8 + 5\n", "bullet")
    help_text_widget.insert("end", "• ", ("bold", "bullet")); help_text_widget.insert("end", "Exemple complexe : ", "bold"); help_text_widget.insert("end", "4d6e[>5]c[=6]s + 5\n", "bullet")
    help_text_widget.insert("end", "  - ", ("bold", "sub_bullet")); help_text_widget.insert("end", "Lance 4d6. Les dés > 5 explosent. Les résultats du groupe sont triés (s). Puis, on compte le nombre de succès qui sont égaux à 6 (c[=6]). Enfin, on ajoute 5 au nombre de succès.\n\n", "sub_bullet")

    # --- Section 4: Jets Sauvegardés ---
    help_text_widget.insert("end", "Gestion des jets sauvegardés\n", "h1")
    help_text_widget.insert("end", "Pour ne pas avoir à retaper vos jets complexes favoris, vous pouvez les sauvegarder.\n")
    help_text_widget.insert("end", "• ", ("bold", "bullet")); help_text_widget.insert("end", "Sauvegarder : ", "bold"); help_text_widget.insert("end", "Tapez votre expression dans le champ 'Jet Personnalisé', donnez-lui un nom dans le champ 'Nom du jet', puis cliquez sur 'Sauvegarder ce jet'.\n", "bullet")
    help_text_widget.insert("end", "• ", ("bold", "bullet")); help_text_widget.insert("end", "Charger : ", "bold"); help_text_widget.insert("end", "Sélectionnez un jet dans la liste déroulante et cliquez sur 'Charger'. L'expression apparaîtra dans le champ de saisie, prête à être lancée ou modifiée.\n", "bullet")
    help_text_widget.insert("end", "• ", ("bold", "bullet")); help_text_widget.insert("end", "Supprimer : ", "bold"); help_text_widget.insert("end", "Sélectionnez un jet dans la liste et cliquez sur 'Supprimer'.\n\n", "bullet")

    # --- Section 5: Historique ---
    help_text_widget.insert("end", "Historique des jets\n", "h1")
    help_text_widget.insert("end", "Chaque jet que vous effectuez (standard ou personnalisé) est ajouté à l'historique en bas de la page.\n")
    help_text_widget.insert("end", "• ", ("bold", "bullet")); help_text_widget.insert("end", "Détails : ", "bold"); help_text_widget.insert("end", "Double-cliquez sur une ligne de l'historique pour afficher une fenêtre avec tous les détails du jet.\n", "bullet")
    help_text_widget.insert("end", "• ", ("bold", "bullet")); help_text_widget.insert("end", "Gestion : ", "bold"); help_text_widget.insert("end", "Utilisez les boutons sous l'historique pour l'effacer de l'écran, le recharger depuis le fichier de sauvegarde, ou le vider complètement (action irréversible).\n", "bullet")

    help_text_widget.config(state="disabled") # Rendre le texte non modifiable

    # --- Logique pour le défilement par glissement (drag-to-scroll) ---
    # Pour éliminer les déchirements d'image, on utilise une méthode de défilement
    # incrémentale en pixels. C'est souvent plus fluide car cela donne des instructions
    # de déplacement simples au moteur graphique, plutôt que de recalculer une
    # position absolue à chaque instant.

    def on_text_press(event):
        """Enregistre la position de départ pour le défilement manuel."""
        if hasattr(help_text_widget, 'is_dragging') and help_text_widget.is_dragging:
            return
        help_text_widget.is_dragging = True
        help_text_widget.config(cursor="hand2")
        # Enregistre la position Y de départ pour calculer le delta de défilement.
        help_text_widget.last_y = event.y_root
        return "break"  # Empêche le comportement par défaut (sélection, etc.)

    def on_text_drag(event):
        """Défile le widget Text en fonction du mouvement de la souris (en pixels)."""
        if not hasattr(help_text_widget, 'is_dragging') or not help_text_widget.is_dragging:
            return

        delta_y = event.y_root - help_text_widget.last_y
        help_text_widget.yview_scroll(-delta_y, "pixels")
        help_text_widget.last_y = event.y_root
        return "break"  # Empêche la sélection de texte

    def on_text_release(event):
        """Restaure le curseur par défaut et réinitialise l'état de glissement."""
        help_text_widget.config(cursor="")
        help_text_widget.is_dragging = False

    # Lier les événements au widget de texte pour les clics gauche et droit
    for button in ["<Button-1>", "<Button-3>"]:
        help_text_widget.bind(button, on_text_press)
    for motion in ["<B1-Motion>", "<B3-Motion>"]:
        help_text_widget.bind(motion, on_text_drag)
    for release in ["<ButtonRelease-1>", "<ButtonRelease-3>"]:
        help_text_widget.bind(release, on_text_release)

    ttk.Button(main_frame, text="Fermer", command=help_popup.destroy, bootstyle=SECONDARY).pack(side="bottom", pady=10)
    help_popup.grab_set()

# === Fonctions Lanceur de Dés ===
def reinitialiser_resultats_jet(error_message=""):
    """Réinitialise les zones de résultats, affichant un message d'erreur si fourni."""
    min_var.set("-")
    max_var.set("-")
    total_var.set("-")
    moyenne_var.set("-")
    jet_info_var.set("-")
    result_text.config(state="normal")
    result_text.delete("1.0", "end")
    if error_message:
        result_text.insert("end", error_message)
        result_text.tag_add("center", "1.0", "end")
    result_text.config(state="disabled")

def lancer_des(event=None):
    """Gère le lancer de dés et met à jour l'interface graphique."""
    try:
        nb_des = int(entry_nb_des.get())
        nb_faces = int(entry_nb_faces.get())

        if not (1 <= nb_des <= 100 and 2 <= nb_faces <= 100000):
            reinitialiser_resultats_jet("⚠️ Valeurs invalides\n(1-100 dés, 2-100000 faces)")
            return

        resultats = [random.randint(1, nb_faces) for _ in range(nb_des)]

        # Tri des résultats selon l'option choisie
        sort_order = sort_order_var.get()
        if sort_order == "Ordre croissant":
            resultats.sort()
        elif sort_order == "Ordre décroissant":
            resultats.sort(reverse=True)

        total = sum(resultats)
        moyenne = total / nb_des
        min_val = min(resultats)
        max_val = max(resultats)

        # Mettre à jour les labels de stats
        min_var.set(str(min_val))
        max_var.set(str(max_val))
        total_var.set(str(total))
        moyenne_var.set(f"{moyenne:.2f}")
        jet_info_var.set(f"{nb_des}d{nb_faces}")

        # Mettre à jour la zone de texte centrale avec les résultats
        texte_resultats = str(resultats)
        result_text.config(state="normal")
        result_text.delete("1.0", "end")
        result_text.insert("end", texte_resultats)
        result_text.tag_add("center", "1.0", "end")
        result_text.config(state="disabled")

        # Historique : résumé uniquement
        historique.insert(0, f"{nb_des}d{nb_faces} → {total}")
        details_lancers.insert(0, (nb_des, nb_faces, resultats, total, moyenne))

        # Sauvegarde JSON du jet
        enregistrer_jet_json(nb_des, nb_faces, resultats, total, moyenne)

    except ValueError:
        reinitialiser_resultats_jet("⚠️ Entrée invalide\n(Nombres entiers requis)")


def afficher_details(event):
    selection = historique.curselection()
    if not selection:
        return
    index = selection[0]

    if index >= len(details_lancers): return # Sécurité si la liste est modifiée

    current_width = root.winfo_width()
    scale_factor = current_width / BASE_WIDTH

    # Unpack the data
    data_tuple = details_lancers[index]

    # Vérifier s'il s'agit d'un jet personnalisé
    if data_tuple[0] == "custom":
        _, expression, total, details_list, _ = data_tuple
        popup = ttk.Toplevel(root)
        popup.title(f"Détails pour : {expression}")
        popup.transient(root)

        main_frame = ttk.Frame(popup, padding=10)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text=f"Expression : {expression}", font=(base_font_family, 12, "bold")).pack(pady=5)
        ttk.Label(main_frame, text=f"Résultat Final : {total}", font=(base_font_family, 14, "bold"), bootstyle=PRIMARY).pack(pady=10)

        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill="both", expand=True, padx=10, pady=5)
        details_text = tk.Text(text_frame, height=8, width=60, wrap="word", bg=style.colors.bg, fg="white", font=("Courier", 9))
        details_text.insert("end", "\n".join(details_list))
        details_text.config(state="disabled")
        details_text.pack(side="left", fill="both", expand=True)

        ttk.Button(main_frame, text="Fermer", command=popup.destroy, bootstyle=SECONDARY).pack(pady=10)

        popup.update_idletasks()
        root_x, root_y, root_width, root_height = root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height()
        popup_width, popup_height = popup.winfo_width(), popup.winfo_height()
        center_x = int(root_x + (root_width / 2) - (popup_width / 2))
        center_y = int(root_y + (root_height / 2) - (popup_height / 2))
        popup.geometry(f"+{center_x}+{center_y}")
        popup.resizable(False, False)
        return # Fin du traitement pour les jets personnalisés

    # --- Logique existante pour les jets standards ---
    nb_des, nb_faces, resultats, total, moyenne = data_tuple
    min_val = min(resultats) if resultats else 0
    max_val = max(resultats) if resultats else 0

    # --- Fenêtre Popup ---
    popup = ttk.Toplevel(root)
    popup.title("Détails du jet 🎲")
    popup.transient(root)  # Garde la popup au-dessus de la fenêtre principale
    # On retire le mode "modal" (grab_set) pour ne pas bloquer l'application.
    # On retire overrideredirect pour restaurer la barre de titre (déplacement, fermeture).

    # Conteneur principal
    frame_container = ttk.Frame(popup)
    frame_container.pack(pady=10, padx=10, fill="both", expand=True)

    # --- Section Gauche (Min/Max) ---
    frame_stats_minmax_popup = ttk.Frame(frame_container, padding=10)
    frame_stats_minmax_popup.pack(side="left", fill="y", padx=(0, 10))
    ttk.Label(frame_stats_minmax_popup, text="Minimum", font=(base_font_family, int(10 * scale_factor), "bold")).pack()
    ttk.Label(frame_stats_minmax_popup, text=str(min_val), font=(base_font_family, int(14 * scale_factor)), bootstyle=INFO).pack(pady=(0, 10))
    ttk.Label(frame_stats_minmax_popup, text="Maximum", font=(base_font_family, int(10 * scale_factor), "bold")).pack()
    ttk.Label(frame_stats_minmax_popup, text=str(max_val), font=(base_font_family, int(14 * scale_factor)), bootstyle=SUCCESS).pack()

    # --- Section Droite (Total/Moyenne) ---
    frame_stats_total_popup = ttk.Frame(frame_container, padding=10)
    frame_stats_total_popup.pack(side="right", fill="y", padx=(10, 0))
    ttk.Label(frame_stats_total_popup, text="Total", font=(base_font_family, int(10 * scale_factor), "bold")).pack()
    ttk.Label(frame_stats_total_popup, text=str(total), font=(base_font_family, int(14 * scale_factor)), bootstyle=PRIMARY).pack(pady=(0, 10))
    ttk.Label(frame_stats_total_popup, text="Moyenne", font=(base_font_family, int(10 * scale_factor), "bold")).pack()
    ttk.Label(frame_stats_total_popup, text=f"{moyenne:.2f}", font=(base_font_family, int(14 * scale_factor)), bootstyle=WARNING).pack()

    # --- Section Centrale (Résultats) ---
    frame_rolls_popup = ttk.Frame(frame_container)
    frame_rolls_popup.pack(side="left", fill="both", expand=True)
    ttk.Label(frame_rolls_popup, text="Jet Effectué", font=(base_font_family, int(10 * scale_factor), "bold")).pack(pady=(0, 2))
    ttk.Label(frame_rolls_popup, text=f"{nb_des}d{nb_faces}", font=(base_font_family, int(14 * scale_factor)), bootstyle=PRIMARY).pack(pady=(0, 10))

    text_frame_popup = ttk.Frame(frame_rolls_popup)
    text_frame_popup.pack(fill="both", expand=True)
    result_text_popup = tk.Text(text_frame_popup, height=5, width=25, wrap="word", bg=style.colors.bg, fg="white", font=("Courier", int(9 * scale_factor)))
    result_text_popup.tag_configure("center", justify="center")
    scrollbar_popup = ttk.Scrollbar(text_frame_popup, command=result_text_popup.yview)
    result_text_popup.config(yscrollcommand=scrollbar_popup.set)
    scrollbar_popup.pack(side="right", fill="y")
    result_text_popup.pack(side="left", fill="both", expand=True)
    result_text_popup.insert("end", str(resultats))
    result_text_popup.tag_add("center", "1.0", "end")
    result_text_popup.config(state="disabled")

    # --- Bouton Fermer ---
    button_frame = ttk.Frame(popup)
    button_frame.pack(fill="x", pady=(0, 10))
    ttk.Button(button_frame, text="Fermer", command=popup.destroy, bootstyle=SECONDARY).pack()

    # Laisse la fenêtre s'ajuster, la centre, et la rend non-redimensionnable
    popup.update_idletasks()

    # Centrer la popup par rapport à la fenêtre principale
    try:
        root_x = root.winfo_x()
        root_y = root.winfo_y()
        root_width = root.winfo_width()
        root_height = root.winfo_height()
        popup_width = popup.winfo_width()
        popup_height = popup.winfo_height()

        center_x = int(root_x + (root_width / 2) - (popup_width / 2))
        center_y = int(root_y + (root_height / 2) - (popup_height / 2))
        popup.geometry(f"+{center_x}+{center_y}")
    except tk.TclError:
        # La fenêtre principale a peut-être été fermée, on ignore
        pass
    popup.resizable(False, False)

# === Analyseur de dés personnalisé ===
class CustomDiceParser:
    def __init__(self, expression_str):
        self.original_expression = expression_str.strip()
        expression_to_parse = self.original_expression.lower().strip()
        self.details = []
        self.results_list = []
        self.sort_mode = None # 'asc', 'desc', ou None

        # Détecter et retirer les suffixes de tri global (sl/sk)
        # Gère "2d6sl" et "2d6 sl"
        if expression_to_parse.endswith("sl"):
            self.sort_mode = "asc"
            # Enlève 'sl' et l'espace potentiel avant
            expression_to_parse = expression_to_parse[:-2].strip()
        elif expression_to_parse.endswith("sk"):
            self.sort_mode = "desc"
            # Enlève 'sk' et l'espace potentiel avant
            expression_to_parse = expression_to_parse[:-2].strip()

        self.expression = expression_to_parse
    def _roll_single_group(self, count, faces, modifiers):
        # Limites pour éviter les blocages
        if count > 1000 or faces > 100000:
            raise ValueError(f"Jet trop grand : {count}d{faces} (max 1000d100000)")

        # Analyse des modificateurs
        has_s = 's' in modifiers
        re_c = re.search(r'c\[([<>=]+)?(\d+)\]', modifiers)
        is_success_count = re_c is not None
        re_e = re.search(r'e(?:\[([<>=]+)?(\d+)\])?', modifiers)
        is_exploding = re_e is not None

        # Logique de jet
        all_rolls = []
        queue_to_roll = count
        initial_rolls = []

        # Premier jet
        if queue_to_roll > 0:
            initial_rolls = [random.randint(1, faces) for _ in range(queue_to_roll)]
            all_rolls.extend(initial_rolls)
            queue_to_roll = 0

            if is_exploding:
                exploding_dice = initial_rolls
                while exploding_dice:
                    next_exploding_dice = []
                    for r in exploding_dice:
                        op = (re_e.group(1) or '=') if re_e and re_e.group(1) else '='
                        explode_val = int(re_e.group(2)) if re_e and re_e.group(2) else faces

                        condition_met = False
                        if op == '=' and r == explode_val: condition_met = True
                        elif op == '>' and r > explode_val: condition_met = True
                        elif op == '<' and r < explode_val: condition_met = True
                        elif op == '>=' and r >= explode_val: condition_met = True
                        elif op == '<=' and r <= explode_val: condition_met = True

                        if condition_met:
                            new_roll = random.randint(1, faces)
                            all_rolls.append(new_roll)
                            next_exploding_dice.append(new_roll)
                    exploding_dice = next_exploding_dice

        # Tri
        if has_s:
            all_rolls.sort()

        self.results_list.extend(all_rolls)

        # Calcul du total ou du nombre de succès
        if is_success_count:
            op = re_c.group(1) or '='
            val = int(re_c.group(2))
            successes = 0
            for r in all_rolls:
                if op == '=' and r == val: successes += 1
                elif op == '>' and r > val: successes += 1
                elif op == '<' and r < val: successes += 1
                elif op == '>=' and r >= val: successes += 1
                elif op == '<=' and r <= val: successes += 1
            
            self.details.append(f"Jet {count}d{faces}{modifiers}: {all_rolls} -> {successes} succès")
            return successes
        else:
            total = sum(all_rolls)
            detail_str = f"Jet {count}d{faces}{modifiers}: "
            if initial_rolls != all_rolls:
                detail_str += f"{initial_rolls} -> explosions -> {all_rolls}"
            else:
                detail_str += f"{all_rolls}"
            self.details.append(f"{detail_str} -> Total: {total}")
            return total

    def _parse_term(self, term):
        term = term.strip()
        # La regex doit correspondre à l'intégralité du terme du dé
        dice_match = re.match(r'^(\d*)[d](\d+)((?:e(?:\[.*?\])?|c\[.*?\]|s)*)$', term)
        if not dice_match:
            # Ne devrait pas se produire si le `re.sub` dans `parse` est correct
            raise ValueError(f"Erreur interne: format de dé invalide '{term}'")
        
        count_str, faces_str, modifiers = dice_match.groups()
        count = int(count_str) if count_str else 1
        faces = int(faces_str)
        return self._roll_single_group(count, faces, modifiers)

    def parse(self):
        # Gérer les expressions purement arithmétiques (sans 'd')
        if 'd' not in self.expression:
            # Sécurité : n'autoriser que les chiffres et les opérateurs de base
            if re.search(r'[^0-9+\-*/\s().]', self.expression):
                raise ValueError("Caractères non autorisés dans le calcul.")
            try:
                # Remplacer / par // pour une division entière cohérente
                safe_expr = self.expression.replace('/', '//')
                result = eval(safe_expr, {"__builtins__": {}}, {})
                self.details.append(f"Calcul : {self.original_expression} = {result}")
                return result
            except Exception:
                raise ValueError("Expression arithmétique invalide.")

        # --- Nouvelle logique pour les expressions avec des dés ---

        # Fonction interne pour être utilisée par re.sub
        def roll_and_replace(match):
            dice_string = match.group(0)
            # _parse_term s'occupe du jet et de l'ajout aux détails
            value = self._parse_term(dice_string)
            # On retourne une chaîne pour la substitution
            return str(value)

        # Regex pour trouver toutes les notations de dés (ex: 2d6, d20, 10d10e[=10]s)
        dice_pattern = r'(\d*d\d+(?:e(?:\[.*?\])?|c\[.*?\]|s)*)'
        
        # Remplacer toutes les notations de dés par leur valeur numérique
        math_expression = re.sub(dice_pattern, roll_and_replace, self.expression)
        
        # Appliquer le tri global si demandé, après que tous les dés aient été lancés
        if self.results_list: # Ne pas trier ou afficher de message si aucun dé n'a été lancé
            if self.sort_mode == "asc":
                self.results_list.sort()
                self.details.append(f"-> Tri global croissant : {self.results_list}")
            elif self.sort_mode == "desc":
                self.results_list.sort(reverse=True)
                self.details.append(f"-> Tri global décroissant : {self.results_list}")

        # Sécurité : Vérifier que l'expression ne contient plus de lettres
        if re.search(r'[a-zA-Z]', math_expression):
            raise ValueError("Expression invalide après l'évaluation des dés.")
        
        try:
            # Remplacer / par // pour la division entière
            safe_expr = math_expression.replace('/', '//')
            # Évaluer l'expression mathématique finale en toute sécurité
            result = eval(safe_expr, {"__builtins__": {}}, {})
            self.details.append("---")
            self.details.append(f"Calcul final : {math_expression} = {result}")
            return result
        except Exception as e:
            raise ValueError(f"Erreur de calcul dans l'expression '{math_expression}': {e}")

def lancer_des_personnalise(event=None):
    expression = custom_entry_var.get()
    if not expression: return
    reinitialiser_resultats_jet()
    try:
        parser = CustomDiceParser(expression)
        total = parser.parse()
        update_ui_with_results(total, parser)
        # Ajout à l'historique de session
        historique.insert(0, f"{parser.original_expression} → {total}")
        details_lancers.insert(0, ("custom", parser.original_expression, total, parser.details, parser.results_list))
        # Vider le champ de saisie après un jet réussi
        custom_entry_var.set("")
    except Exception as e:
        reinitialiser_resultats_jet(f"⚠️ Erreur dans l'expression:\n{e}")

def on_save_custom_roll():
    """Sauvegarde l'expression actuelle avec le nom donné."""
    roll_name = custom_roll_name_var.get().strip()
    roll_expression = custom_entry_var.get().strip()

    if not roll_name or not roll_expression:
        messagebox.showwarning("Entrée manquante", "Veuillez fournir un nom et une expression pour le jet.")
        return

    if roll_name in saved_rolls and not messagebox.askyesno("Confirmation", f"Le nom '{roll_name}' existe déjà. Voulez-vous l'écraser ?"):
        return

    saved_rolls[roll_name] = roll_expression
    save_custom_rolls()
    update_custom_rolls_combobox()
    custom_roll_name_var.set("") # Clear the name entry
    messagebox.showinfo("Succès", f"Le jet '{roll_name}' a été sauvegardé.")

def on_load_custom_roll():
    """Charge l'expression sélectionnée dans le champ de saisie."""
    selected_name = saved_rolls_var.get()
    if not selected_name:
        # Pas d'avertissement ici, car cela peut être appelé par un événement
        return

    expression = saved_rolls.get(selected_name)
    if expression:
        custom_entry_var.set(expression)

def on_delete_custom_roll():
    """Supprime le jet personnalisé sélectionné."""
    selected_name = saved_rolls_var.get()
    if not selected_name:
        messagebox.showwarning("Aucune sélection", "Veuillez sélectionner un jet à supprimer.")
        return

    if messagebox.askyesno("Confirmation", f"Voulez-vous vraiment supprimer le jet '{selected_name}' ?"):
        if selected_name in saved_rolls:
            del saved_rolls[selected_name]
            save_custom_rolls()
            update_custom_rolls_combobox()
            messagebox.showinfo("Succès", f"Le jet '{selected_name}' a été supprimé.")

# === Helper function for theming ===
def lighten_color(hex_color, amount=0.1):
    """
    Lightens a hex color by a given amount.
    This is a self-contained implementation to avoid library version issues.
    """
    try:
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        # Convert RGB to HLS, modify lightness, and convert back to RGB
        h, l, s = colorsys.rgb_to_hls(rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0)
        l += (1 - l) * amount
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'
    except Exception:
        return hex_color # Fallback to original color if anything goes wrong

# === Custom Tooltip Class (to avoid version issues) ===
class Tooltip:
    """
    Custom Tooltip class to avoid ttkbootstrap version conflicts.
    It creates a Toplevel window with a styled label when the user
    hovers over a widget.
    """
    def __init__(self, widget, text, bootstyle="secondary", delay=500):
        self.widget = widget
        self.text = text
        self.bootstyle = bootstyle
        self.delay = delay
        self.tip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.schedule)
        self.widget.bind("<Leave>", self.hide)
        self.widget.bind("<ButtonPress>", self.hide)

    def schedule(self, event=None):
        self.hide()
        self.id = self.widget.after(self.delay, self.show)

    def show(self, event=None):
        if self.tip_window:
            return
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        frame = ttk.Frame(self.tip_window, bootstyle=self.bootstyle, padding=0)
        frame.pack()
        label = ttk.Label(frame, text=self.text, bootstyle=f"{self.bootstyle}-inverse", padding=(5, 3))
        label.pack()

    def hide(self, event=None):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

# === Fenêtre principale ===
root = ttk.Window(themename="darkly") # Le thème de base sera écrasé par notre style personnalisé
root.title("Azg GameMasterTool")
root.geometry("800x600")
root.minsize(800, 600) # Taille minimale pour éviter que les widgets soient écrasés

# === Style et Thème Personnalisé ===
style = ttk.Style()

# 1. Définir une police moderne et adaptée à l'OS pour une meilleure lisibilité
base_font_family = "Segoe UI" if os.name == 'nt' else "Helvetica"

# 2. On crée un nouveau thème "mj_custom" qui hérite des propriétés du thème "darkly"
style.theme_create("mj_custom", parent="darkly")

# 3. On sélectionne notre nouveau thème pour pouvoir le modifier et l'appliquer
style.theme_use("mj_custom")

# 4. On définit les nouvelles couleurs pour notre thème.
style.colors.primary = '#6e44ff'      # Un violet vibrant pour les actions principales
style.colors.secondary = '#555b6e'    # Un gris-bleu pour les actions secondaires
style.colors.success = '#17a2b8'      # Un bleu-vert pour les succès
style.colors.info = '#4f94d4'         # Un bleu plus clair pour l'information
style.colors.warning = '#ffc107'      # Un or/jaune pour les avertissements
style.colors.danger = '#dc3545'       # Un rouge classique pour le danger
style.colors.fg = '#e0e0e0'           # Un blanc cassé pour le texte, moins agressif que le blanc pur
style.colors.bg = '#222222'           # Un fond gris très sombre et neutre

# 5. Configuration fine des styles de widgets pour notre thème
# Appliquer la police de base à tous les widgets par défaut
style.configure('.', font=(base_font_family, 10), foreground=style.colors.fg)

# Boutons : police plus grasse, padding interne généreux et effet de survol
style.configure('TButton', font=(base_font_family, 11, 'bold'), padding=(10, 5), focusthickness=0)

# Pour chaque bootstyle, on définit l'effet de survol (hover) et de clic (pressed).
for bs in ['primary', 'info', 'success', 'warning', 'secondary', 'danger']:
    color = getattr(style.colors, bs)
    hover_color = lighten_color(color, 0.1)
    # Boutons pleins
    style.map(f'{bs}.TButton', background=[('pressed', color), ('active', hover_color)])
    # Boutons "Outline" (contour)
    style.map(f'{bs}.Outline.TButton',
              foreground=[('pressed', style.colors.fg), ('active', style.colors.fg)],
              background=[('pressed', color), ('active', hover_color)])

# Champs de saisie : bordure colorée en focus et padding interne
style.configure('TEntry', padding=(8, 4))
style.map('TEntry', bordercolor=[('focus', style.colors.primary)])

# Combobox
style.configure('TCombobox', padding=(8, 4))

# Labelframes : bordure subtile et titre stylisé pour une meilleure organisation visuelle
style.configure('TLabelframe', bordercolor=style.colors.secondary, borderwidth=1, padding=20)
style.configure('TLabelframe.Label', font=(base_font_family, 11, 'bold'), foreground=style.colors.info, background=style.colors.bg)

# Treeview : lignes plus hautes pour une meilleure lisibilité et en-têtes stylisés pour séparer les colonnes
style.configure('Treeview', rowheight=30, fieldbackground=style.colors.bg)
style.map('Treeview', background=[('selected', style.colors.primary)])
style.configure('Treeview.Heading', font=(base_font_family, 10, 'bold'), padding=5, relief='raised')

# === Icône de l'application ===
# Note : Pillow (pip install Pillow) est requis pour les formats .jpeg ou .png
if Image and ImageTk:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(base_dir, "data", "logo_large.jpeg")
    if os.path.exists(logo_path):
        try:
            logo_image = Image.open(logo_path)
            logo_photo = ImageTk.PhotoImage(logo_image)
            # IMPORTANT: Il faut garder une référence à l'objet PhotoImage,
            # sinon Python le supprime (garbage collection) et l'icône disparaît.
            root.logo_photo = logo_photo
            root.iconphoto(False, root.logo_photo)
        except Exception as e:
            print(f"Erreur détaillée lors du chargement de l'icône : {e}")
    else:
        print("NOTE: Logo 'data/logo_large.jpeg' non trouvé. L'icône par défaut sera utilisée.")
else:
    print("NOTE: Pillow non installé (pip install Pillow). L'icône par défaut sera utilisée.")

pages = {}  # Dictionnaire pour stocker les différentes pages

# === PAGE MENU PRINCIPAL ===
frame_menu = ttk.Frame(root)
pages["menu"] = frame_menu

menu_title = ttk.Label(frame_menu, text="Azg GameMasterTool", font=(base_font_family, 32, "bold"), bootstyle=PRIMARY)
menu_title.pack(pady=(50, 10))
register_scalable_widget(menu_title, 32)

menu_subtitle = ttk.Label(frame_menu, text="Votre compagnon pour des parties inoubliables", font=(base_font_family, 12), bootstyle=SECONDARY)
menu_subtitle.pack(pady=(0, 20))
register_scalable_widget(menu_subtitle, 12)

if Image and ImageTk:
    try:
        # Chemin vers le logo dans le dossier 'data'
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "data", "logo_large.jpeg")

        if os.path.exists(logo_path):
            logo_image = Image.open(logo_path)
            logo_image.thumbnail((180, 180))  # Taille max de 180x180 pixels
            logo_photo_menu = ImageTk.PhotoImage(logo_image)

            # Garder une référence pour éviter la suppression par le garbage collector
            frame_menu.logo_photo_menu = logo_photo_menu

            logo_label = ttk.Label(frame_menu, image=frame_menu.logo_photo_menu)
            # Assurer la transparence du fond en utilisant la couleur de fond du style
            logo_label.configure(background=style.colors.bg)
            logo_label.pack(pady=20)
        else:
            print(f"Avertissement : Le fichier logo '{logo_path}' est introuvable.")
    except Exception as e:
        print(f"Une erreur est survenue lors du chargement du logo du menu : {e}")

button_frame = ttk.Frame(frame_menu)
button_frame.pack()

ttk.Button(button_frame, text="🎲 Lanceur de Dés", bootstyle=(SUCCESS, OUTLINE), width=25, command=lambda: afficher_page("des")).pack(pady=8, ipady=8)
ttk.Button(button_frame, text="📜 Gestion des Quêtes", bootstyle=(INFO, OUTLINE), width=25, command=lambda: afficher_page("quetes")).pack(pady=8, ipady=8)
ttk.Button(button_frame, text="👤 Fiches Personnages", bootstyle=(INFO, OUTLINE), width=25, command=lambda: afficher_page("persos")).pack(pady=8, ipady=8)
ttk.Button(button_frame, text="🤖 IA Assistante", bootstyle=(PRIMARY, OUTLINE), width=25, command=lambda: afficher_page("ia")).pack(pady=8, ipady=8)
ttk.Button(button_frame, text="📅 Calendrier & Journal", bootstyle=(WARNING, OUTLINE), width=25, command=lambda: afficher_page("calendrier")).pack(pady=8, ipady=8)

# Boutons utilitaires en bas
bottom_frame = ttk.Frame(frame_menu)
bottom_frame.pack(side="bottom", pady=30)

ttk.Button(bottom_frame, text="⚙️ Paramètres", bootstyle=(SECONDARY, OUTLINE), width=15, command=afficher_page_parametres).pack(side="left", padx=10, ipady=5)
ttk.Button(bottom_frame, text="🚪 Fermer", bootstyle=(DANGER, OUTLINE), width=15, command=lambda: on_closing()).pack(side="left", padx=10, ipady=5)

# === PAGE LANCEUR DE DÉS ===
# Conteneur principal pour la page des dés, qui permettra le scroll
page_des_container = ttk.Frame(root)
pages["des"] = page_des_container

# Création du Canvas et de la Scrollbar verticale pour la page entière
canvas = tk.Canvas(page_des_container, highlightthickness=0)
scrollbar_page = ttk.Scrollbar(page_des_container, orient="vertical", command=canvas.yview)
canvas.configure(yscrollcommand=scrollbar_page.set)

scrollbar_page.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)

# Le frame qui contient VRAIMENT les widgets (il sera dans le canvas)
frame_des = ttk.Frame(canvas)

# On ajoute ce frame au canvas
canvas_frame_id = canvas.create_window((0, 0), window=frame_des, anchor="nw")

# Fonction pour mettre à jour la scroll region du canvas quand la taille du contenu change
def on_frame_configure(event):
    """Met à jour la scrollregion quand le contenu interne change de taille (ex: hauteur)."""
    canvas.configure(scrollregion=canvas.bbox("all"))

def on_canvas_configure(event):
    """Centre le contenu horizontalement quand la fenêtre (et donc le canvas) change de taille."""
    # On ajuste la largeur du frame interne à celle du canvas.
    # Les widgets à l'intérieur, utilisant .pack(), se centreront alors naturellement.
    canvas_width = event.width
    canvas.itemconfig(canvas_frame_id, width=canvas_width)

def _on_mousewheel(event):
    """Gère le défilement avec la molette de la souris sur le canvas."""
    # La division par 120 est typique pour Windows pour convertir le 'delta' en 'lignes' de défilement.
    # Le signe est inversé car un delta positif (molette vers le haut) doit faire défiler le contenu vers le bas.
    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

frame_des.bind("<Configure>", on_frame_configure)
canvas.bind("<Configure>", on_canvas_configure)


# --- Logique pour le défilement par glissement (drag-to-scroll) ---
# La méthode `yview_moveto` causait des déchirements d'image. On la remplace
# par la méthode native `scan_mark`/`scan_dragto` du Canvas, qui est
# spécifiquement conçue pour un défilement fluide par glissement et qui
# devrait éliminer les artefacts visuels.
def on_canvas_press(event):
    """Enregistre la position de départ pour le défilement par glissement (scan_mark)."""
    if isinstance(event.widget, (ttk.Entry, ttk.Combobox, tk.Listbox)):
        return
    if hasattr(canvas, 'is_dragging') and canvas.is_dragging:
        return
    canvas.is_dragging = True
    canvas.config(cursor="hand2")
    # `scan_mark` attend des coordonnées relatives au canvas.
    # On les calcule à partir des coordonnées absolues de l'événement pour plus de stabilité.
    canvas_x = event.x_root - canvas.winfo_rootx()
    canvas_y = event.y_root - canvas.winfo_rooty()
    canvas.scan_mark(canvas_x, canvas_y)

def on_canvas_drag(event):
    """Défile le canvas en utilisant scan_dragto pour un mouvement fluide."""
    if not hasattr(canvas, 'is_dragging') or not canvas.is_dragging:
        return
    # `scan_dragto` attend aussi des coordonnées relatives au canvas.
    canvas_x = event.x_root - canvas.winfo_rootx()
    canvas_y = event.y_root - canvas.winfo_rooty()
    canvas.scan_dragto(canvas_x, canvas_y, gain=1)

def on_canvas_release(event):
    """Restaure le curseur par défaut et réinitialise l'état de glissement."""
    canvas.config(cursor="")
    canvas.is_dragging = False

# --- Activation des différents types de scroll (molette, clic gauche/droit) ---
def bind_scroll_events(event):
    """Lie tous les événements de scroll quand la souris entre sur le canvas."""
    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    # Clic gauche
    canvas.bind_all("<ButtonPress-1>", on_canvas_press)
    canvas.bind_all("<B1-Motion>", on_canvas_drag)
    canvas.bind_all("<ButtonRelease-1>", on_canvas_release)
    # Clic droit
    canvas.bind_all("<ButtonPress-3>", on_canvas_press)
    canvas.bind_all("<B3-Motion>", on_canvas_drag)
    canvas.bind_all("<ButtonRelease-3>", on_canvas_release)

def unbind_scroll_events(event):
    """Délie les événements de scroll quand la souris quitte le canvas."""
    canvas.unbind_all("<MouseWheel>")
    canvas.unbind_all("<ButtonPress-1>")
    canvas.unbind_all("<B1-Motion>")
    canvas.unbind_all("<ButtonRelease-1>")
    canvas.unbind_all("<ButtonPress-3>")
    canvas.unbind_all("<B3-Motion>")
    canvas.unbind_all("<ButtonRelease-3>")
    # S'assurer que le curseur est réinitialisé si on quitte en plein drag
    on_canvas_release(None)

canvas.bind("<Enter>", bind_scroll_events)
canvas.bind("<Leave>", unbind_scroll_events)

top_nav_frame = ttk.Frame(frame_des)
top_nav_frame.pack(side="top", fill="x", padx=10, pady=10)

ttk.Button(top_nav_frame, text="⬅ Menu principal", bootstyle=SECONDARY, command=retour_menu_principal).pack(side="left")
ttk.Button(top_nav_frame, text="❓ Aide", bootstyle=(INFO, OUTLINE), command=show_dice_roller_help).pack(side="right")

des_title = ttk.Label(frame_des, text="🎲 Lanceur de Dés", font=("Helvetica", 18, "bold"), bootstyle=PRIMARY)
des_title.pack(pady=20)
register_scalable_widget(des_title, 18)

frame_controls = ttk.Frame(frame_des)
frame_controls.pack(pady=10)

# Listes prédéfinies pour les sélecteurs de dés
dice_counts = [str(i) for i in range(1, 11)]
dice_faces = [str(i) for i in [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]]

# Ligne 1: entrées
ttk.Label(frame_controls, text="Nombre de dés :").grid(row=0, column=0, padx=5, pady=2, sticky="w")
entry_nb_des = ttk.Combobox(frame_controls, values=dice_counts, width=5, state="readonly")
entry_nb_des.bind("<Return>", lancer_des)
entry_nb_des.set("3")
entry_nb_des.grid(row=0, column=1, padx=5, pady=2, sticky="w")

ttk.Label(frame_controls, text="Nombre de faces :").grid(row=0, column=2, padx=5, pady=2, sticky="w")
entry_nb_faces = ttk.Combobox(frame_controls, values=dice_faces, width=5, state="readonly")
entry_nb_faces.bind("<Return>", lancer_des)
entry_nb_faces.set("6")
entry_nb_faces.grid(row=0, column=3, padx=5, pady=2, sticky="w")

ttk.Button(frame_controls, text="🎲 Lancer !", bootstyle=SUCCESS, command=lancer_des).grid(row=0, column=4, padx=10, pady=2)

# Ligne 2: tri (l'aide a été supprimée car les valeurs sont maintenant fixes)
ttk.Label(frame_controls, text="Trier par :").grid(row=1, column=0, padx=5, pady=(0,6), sticky="w")
sort_order_options = ["Ordre de jet", "Ordre croissant", "Ordre décroissant"]
sort_order_var = tk.StringVar(value=sort_order_options[0])
sort_order_combo = ttk.Combobox(frame_controls, textvariable=sort_order_var, values=sort_order_options, state="readonly", width=15)
sort_order_combo.grid(row=1, column=1, columnspan=2, padx=5, pady=(0,6), sticky="w")

# --- Zone de résultats ---
frame_result = ttk.Frame(frame_des)
frame_result.pack(pady=10)

def update_ui_with_results(total, parser):
    """Met à jour l'interface avec les résultats du parser."""
    total_var.set(str(total))
    jet_info_var.set(parser.original_expression)

    result_text.config(state="normal")
    result_text.delete("1.0", "end")
    details_str = "\n".join(parser.details)
    result_text.insert("end", details_str)
    result_text.config(state="disabled")

    if parser.results_list:
        min_var.set(str(min(parser.results_list)))
        max_var.set(str(max(parser.results_list)))
        avg = sum(parser.results_list) / len(parser.results_list)
        moyenne_var.set(f"{avg:.2f}")
    else:
        min_var.set("-")
        max_var.set("-")
        moyenne_var.set("-")
# --- Section Gauche (Min/Max) ---
frame_stats_minmax = ttk.Frame(frame_result, padding=10)
frame_stats_minmax.grid(row=0, column=0, sticky="ns", padx=(0, 10))
min_label = ttk.Label(frame_stats_minmax, text="Minimum", font=(base_font_family, 10, "bold"))
min_label.pack()
register_scalable_widget(min_label, 10)
min_var = tk.StringVar(value="-")
label_min_val = ttk.Label(frame_stats_minmax, textvariable=min_var, font=("Helvetica", 14), bootstyle=INFO)
label_min_val.pack(pady=(0, 10))
register_scalable_widget(label_min_val, 14)

max_label = ttk.Label(frame_stats_minmax, text="Maximum", font=(base_font_family, 10, "bold"))
max_label.pack()
register_scalable_widget(max_label, 10)
max_var = tk.StringVar(value="-")
label_max_val = ttk.Label(frame_stats_minmax, textvariable=max_var, font=("Helvetica", 14), bootstyle=SUCCESS)
label_max_val.pack()
register_scalable_widget(label_max_val, 14)

# --- Section Centrale (Résultats) ---
frame_rolls = ttk.Frame(frame_result)
frame_rolls.grid(row=0, column=1, sticky="ns")

jet_label = ttk.Label(frame_rolls, text="Jet Effectué", font=(base_font_family, 10, "bold"))
jet_label.pack(pady=(0, 2))
register_scalable_widget(jet_label, 10)
jet_info_var = tk.StringVar(value="-")
label_jet_info = ttk.Label(frame_rolls, textvariable=jet_info_var, font=("Helvetica", 14), bootstyle=PRIMARY)
label_jet_info.pack(pady=(0, 10))
register_scalable_widget(label_jet_info, 14)
result_text = tk.Text(
    frame_rolls,
    height=4,  # Hauteur ajustée car le titre est maintenant au-dessus
    width=35,
    wrap="word",
    bg=style.colors.bg,
    fg="white",
    state="disabled"
)
result_text.tag_configure("center", justify="center")
result_text.pack(side="left", fill="both", expand=True)

scrollbar = ttk.Scrollbar(frame_rolls, command=result_text.yview)
scrollbar.pack(side="right", fill="y")
result_text.config(yscrollcommand=scrollbar.set)

# --- Section Droite (Total/Moyenne) ---
frame_stats_total = ttk.Frame(frame_result, padding=10)
frame_stats_total.grid(row=0, column=2, sticky="ns", padx=(10, 0))

total_label = ttk.Label(frame_stats_total, text="Total", font=(base_font_family, 10, "bold"))
total_label.pack()
register_scalable_widget(total_label, 10)
total_var = tk.StringVar(value="-")
label_total_val = ttk.Label(frame_stats_total, textvariable=total_var, font=("Helvetica", 14), bootstyle=PRIMARY)
label_total_val.pack(pady=(0, 10))
register_scalable_widget(label_total_val, 14)

moyenne_label = ttk.Label(frame_stats_total, text="Moyenne", font=(base_font_family, 10, "bold"))
moyenne_label.pack()
register_scalable_widget(moyenne_label, 10)
moyenne_var = tk.StringVar(value="-")
label_moyenne_val = ttk.Label(frame_stats_total, textvariable=moyenne_var, font=("Helvetica", 14), bootstyle=WARNING)
label_moyenne_val.pack()
register_scalable_widget(label_moyenne_val, 14)

btn_vider_jet = ttk.Button(frame_des, text="🧹 Vider le jet", command=reinitialiser_resultats_jet, bootstyle=SECONDARY)
btn_vider_jet.pack(pady=(5, 10))
Tooltip(btn_vider_jet, text="Réinitialise l'affichage du dernier jet.", bootstyle="info")

# --- Zone de jet personnalisé ---
frame_custom = ttk.Frame(frame_des)
frame_custom.pack(pady=(10, 10), fill='x', padx=20)

separator = ttk.Separator(frame_custom, orient=HORIZONTAL)
separator.pack(fill='x', pady=10)

custom_label = ttk.Label(frame_custom, text="Jet Personnalisé", font=(base_font_family, 12, "bold"))
custom_label.pack(anchor='center')
register_scalable_widget(custom_label, 12)

custom_entry_var = tk.StringVar()
custom_entry = ttk.Entry(frame_custom, textvariable=custom_entry_var, font=("Courier", 10))
custom_entry.bind("<Return>", lancer_des_personnalise)
custom_entry.pack(fill='x', pady=(5, 10), padx=40)
ttk.Button(frame_custom, text="🎲 Lancer le jet personnalisé !", bootstyle=PRIMARY, command=lancer_des_personnalise).pack()

# --- Zone de gestion des jets personnalisés ---
saved_rolls_labelframe = ttk.Labelframe(frame_des, text=" 💾 Jets Personnalisés Sauvegardés ", padding=15)
saved_rolls_labelframe.pack(pady=20, padx=20, fill='x')

# Frame pour la sauvegarde
save_frame = ttk.Frame(saved_rolls_labelframe)
save_frame.pack(fill='x', pady=(0, 10))
ttk.Label(save_frame, text="Nom du jet :").pack(side='left', padx=(0, 5))
custom_roll_name_var = tk.StringVar()
custom_roll_name_entry = ttk.Entry(save_frame, textvariable=custom_roll_name_var)
custom_roll_name_entry.pack(side='left', expand=True, fill='x', padx=5)
ttk.Button(save_frame, text="Sauvegarder ce jet", command=on_save_custom_roll, bootstyle=INFO).pack(side='left')
Tooltip(custom_roll_name_entry, text="Donnez un nom au jet dans le champ 'Jet Personnalisé' ci-dessus, puis cliquez sur 'Sauvegarder'.", bootstyle="info")

# Frame pour le chargement/suppression
load_frame = ttk.Frame(saved_rolls_labelframe)
load_frame.pack(fill='x', pady=10)
ttk.Label(load_frame, text="Jets sauvegardés :").pack(side='left', padx=(0, 5))
saved_rolls_var = tk.StringVar()
saved_rolls_combo = ttk.Combobox(load_frame, textvariable=saved_rolls_var, state="readonly", font=(base_font_family, 10))
saved_rolls_combo.pack(side='left', expand=True, fill='x', padx=5)
ttk.Button(load_frame, text="Charger", command=on_load_custom_roll, bootstyle=SUCCESS).pack(side='left', padx=5)
ttk.Button(load_frame, text="Supprimer", command=on_delete_custom_roll, bootstyle=DANGER).pack(side='left')
# Historique
hist_label = ttk.Label(frame_des, text="📜 Historique :", font=(base_font_family, 12, "bold"))
hist_label.pack(pady=5)
register_scalable_widget(hist_label, 12)

# Nouveau conteneur pour l'historique pour contrôler sa largeur avec du padding
hist_container = ttk.Frame(frame_des)
hist_container.pack(pady=5, padx=40, fill="x", expand=True) # padx=40 crée une marge de 40px de chaque côté

historique = tk.Listbox(hist_container, height=10, width=80, bg=style.colors.bg, fg="white", selectbackground=style.colors.secondary, selectforeground="white", highlightthickness=0, borderwidth=0, activestyle='none')
historique.pack(fill="both", expand=True) # Le listbox remplit son conteneur (qui a des marges)
historique.bind("<Double-1>", afficher_details)

# Boutons de gestion de l'historique
frame_actions = ttk.Frame(frame_des)
frame_actions.pack(pady=5)

btn_effacer_local = ttk.Button(frame_actions, text="🧹 Effacer localement l'historique", bootstyle=WARNING, command=effacer_historique_local)
btn_effacer_local.pack(side="left", padx=5)
Tooltip(btn_effacer_local, text="Vide l'historique affiché à l'écran (ne supprime pas le fichier).", bootstyle="warning")

btn_recharger = ttk.Button(frame_actions, text="🔄 Recharger l'historique", bootstyle=INFO, command=recharger_historique_json)
btn_recharger.pack(side="left", padx=5)
Tooltip(btn_recharger, text="Recharge l'historique depuis le fichier lancers.json.", bootstyle="info")

btn_effacer_total = ttk.Button(frame_actions, text="🗑️ Effacer entièrement l'historique", bootstyle=DANGER, command=effacer_historique_total)
btn_effacer_total.pack(side="left", padx=5)
Tooltip(btn_effacer_total, text="ATTENTION : Supprime définitivement le fichier lancers.json.", bootstyle="danger")

# === PAGE FICHES PERSONNAGES ===
frame_persos = ttk.Frame(root)
pages["persos"] = frame_persos

# --- Fonctions pour l'animation des GIFs ---
def start_gif_animation(label, size=(80, 80)):
    """Charge et démarre l'animation d'un GIF sur un Label."""
    if not (Image and ImageTk and ImageSequence and hasattr(label, 'gif_path')):
        return
    # On s'assure de ne pas démarrer une animation déjà en cours
    if hasattr(label, 'cancel_id'):
        return

    try:
        path = label.gif_path
        with Image.open(path) as gif_image:
            frames = []
            durations = []
            for frame in ImageSequence.Iterator(gif_image):
                frame_copy = frame.copy().convert("RGBA") # Assurer la compatibilité des modes
                frame_copy.thumbnail(size)
                frames.append(ImageTk.PhotoImage(frame_copy))
                durations.append(frame.info.get('duration', 100))

        if not frames: return

        label.frames = frames
        label.durations = durations
        label.frame_index = 0
        
        animate_gif_frame(label)
    except Exception as e:
        print(f"Erreur d'animation GIF {path}: {e}")

def animate_gif_frame(label):
    """Met à jour une frame de l'animation GIF."""
    if not hasattr(label, 'frames'): # L'animation a été arrêtée
        return
    frame = label.frames[label.frame_index]
    label.config(image=frame)
    label.frame_index = (label.frame_index + 1) % len(label.frames)
    duration = label.durations[label.frame_index]
    label.cancel_id = label.after(duration, lambda: animate_gif_frame(label))

def stop_gif_animation(label):
    """Arrête l'animation d'un GIF et nettoie."""
    if hasattr(label, 'cancel_id'):
        label.after_cancel(label.cancel_id)
    if hasattr(label, 'static_image'):
        label.config(image=label.static_image)
    for attr in ['cancel_id', 'frames', 'durations', 'frame_index']:
        if hasattr(label, attr):
            delattr(label, attr)

# --- Logique de Glisser-Déposer pour les fiches personnages ---
drag_data = {
    "widget": None,
    "char_data": None,
    "char_type": None,
    "press_x_root": 0,
    "press_y_root": 0,
    "initial_place_y": 0,
    "is_dragging": False
}

def drag_start(event, card, char_data, char_type):
    """Enregistre le point de départ d'un glissement potentiel."""
    if is_animating: return
    drag_data["widget"] = card
    drag_data["char_data"] = char_data
    drag_data["char_type"] = char_type
    drag_data["press_x_root"] = event.x_root
    drag_data["press_y_root"] = event.y_root
    drag_data["is_dragging"] = False
    # Lier les événements de mouvement et de relâchement à la fenêtre racine
    # pour capturer les mouvements même si le curseur quitte le widget.
    root.bind("<B1-Motion>", drag_motion)
    root.bind("<ButtonRelease-1>", drag_end)

def drag_motion(event):
    """Déplace la carte si le glissement a commencé."""
    card = drag_data["widget"]
    if not card: return

    if not drag_data["is_dragging"]:
        # Commencer à glisser seulement si la souris a bougé de manière significative
        if abs(event.x_root - drag_data["press_x_root"]) > 5 or abs(event.y_root - drag_data["press_y_root"]) > 5:
            drag_data["is_dragging"] = True
            # Soulever la carte au-dessus des autres et passer en mode 'place'
            card.lift()
            original_y = card.winfo_y()
            card.pack_forget()
            card.place(x=0, y=original_y, width=card.winfo_width())
            drag_data["initial_place_y"] = original_y

    if drag_data["is_dragging"]:
        # Déplacer la carte verticalement
        delta_y = event.y_root - drag_data["press_y_root"]
        new_y = drag_data["initial_place_y"] + delta_y
        card.place_configure(y=new_y)

def drag_end(event):
    """Finalise le glissement, réorganise les données et redessine la liste."""
    card = drag_data["widget"]
    # Délier les événements globaux
    root.unbind("<B1-Motion>")
    root.unbind("<ButtonRelease-1>")

    if not card or not drag_data["is_dragging"]:
        reset_drag_data()
        return

    target_y = card.winfo_y()
    other_cards = [child for child in character_list_frame.winfo_children() if child.winfo_exists() and child is not card]
    
    new_index = 0
    for i, child in enumerate(other_cards):
        if target_y < child.winfo_y() + (child.winfo_height() / 2):
            new_index = i
            break
        else:
            new_index = i + 1

    char_list = all_characters[drag_data["char_type"]]
    char_to_move = drag_data["char_data"]
    if char_to_move in char_list:
        char_list.remove(char_to_move) # Réorganisation en mémoire
        char_list.insert(new_index, char_to_move)

    sort_var.set("Ordre personnalisé")
    update_character_list_display()
    reset_drag_data()

def reset_drag_data():
    """Réinitialise les données globales de glissement."""
    drag_data.update({"widget": None, "char_data": None, "char_type": None, "is_dragging": False})

# --- Menu contextuel pour les fiches personnages ---
def animate_card_action(card, bootstyle, on_finish=None, is_disappearing=True):
    """
    Anime une carte avec un flash de couleur.
    Si is_disappearing est True, la carte est retirée après l'animation.
    """
    # L'option 'bootstyle' est un raccourci à la création. Après, il faut manipuler 'style'.
    # Le style d'un ttk.Frame est 'bootstyle.TFrame' (ex: 'danger.TFrame').
    original_style_name = card.cget("style")
    
    # Étape 1: Flash avec la nouvelle couleur
    flash_style_name = f"{bootstyle}.TFrame"
    card.configure(style=flash_style_name)
    
    def revert_or_remove():
        if is_disappearing:
            # Retire en douceur de la mise en page, puis détruit le widget
            card.pack_forget()
            card.destroy()
        else:
            # Revient à la couleur d'origine
            card.configure(style=original_style_name)
        if on_finish:
            on_finish()

    card.after(300, revert_or_remove) # Durée du flash
character_context_menu = tk.Menu(root, tearoff=0, font=(base_font_family, 10))

def show_character_context_menu(event, char_data, char_type):
    """Affiche le menu contextuel pour un personnage donné."""
    character_context_menu.delete(0, tk.END) # Vider le menu précédent
    
    char_id = char_data.get('id')

    # Utilisation d'emojis plus modernes pour un meilleur rendu sur tous les systèmes.
    character_context_menu.add_command(label=f"📝 | Éditer la fiche", command=lambda: edit_character(char_id, char_type))
    character_context_menu.add_command(label=f"✏️ | Renommer", command=lambda: rename_character(char_id, char_type))
    character_context_menu.add_command(label=f"📋 | Dupliquer", command=lambda: duplicate_character(char_id, char_type))
    
    transfer_to_type = "pnjs" if char_type == "pjs" else "pjs"
    transfer_label = "PNJ" if char_type == "pjs" else "PJ"
    character_context_menu.add_command(label=f"🔀 | Transférer vers {transfer_label}", command=lambda: transfer_character(char_id, char_type))
    
    character_context_menu.add_separator()
    character_context_menu.add_command(label=f"❌ | Supprimer", command=lambda: delete_character(char_id, char_type))
    character_context_menu.add_separator()
    character_context_menu.add_command(label=f"📄 | Exporter en PDF", command=lambda: export_character_to_pdf(char_id, char_type))
    character_context_menu.add_command(label=f"🔍 | Voir les détails/JSON", command=lambda: show_character_details(char_data))
    character_context_menu.tk_popup(event.x_root, event.y_root)

def show_character_details(char_data):
    """Affiche une popup avec les détails du personnage, y compris l'image."""
    popup = ttk.Toplevel(root)
    popup.title(f"Détails de {char_data.get('name', 'N/A')}")
    popup.transient(root)
    popup.grab_set()

    main_frame = ttk.Frame(popup, padding=20)
    main_frame.pack(fill="both", expand=True)

    # --- Section Image ---
    image_path = char_data.get('image_path', '')
    full_image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), image_path) if image_path else ""
    is_gif = image_path.lower().endswith('.gif')

    img_label = ttk.Label(main_frame, text="🖼️", font=(base_font_family, 48), anchor="center")
    img_label.pack(pady=(0, 15))

    if full_image_path and os.path.exists(full_image_path) and Image and ImageTk:
        try:
            img_label.gif_path = full_image_path # Stocker pour l'animation
            if is_gif:
                # Démarrer l'animation immédiatement pour les GIFs
                start_gif_animation(img_label, size=(300, 300)) # Taille augmentée
            else:
                # Afficher l'image statique
                with Image.open(full_image_path) as img:
                    img.thumbnail((300, 300)) # Taille augmentée
                    photo = ImageTk.PhotoImage(img)
                    img_label.config(image=photo, text="")
                    img_label.image = photo # Garder la référence
        except Exception as e:
            print(f"Erreur lors du chargement de l'image de détail : {e}")
            img_label.config(text="⚠️", font=(base_font_family, 48))

    # --- Section Détails (JSON brut) ---
    details_str = json.dumps(char_data, indent=2, ensure_ascii=False)
    
    text_widget = tk.Text(main_frame, wrap="none", height=15, width=50, font=("Courier", 10))
    text_widget.insert("1.0", details_str)
    text_widget.config(state="disabled")
    
    text_container = ttk.Frame(main_frame)
    text_container.pack(fill="both", expand=True)
    x_scrollbar = ttk.Scrollbar(text_container, orient="horizontal", command=text_widget.xview)
    y_scrollbar = ttk.Scrollbar(text_container, orient="vertical", command=text_widget.yview)
    text_widget.config(xscrollcommand=x_scrollbar.set, yscrollcommand=y_scrollbar.set)

    y_scrollbar.pack(side="right", fill="y")
    x_scrollbar.pack(side="bottom", fill="x")
    text_widget.pack(side="left", fill="both", expand=True)
    
    def on_popup_close():
        stop_gif_animation(img_label) # Arrête toute animation en cours
        popup.destroy()

    ttk.Button(main_frame, text="Fermer", command=on_popup_close, bootstyle=SECONDARY).pack(pady=(10,0))
    popup.protocol("WM_DELETE_WINDOW", on_popup_close)

    # Centrer la popup
    popup.update_idletasks()
    root_x, root_y, root_width, root_height = root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height()
    popup_width, popup_height = popup.winfo_width(), popup.winfo_height()
    center_x = int(root_x + (root_width / 2) - (popup_width / 2))
    center_y = int(root_y + (root_height / 2) - (popup_height / 2))
    popup.geometry(f"+{center_x}+{center_y}")

def open_character_sheet(char_id, char_type):
    """Ouvre la fenêtre complète de la fiche personnage."""
    char_list = all_characters.get(char_type, [])
    character_data = next((c for c in char_list if c.get('id') == char_id), None)
    if not character_data:
        messagebox.showerror("Erreur", "Personnage non trouvé.")
        return

    # --- Création de la fenêtre principale de la fiche ---
    sheet_window = ttk.Toplevel(root)
    sheet_window.title(f"Fiche de personnage : {character_data.get('name', 'N/A')}")
    sheet_window.geometry("1600x900") # Taille augmentée pour les nouveaux widgets
    sheet_window.minsize(1200, 800)
    sheet_window.transient(root)
    sheet_window.grab_set()

    # --- Menu contextuel pour le type de compétence ---
    skill_type_menu = tk.Menu(sheet_window, tearoff=0)
    skill_types = ["Aucun", "Jet", "Actif", "Passif", "Actif-Passif"]
    
    def set_skill_type(item_id, new_type):
        """Met à jour le type de la compétence et gère les dépendances."""
        skills_tree.set(item_id, 'type', new_type)
        if new_type != 'Jet':
            skills_tree.set(item_id, 'jet_associe', '') # Vider le jet associé si ce n'est plus un jet

    def show_skill_type_menu(event):
        """Affiche le menu contextuel pour changer le type d'une compétence."""
        item_id = skills_tree.identify_row(event.y)
        column_id = skills_tree.identify_column(event.x)
        if not item_id or not column_id: return

        column_index = int(column_id.replace('#', '')) - 1
        # Assurer que l'index est valide pour la liste des colonnes affichées
        if column_index < 0 or column_index >= len(skills_tree['columns']): return
        column_name = skills_tree['columns'][column_index]

        if column_name == 'type':
            skill_type_menu.delete(0, tk.END) # Vider le menu
            for skill_type in skill_types:
                skill_type_menu.add_command(
                    label=skill_type,
                    command=lambda i=item_id, t=skill_type: set_skill_type(i, t)
                )
            skill_type_menu.tk_popup(event.x_root, event.y_root)
            return "break" # Empêche la propagation de l'événement

    # --- Données locales ---
    stats_data = character_data.get('stats', [])
    inventory_content = character_data.get('inventory', '')
    # NOUVEAU: Charger les informations générales et leur visibilité
    info_data = character_data.get('info', {})
    info_visibility_data = character_data.get('info_visibility', {k: True for k in INFO_FIELDS_CONFIG.keys()})

    # On charge aussi les tags de l'inventaire s'ils existent
    skills_data = character_data.get('skills', [])
    inventory_tags = character_data.get('inventory_tags', [])
    # Variable pour suivre l'image à supprimer lors de la sauvegarde
    image_path_to_delete_on_save = tk.StringVar(value="")

    # --- Layout principal avec PanedWindow ---
    paned_window = ttk.PanedWindow(sheet_window, orient=tk.HORIZONTAL)
    paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # --- Frame de gauche (Image + Inventaire) ---
    left_frame = ttk.Frame(paned_window, padding=10)
    paned_window.add(left_frame, weight=1)

    # Image
    image_path = character_data.get('image_path', '')
    full_image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), image_path) if image_path else ""
    img_label = ttk.Label(left_frame, text="🖼️", font=(base_font_family, 48), anchor="center")
    img_label.pack(pady=10, fill="x")

    if full_image_path and os.path.exists(full_image_path) and Image and ImageTk:
        try:
            with Image.open(full_image_path) as img:
                img.thumbnail((450, 450))
                photo = ImageTk.PhotoImage(img)
                img_label.config(image=photo, text="")
                img_label.image = photo
        except Exception as e:
            print(f"Erreur chargement image fiche: {e}")
            img_label.config(text="⚠️")

    # --- Fonctions de gestion de l'image ---
    def change_character_image():
        """Ouvre une popup pour modifier l'image du personnage."""
        popup = ttk.Toplevel(sheet_window)
        popup.title("Modifier l'image")
        popup.transient(sheet_window)
        popup.grab_set()
        popup.resizable(False, False)

        main_frame = ttk.Frame(popup, padding=20)
        main_frame.pack(fill="both", expand=True)

        image_source_var = tk.StringVar()

        image_preview = ttk.Label(main_frame, text="🖼️\nNouvelle image", font=(base_font_family, 12), bootstyle=SECONDARY, padding=20, width=20, anchor="center", relief="solid", borderwidth=1)
        image_preview.pack(side="left", padx=(0, 20))

        image_buttons_frame = ttk.Frame(main_frame)
        image_buttons_frame.pack(anchor="center")

        def select_local_image():
            file_path = filedialog.askopenfilename(title="Sélectionner une image", filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Tous les fichiers", "*.*")], parent=popup)
            if file_path:
                image_source_var.set(file_path)
                try:
                    with Image.open(file_path) as img:
                        img.thumbnail((128, 128))
                        photo = ImageTk.PhotoImage(img)
                        image_preview.config(image=photo, text="")
                        image_preview.image = photo
                except Exception as e:
                    messagebox.showerror("Erreur d'image", f"Impossible de charger l'image : {e}", parent=popup)
                    image_source_var.set("")

        def import_from_url():
            if not requests:
                messagebox.showerror("Module manquant", "Le module 'requests' est nécessaire pour télécharger depuis une URL.\n\nVeuillez l'installer avec : pip install requests", parent=popup)
                return

            url = simpledialog.askstring("Importer depuis une URL", "Collez le lien direct de l'image.\n(Sources supportées : Discord, Imgur, Pinterest, etc.)", parent=popup)
            if url and url.strip():
                url = url.strip()
                image_source_var.set(url)
                try:
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    response = requests.get(url, timeout=10, headers=headers)
                    response.raise_for_status()
                    image_content = None
                    content_type = response.headers.get('Content-Type', '').lower()

                    if content_type.startswith('image/'):
                        image_content = response.content
                    elif content_type.startswith('text/html'):
                        match = re.search(r'<meta\s+property="og:image"\s+content="(.*?)"', response.text)
                        if match:
                            image_url = match.group(1).replace('&amp;', '&')
                            image_source_var.set(image_url)
                            image_response = requests.get(image_url, timeout=10, headers=headers)
                            image_response.raise_for_status()
                            image_content = image_response.content
                        else:
                            raise ValueError("Impossible de trouver un lien d'image direct (balise og:image) sur la page.")
                    else:
                        raise ValueError(f"L'URL ne pointe pas vers une image ou une page web reconnue. Type de contenu reçu : '{content_type}'.")

                    if image_content:
                        from io import BytesIO
                        image_data = BytesIO(image_content)
                        with Image.open(image_data) as img:
                            img.thumbnail((256, 256))
                            photo = ImageTk.PhotoImage(img)
                            image_preview.config(image=photo, text="")
                            image_preview.image = photo
                    else:
                        raise ValueError("Aucun contenu d'image n'a pu être récupéré.")
                except Exception as e:
                    messagebox.showerror("Erreur de téléchargement", f"Impossible de charger l'image depuis l'URL.\n\nVérifiez le lien et votre connexion.\n\nErreur: {e}", parent=popup)
                    image_source_var.set("")

        ttk.Button(image_buttons_frame, text="Choisir depuis le PC...", command=select_local_image).pack(pady=2, fill='x')
        ttk.Button(image_buttons_frame, text="Importer depuis une URL...", command=import_from_url).pack(pady=2, fill='x')

        def on_save_image():
            source = image_source_var.get()
            if not source:
                popup.destroy()
                return

            img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "character_images")
            os.makedirs(img_dir, exist_ok=True)
            final_image_path = ""

            try:
                if source.startswith(('http://', 'https://')):
                    response = requests.get(source, stream=True, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                    response.raise_for_status()
                    content_type = response.headers.get('content-type', '').lower()
                    ext = '.jpg'
                    if 'png' in content_type: ext = '.png'
                    elif 'gif' in content_type: ext = '.gif'
                    elif 'jpeg' in content_type: ext = '.jpg'
                    unique_filename = f"{uuid.uuid4().hex[:8]}{ext}"
                    save_path = os.path.join(img_dir, unique_filename)
                    with open(save_path, 'wb') as f: shutil.copyfileobj(response.raw, f)
                    final_image_path = os.path.join("data", "character_images", unique_filename)
                else:
                    ext = os.path.splitext(source)[1] or ".jpg"
                    unique_filename = f"{uuid.uuid4().hex[:8]}{ext}"
                    save_path = os.path.join(img_dir, unique_filename)
                    shutil.copy(source, save_path)
                    final_image_path = os.path.join("data", "character_images", unique_filename)

                final_image_path = final_image_path.replace("\\", "/")
                if character_data.get('image_path'): image_path_to_delete_on_save.set(character_data['image_path'])
                character_data['image_path'] = final_image_path
                with Image.open(save_path) as img:
                    img.thumbnail((450, 450))
                    photo = ImageTk.PhotoImage(img)
                    img_label.config(image=photo, text="")
                    img_label.image = photo
                popup.destroy()
            except Exception as e:
                messagebox.showerror("Erreur de sauvegarde d'image", f"Impossible de traiter l'image :\n{e}", parent=popup)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(20, 0))
        ttk.Button(button_frame, text="Annuler", command=popup.destroy, bootstyle=SECONDARY).pack(side="right", padx=(10, 0))
        ttk.Button(button_frame, text="💾 Valider", command=on_save_image, bootstyle=SUCCESS).pack(side="right")

    def remove_character_image():
        if not character_data.get('image_path'):
            messagebox.showinfo("Information", "Ce personnage n'a pas d'image.", parent=sheet_window)
            return
        if messagebox.askyesno("Confirmation", "Voulez-vous vraiment supprimer l'image ?\nLe changement sera appliqué à la sauvegarde.", parent=sheet_window):
            if character_data.get('image_path'): image_path_to_delete_on_save.set(character_data['image_path'])
            character_data['image_path'] = ""
            img_label.config(image="", text="🖼️")
            img_label.image = None

    # --- NOUVEAU: Boutons de gestion de l'image ---
    image_buttons_frame = ttk.Frame(left_frame)
    image_buttons_frame.pack(pady=(5, 10))
    ttk.Button(image_buttons_frame, text="Modifier l'image", command=change_character_image).pack(side="left", padx=5)
    ttk.Button(image_buttons_frame, text="Supprimer l'image", command=remove_character_image, bootstyle=(DANGER, OUTLINE)).pack(side="left", padx=5)

    # Inventaire
    inventory_frame = ttk.Labelframe(left_frame, text="Équipement & Inventaire", padding=10)
    inventory_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
    
    # Barre d'outils pour le texte
    inventory_toolbar = ttk.Frame(inventory_frame)
    inventory_toolbar.pack(fill="x", pady=(0, 5))

    inventory_text = tk.Text(inventory_frame, wrap="word", height=10, font=(base_font_family, 10), undo=True)
    inventory_text.pack(fill=tk.BOTH, expand=True)
    inventory_text.insert("1.0", inventory_content)

    # Appliquer les tags sauvegardés
    for tag_info in inventory_tags:
        tag_name = tag_info['name']
        config = tag_info.get('config', {})
        # Re-créer la police si nécessaire
        if 'font' in config and isinstance(config['font'], list):
            # Logique de chargement de police robuste pour gérer les anciens et nouveaux formats de sauvegarde.
            # L'ancien format pouvait contenir des entiers (0/1) pour les styles,
            # et le correctif précédent supprimait à tort la taille de la police (qui est aussi un entier).
            font_list = config['font']
            final_font_list = []
            if len(font_list) > 0: final_font_list.append(font_list[0]) # Family
            if len(font_list) > 1:
                try:
                    final_font_list.append(int(font_list[1])) # Size
                except (ValueError, TypeError):
                    final_font_list.append(10) # Fallback size
            else:
                final_font_list.append(10)

            if len(font_list) > 2:
                for style_item in font_list[2:]:
                    if style_item == 1: # Ancien format pour 'underline'
                        if 'underline' not in final_font_list: final_font_list.append('underline')
                    elif style_item == 0: # Ancien format pour 'not underline'
                        pass
                    elif isinstance(style_item, str):
                        final_font_list.append(style_item)
            config['font'] = tuple(final_font_list)

        if config: # S'assurer qu'il y a quelque chose à configurer
            inventory_text.tag_configure(tag_name, **config)

        for start, end in tag_info['ranges']:
            inventory_text.tag_add(tag_name, start, end)

    # --- Logique de la barre d'outils de l'inventaire ---
    def apply_text_tag(tag_name, config):
        try:
            start, end = inventory_text.tag_ranges("sel")
            inventory_text.tag_configure(tag_name, **config)
            inventory_text.tag_add(tag_name, start, end)
        except ValueError:
            pass # Pas de sélection

    def toggle_bold():
        try:
            current_tags = inventory_text.tag_names("sel.first")
            font_details = font.Font(font=inventory_text.cget("font"))
            font_details.configure(weight='bold' if 'bold' not in current_tags else 'normal')
            apply_text_tag('bold', {'font': font_details})
        except tk.TclError:
            pass # Pas de sélection

    def toggle_underline():
        try:
            current_tags = inventory_text.tag_names("sel.first")
            font_details = font.Font(font=inventory_text.cget("font"))
            font_details.configure(underline='underline' not in current_tags)
            apply_text_tag('underline', {'font': font_details})
        except tk.TclError:
            pass # Pas de sélection

    def change_text_color():
        from tkinter.colorchooser import askcolor
        color = askcolor(parent=sheet_window)[1]
        if color:
            apply_text_tag(f'fg_{color}', {'foreground': color})

    def change_highlight_color():
        from tkinter.colorchooser import askcolor
        color = askcolor(parent=sheet_window)[1]
        if color:
            apply_text_tag(f'bg_{color}', {'background': color})

    def change_font_size(size):
        if size.isdigit() and int(size) > 0:
            font_details = font.Font(font=inventory_text.cget("font"))
            font_details.configure(size=int(size))
            apply_text_tag(f'size_{size}', {'font': font_details})

    def align_text(alignment):
        try:
            start_line = inventory_text.index("sel.first linestart")
            end_line = inventory_text.index("sel.last lineend")
            inventory_text.tag_add(alignment, start_line, end_line)
            inventory_text.tag_configure(alignment, justify=alignment)
        except tk.TclError:
            pass # Pas de sélection

    # --- Widgets de la barre d'outils ---
    ttk.Button(inventory_toolbar, text="B", command=toggle_bold, width=3).pack(side="left", padx=2)
    ttk.Button(inventory_toolbar, text="U", command=toggle_underline, width=3).pack(side="left", padx=2)
    ttk.Button(inventory_toolbar, text="Couleur", command=change_text_color).pack(side="left", padx=2)
    ttk.Button(inventory_toolbar, text="Surligner", command=change_highlight_color).pack(side="left", padx=2)
    
    size_var = tk.StringVar(value="10")
    size_spinbox = ttk.Spinbox(inventory_toolbar, from_=8, to=32, textvariable=size_var, width=4, command=lambda: change_font_size(size_var.get()))
    size_spinbox.pack(side="left", padx=2)

    ttk.Button(inventory_toolbar, text=" Gauche", command=lambda: align_text('left')).pack(side="left", padx=2)
    ttk.Button(inventory_toolbar, text=" Centré", command=lambda: align_text('center')).pack(side="left", padx=2)
    ttk.Button(inventory_toolbar, text=" Droite", command=lambda: align_text('right')).pack(side="left", padx=2)

    # --- Frame de droite (Stats + Boutons) ---
    # NOUVEAU: Conteneur pour le canvas et la scrollbar pour rendre la colonne de droite scrollable
    right_scroll_container = ttk.Frame(paned_window)
    paned_window.add(right_scroll_container, weight=2)

    # Canvas pour le contenu scrollable
    right_canvas = tk.Canvas(right_scroll_container, highlightthickness=0, bg=style.colors.bg)
    right_scrollbar = ttk.Scrollbar(right_scroll_container, orient="vertical", command=right_canvas.yview)
    right_canvas.configure(yscrollcommand=right_scrollbar.set)

    right_scrollbar.pack(side="right", fill="y")
    right_canvas.pack(side="left", fill="both", expand=True)

    # Frame interne qui contiendra les widgets et sera scrollé
    right_frame = ttk.Frame(right_canvas, padding=10)
    right_canvas_window = right_canvas.create_window((0, 0), window=right_frame, anchor="nw")

    # --- Fonctions pour la mise à jour du scroll ---
    def on_right_frame_configure(event):
        """Met à jour la scrollregion quand le contenu interne change de taille."""
        right_canvas.configure(scrollregion=right_canvas.bbox("all"))

    def on_right_canvas_configure(event):
        """Ajuste la largeur du frame interne à celle du canvas."""
        right_canvas.itemconfig(right_canvas_window, width=event.width)

    def _on_sheet_mousewheel(event):
        """Gère le défilement avec la molette de la souris sur le canvas."""
        right_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    right_frame.bind("<Configure>", on_right_frame_configure)
    right_canvas.bind("<Configure>", on_right_canvas_configure)
    right_canvas.bind("<Enter>", lambda e: right_canvas.bind_all("<MouseWheel>", _on_sheet_mousewheel))
    right_canvas.bind("<Leave>", lambda e: right_canvas.unbind_all("<MouseWheel>"))

    # --- NOUVEAU: Tableau des informations générales ---
    info_frame = ttk.Labelframe(right_frame, text="Informations Générales", padding=10)
    info_frame.pack(fill=tk.X, expand=False, side=tk.TOP, pady=(0, 10))
    info_frame.columnconfigure(0, weight=1)

    info_toolbar = ttk.Frame(info_frame)
    info_toolbar.grid(row=0, column=0, sticky='ew', pady=(0, 5))

    info_columns = ("info_key", "info_value")
    info_tree = ttk.Treeview(info_frame, columns=info_columns, show="headings", height=len(INFO_FIELDS_CONFIG))
    info_tree.heading("info_key", text="Information")
    info_tree.heading("info_value", text="Valeur")
    info_tree.column("info_key", width=150, anchor="w")
    info_tree.column("info_value", width=250, anchor="w")
    info_tree.grid(row=1, column=0, sticky='ew')

    def populate_info_tree():
        """(Re)Peuple le tableau des informations en fonction de la visibilité."""
        info_tree.delete(*info_tree.get_children())
        for key, display_name in INFO_FIELDS_CONFIG.items():
            if info_visibility_data.get(key, True): # Afficher par défaut si non défini
                value = info_data.get(key, "")
                info_tree.insert("", tk.END, iid=key, values=(display_name, value))

    def toggle_info_visibility(key):
        """Inverse la visibilité d'un champ d'information."""
        info_visibility_data[key] = not info_visibility_data.get(key, True)
        populate_info_tree()

    def edit_info_cell(event):
        item_id = info_tree.focus()
        if not item_id: return
        new_value = simpledialog.askstring(
            f"Éditer '{INFO_FIELDS_CONFIG[item_id]}'",
            f"Entrez la nouvelle valeur pour {INFO_FIELDS_CONFIG[item_id]}:",
            initialvalue=info_data.get(item_id, ""),
            parent=sheet_window
        )
        if new_value is not None:
            info_data[item_id] = new_value
            info_tree.set(item_id, "info_value", new_value)

    info_tree.bind("<Double-1>", edit_info_cell)

    # Menu pour la visibilité des informations
    info_config_menu = tk.Menu(info_toolbar, tearoff=0)
    for key, display_name in INFO_FIELDS_CONFIG.items():
        var = tk.BooleanVar(value=info_visibility_data.get(key, True))
        info_config_menu.add_checkbutton(
            label=display_name,
            variable=var,
            command=lambda k=key: toggle_info_visibility(k)
        )

    config_button = ttk.Menubutton(info_toolbar, text="⚙️ Infos Visibles", menu=info_config_menu, bootstyle=(SECONDARY, OUTLINE))
    config_button.pack(side="right")

    populate_info_tree()

    # Tableau des statistiques
    stats_frame = ttk.Labelframe(right_frame, text="Statistiques", padding=10)
    stats_frame.pack(fill=tk.BOTH, expand=False, side=tk.TOP) # expand=False pour respecter la hauteur

    columns = ("stat_name", "stat_value")
    stats_tree = ttk.Treeview(stats_frame, columns=columns, show="headings", height=8) # Hauteur réduite de moitié
    stats_tree.heading("stat_name", text="Statistique")
    stats_tree.heading("stat_value", text="Valeur")
    stats_tree.column("stat_name", width=200, anchor="w")
    stats_tree.column("stat_value", width=80, anchor="center")
    stats_tree.pack(fill=tk.BOTH, expand=True)

    for stat in stats_data:
        stats_tree.insert("", tk.END, values=(stat.get('name', ''), stat.get('value', '')))

    # Boutons de gestion des stats
    stats_buttons_frame = ttk.Frame(stats_frame)
    stats_buttons_frame.pack(fill="x", pady=(10, 0))
    ttk.Button(stats_buttons_frame, text="Ajouter", bootstyle=SUCCESS, command=lambda: add_stat(stats_tree)).pack(side="left", padx=5)
    ttk.Button(stats_buttons_frame, text="Modifier", bootstyle=INFO, command=lambda: edit_stat(stats_tree)).pack(side="left", padx=5)
    ttk.Button(stats_buttons_frame, text="Supprimer", bootstyle=DANGER, command=lambda: delete_stat(stats_tree)).pack(side="left", padx=5)
    ttk.Button(stats_buttons_frame, text="Tout Supprimer", bootstyle=(DANGER, OUTLINE), command=lambda: delete_all_stats(stats_tree)).pack(side="right", padx=5)

    # --- NOUVEAU: Tableau des compétences ---
    skills_frame = ttk.Labelframe(right_frame, text="Compétences", padding=10)
    skills_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0), side=tk.TOP)
    # Configuration de la grille pour une meilleure gestion des scrollbars
    skills_frame.rowconfigure(1, weight=1) # Le Treeview s'étend
    skills_frame.rowconfigure(3, weight=0) # Le panneau de description a une hauteur fixe
    skills_frame.columnconfigure(0, weight=1)

    skills_toolbar = ttk.Frame(skills_frame)
    skills_toolbar.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 10))

    skill_columns = {
        "nom": "Nom", "type": "Type", "jet_associe": "Jet Associé", "cout": "Coût",
        "pa": "PA", "description": "Description"
    }
    skills_tree = ttk.Treeview(skills_frame, columns=list(skill_columns.keys()), show="headings", height=10)

    def setup_skills_columns():
        """Affiche ou masque les colonnes en fonction des paramètres."""
        visible_columns = ["nom"] # Le nom est toujours visible
        visibility_settings = app_settings.get("skill_column_visibility", {})
        for col_id, is_visible in visibility_settings.items():
            if is_visible:
                visible_columns.append(col_id)
        skills_tree["displaycolumns"] = visible_columns

    for col_id, col_text in skill_columns.items():
        anchor = "w" if col_id in ["nom", "description"] else "center"
        width = 200 if col_id == "nom" else (300 if col_id == "description" else 100)
        skills_tree.heading(col_id, text=col_text)
        skills_tree.column(col_id, width=width, anchor=anchor, stretch=tk.YES if col_id == "description" else tk.NO)

    setup_skills_columns()

    # Ajout des scrollbars verticale ET horizontale
    skills_v_scrollbar = ttk.Scrollbar(skills_frame, orient="vertical", command=skills_tree.yview)
    skills_h_scrollbar = ttk.Scrollbar(skills_frame, orient="horizontal", command=skills_tree.xview)
    skills_tree.configure(yscrollcommand=skills_v_scrollbar.set, xscrollcommand=skills_h_scrollbar.set)
    skills_tree.grid(row=1, column=0, sticky='nsew')
    skills_v_scrollbar.grid(row=1, column=1, sticky='ns')
    skills_h_scrollbar.grid(row=2, column=0, columnspan=2, sticky='ew')

    # Configuration des couleurs alternées pour les lignes (lignes de séparation)
    striped_bg = lighten_color(style.colors.bg, 0.05)
    skills_tree.tag_configure('oddrow', background=striped_bg)
    skills_tree.tag_configure('evenrow', background=style.colors.bg)

    for i, skill in enumerate(skills_data):
        tag = 'oddrow' if i % 2 == 0 else 'evenrow'
        skills_tree.insert("", tk.END, iid=skill.get('id'), values=[
            skill.get('nom', ''), skill.get('type', ''), skill.get('jet_associe', ''),
            skill.get('cout', ''), skill.get('pa', ''), skill.get('description', '')
        ], tags=(tag,))

    def toggle_column_visibility(col_id):
        """Inverse la visibilité d'une colonne et sauvegarde le paramètre."""
        is_visible = not app_settings["skill_column_visibility"].get(col_id, True)
        app_settings["skill_column_visibility"][col_id] = is_visible
        save_settings(app_settings)
        setup_skills_columns()

    def add_skill():
        new_id = f"skill_{uuid.uuid4().hex[:8]}"
        num_items = len(skills_tree.get_children())
        tag = 'oddrow' if num_items % 2 == 0 else 'evenrow'
        skills_tree.insert("", tk.END, iid=new_id, values=("Nouvelle compétence", "Aucun", "", "", "", ""), tags=(tag,))
        skills_tree.selection_set(new_id)
        skills_tree.focus(new_id)
        skills_tree.see(new_id) # S'assurer que le nouvel item est visible

    def delete_skill():
        selected_item = skills_tree.focus()
        if selected_item:
            if messagebox.askyesno("Confirmation", "Supprimer la compétence sélectionnée ?", parent=sheet_window):
                skills_tree.delete(selected_item)
                # Re-appliquer les tags pour garder l'alternance de couleurs correcte
                for i, item_id in enumerate(skills_tree.get_children()):
                    tag = 'oddrow' if i % 2 == 0 else 'evenrow'
                    skills_tree.item(item_id, tags=(tag,))

    ttk.Button(skills_toolbar, text="➕ Ajouter", command=add_skill, bootstyle=(SUCCESS, OUTLINE)).pack(side="left")
    ttk.Button(skills_toolbar, text="➖ Supprimer", command=delete_skill, bootstyle=(DANGER, OUTLINE)).pack(side="left", padx=5)

    # Remplacement du bouton popup par un Menubutton plus intuitif
    column_config_menu = tk.Menu(skills_toolbar, tearoff=0)
    config_button = ttk.Menubutton(skills_toolbar, text="⚙️ Colonnes", menu=column_config_menu, bootstyle=(SECONDARY, OUTLINE))
    config_button.pack(side="right")

    visibility_settings = app_settings.get("skill_column_visibility", {})
    for col_id, col_text in skill_columns.items():
        if col_id == "nom": continue
        var = tk.BooleanVar(value=visibility_settings.get(col_id, True))
        column_config_menu.add_checkbutton(
            label=col_text,
            variable=var,
            command=lambda c=col_id: toggle_column_visibility(c)
        )

    # --- Panneau de description qui se met à jour à la sélection ---
    desc_frame = ttk.Labelframe(skills_frame, text="Description de la compétence sélectionnée", padding=10)
    desc_frame.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(10, 0))
    desc_frame.rowconfigure(0, weight=1)
    desc_frame.columnconfigure(0, weight=1)

    skill_desc_text = tk.Text(desc_frame, wrap="word", height=5, font=(base_font_family, 10), state="disabled", relief="flat", bg=style.colors.bg, fg=style.colors.fg, highlightthickness=0, borderwidth=0)
    skill_desc_text.grid(row=0, column=0, sticky='nsew')

    desc_scrollbar = ttk.Scrollbar(desc_frame, orient="vertical", command=skill_desc_text.yview)
    desc_scrollbar.grid(row=0, column=1, sticky='ns')
    skill_desc_text.config(yscrollcommand=desc_scrollbar.set)

    def on_skill_select(event):
        """Met à jour le panneau de description quand une compétence est sélectionnée."""
        selected_item = skills_tree.focus()
        description = skills_tree.set(selected_item, 'description') if selected_item else ""
        skill_desc_text.config(state="normal")
        skill_desc_text.delete("1.0", "end")
        skill_desc_text.insert("1.0", description)
        skill_desc_text.config(state="disabled")

    # --- Logique d'édition pour le tableau des compétences ---
    def edit_treeview_cell(event):
        """Gère l'édition des cellules du tableau des compétences par double-clic."""
        item_id = skills_tree.identify_row(event.y)
        column_id = skills_tree.identify_column(event.x)
        if not item_id or not column_id: return

        column_index = int(column_id.replace('#', '')) - 1
        if column_index < 0 or column_index >= len(skills_tree['columns']): return
        column_name = skills_tree['columns'][column_index]

        value = skills_tree.set(item_id, column_name)

        # Utiliser une boîte de dialogue pour les champs textuels pour une meilleure visibilité
        if column_name in ['nom', 'jet_associe', 'cout', 'pa']:
            # Condition spéciale pour le jet associé
            if column_name == 'jet_associe' and skills_tree.set(item_id, 'type') != 'Jet':
                messagebox.showinfo("Information", "Vous ne pouvez définir un jet associé que pour les compétences de type 'Jet'.", parent=sheet_window)
                return

            new_value = simpledialog.askstring(
                f"Éditer '{skill_columns[column_name]}'",
                f"Entrez la nouvelle valeur pour {skill_columns[column_name]}:",
                initialvalue=value,
                parent=sheet_window
            )
            if new_value is not None: # askstring retourne None si on annule
                skills_tree.set(item_id, column_name, new_value)

        # Utiliser une popup plus grande pour la description
        elif column_name == 'description':
            popup = ttk.Toplevel(sheet_window)
            popup.title("Éditer la description")
            popup.transient(sheet_window)
            popup.grab_set()
            popup.resizable(True, True)

            editor_frame = ttk.Frame(popup, padding=10)
            editor_frame.pack(fill="both", expand=True)
            editor_frame.rowconfigure(0, weight=1)
            editor_frame.columnconfigure(0, weight=1)

            text_editor = tk.Text(editor_frame, wrap="word", width=50, height=10, font=(base_font_family, 10), undo=True)
            text_editor.grid(row=0, column=0, columnspan=2, sticky="nsew")
            text_editor.insert("1.0", value)
            text_editor.focus_set()

            def save_description():
                new_value = text_editor.get("1.0", "end-1c") # -1c pour enlever le newline final
                skills_tree.set(item_id, column_name, new_value)
                popup.destroy()

            button_frame = ttk.Frame(editor_frame)
            button_frame.grid(row=1, column=0, columnspan=2, pady=(10, 0), sticky="e")
            ttk.Button(button_frame, text="Annuler", command=popup.destroy, bootstyle=SECONDARY).pack(side="right", padx=(10, 0))
            ttk.Button(button_frame, text="💾 Sauvegarder", command=save_description, bootstyle=SUCCESS).pack(side="right")

    skills_tree.bind("<Double-1>", edit_treeview_cell)
    skills_tree.bind("<<TreeviewSelect>>", on_skill_select)
    skills_tree.bind("<Button-3>", show_skill_type_menu)

    # --- Boutons d'action en bas ---
    action_buttons_frame = ttk.Frame(right_frame)
    action_buttons_frame.pack(fill="x", pady=(20, 0), side="bottom")
    
    def save_character_sheet_data(close_after=False):
        """Rassemble et sauvegarde toutes les données de la fiche personnage."""
        # NOUVEAU: Récupérer les informations générales
        new_info = {}
        for key in INFO_FIELDS_CONFIG.keys():
            # On sauvegarde la valeur même si elle est cachée
            new_info[key] = info_data.get(key, "")
        character_data['info'] = new_info
        character_data['info_visibility'] = info_visibility_data

        # Récupérer les stats
        new_stats = []
        for item_id in stats_tree.get_children():
            item = stats_tree.item(item_id)
            new_stats.append({"name": item['values'][0], "value": item['values'][1]})
        
        # Récupérer les compétences
        new_skills = []
        for item_id in skills_tree.get_children():
            skill_data = {
                'id': item_id,
                'nom': skills_tree.set(item_id, 'nom'),
                'type': skills_tree.set(item_id, 'type'),
                'jet_associe': skills_tree.set(item_id, 'jet_associe'),
                'cout': skills_tree.set(item_id, 'cout'),
                'pa': skills_tree.set(item_id, 'pa'),
                'description': skills_tree.set(item_id, 'description')
            }
            new_skills.append(skill_data)
        
        # Gérer la suppression de l'ancienne image si nécessaire
        path_to_delete = image_path_to_delete_on_save.get()
        if path_to_delete:
            full_path_to_delete = os.path.join(os.path.dirname(os.path.abspath(__file__)), path_to_delete)
            if os.path.exists(full_path_to_delete):
                try:
                    os.remove(full_path_to_delete)
                    image_path_to_delete_on_save.set("") # Réinitialiser pour éviter une nouvelle suppression
                except OSError as e:
                    print(f"Erreur lors de la suppression de l'ancienne image {full_path_to_delete}: {e}")
        
        # Récupérer le contenu et les tags de l'inventaire
        new_inventory_content = inventory_text.get("1.0", tk.END).strip()
        new_inventory_tags = []
        for tag_name in inventory_text.tag_names():
            if tag_name == "sel": continue
            ranges = []
            # La méthode tag_ranges retourne un tuple plat (start1, end1, start2, end2, ...).
            # On doit donc l'itérer par paires pour obtenir les plages (start, end).
            tag_ranges_flat = inventory_text.tag_ranges(tag_name)
            it = iter(tag_ranges_flat)
            for start in it:
                end = next(it)
                ranges.append((str(start), str(end)))
            if ranges:
                # Récupérer les propriétés de la police et les sauvegarder dans un format valide.
                # L'ancien format sauvegardait 0 ou 1 pour 'underline', ce qui causait une erreur au chargement.
                font_config = font.Font(font=inventory_text.tag_cget(tag_name, 'font')).actual()
                font_list = [
                    font_config.get('family'),
                    font_config.get('size'),
                    font_config.get('weight', 'normal'),
                    font_config.get('slant', 'roman')
                ]
                if font_config.get('underline'): font_list.append('underline')
                if font_config.get('overstrike'): font_list.append('overstrike')

                new_inventory_tags.append({
                    'name': tag_name,
                    'ranges': ranges,
                    'config': { 'font': font_list, 'foreground': inventory_text.tag_cget(tag_name, 'foreground'), 'background': inventory_text.tag_cget(tag_name, 'background'), 'justify': inventory_text.tag_cget(tag_name, 'justify') }
                })

        # Mettre à jour le dictionnaire du personnage
        character_data['stats'] = new_stats
        character_data['skills'] = new_skills
        character_data['inventory'] = new_inventory_content
        character_data['inventory_tags'] = new_inventory_tags
        
        save_character_data(character_data)
        update_character_list_display() # Rafraîchir la liste au cas où le nom aurait changé

        if close_after:
            sheet_window.destroy()
        else:
            # Afficher une confirmation visuelle
            save_button.config(bootstyle=SUCCESS, text="💾 Sauvegardé !")
            save_button.after(2000, lambda: save_button.config(bootstyle=PRIMARY, text="💾 Sauvegarder"))

    def save_and_close():
        save_character_sheet_data(close_after=True)

    save_button = ttk.Button(action_buttons_frame, text="💾 Sauvegarder", bootstyle=PRIMARY, command=save_character_sheet_data)
    save_button.pack(side="right", padx=5)
    ttk.Button(action_buttons_frame, text="💾 Sauvegarder et Fermer", bootstyle=SUCCESS, command=save_and_close).pack(side="right", padx=5)

class StatEditorPopup(simpledialog.Dialog):
    """Popup personnalisé pour ajouter/éditer une statistique."""
    def __init__(self, parent, title=None, initial_name="", initial_value=""):
        self.initial_name = initial_name
        self.initial_value = initial_value
        super().__init__(parent, title=title)

    def body(self, master):
        ttk.Label(master, text="Statistique:").grid(row=0, sticky="w")
        ttk.Label(master, text="Valeur:").grid(row=1, sticky="w")

        self.name_entry = ttk.Entry(master, width=30)
        self.value_entry = ttk.Entry(master, width=10)

        self.name_entry.insert(0, self.initial_name)
        self.value_entry.insert(0, self.initial_value)

        self.name_entry.grid(row=0, column=1, padx=5, pady=5)
        self.value_entry.grid(row=1, column=1, padx=5, pady=5)
        return self.name_entry # initial focus

    def apply(self):
        self.result = (self.name_entry.get(), self.value_entry.get())

# --- Fonctions utilitaires pour la gestion des stats ---
def add_stat(tree):
    popup = StatEditorPopup(tree.winfo_toplevel(), title="Nouvelle Statistique")
    if popup.result:
        name, value = popup.result
        if name.strip():
            tree.insert("", tk.END, values=(name.strip(), value.strip()))

def edit_stat(tree):
    selected_item = tree.focus()
    if not selected_item:
        messagebox.showwarning("Aucune sélection", "Veuillez sélectionner une statistique à modifier.", parent=tree.winfo_toplevel())
        return
    
    item = tree.item(selected_item)
    old_name, old_value = item['values']

    popup = StatEditorPopup(tree.winfo_toplevel(), title="Modifier la Statistique", initial_name=old_name, initial_value=old_value)
    if popup.result:
        new_name, new_value = popup.result
        if new_name.strip():
            tree.item(selected_item, values=(new_name.strip(), new_value.strip()))

def delete_stat(tree):
    selected_item = tree.focus()
    if not selected_item:
        messagebox.showwarning("Aucune sélection", "Veuillez sélectionner une statistique à supprimer.", parent=tree.winfo_toplevel())
        return
    if messagebox.askyesno("Confirmation", "Voulez-vous vraiment supprimer cette statistique ?", parent=tree.winfo_toplevel()):
        tree.delete(selected_item)

def delete_all_stats(tree):
    if messagebox.askyesno("Confirmation", "Voulez-vous vraiment supprimer TOUTES les statistiques de ce personnage ?\nCette action est irréversible.", parent=tree.winfo_toplevel(), icon='warning'):
        for item in tree.get_children():
            tree.delete(item)


def edit_character(char_id, char_type):
    """Ouvre la fenêtre d'édition pour un personnage spécifique."""
    open_character_sheet(char_id, char_type)



def rename_character(char_id, char_type):
    """Renomme un personnage."""
    char_list = all_characters.get(char_type, [])
    char_to_rename = next((c for c in char_list if c.get('id') == char_id), None)
    if not char_to_rename: return

    new_name = simpledialog.askstring("Renommer", "Entrez le nouveau nom :", initialvalue=char_to_rename.get('name'), parent=root)
    if new_name and new_name.strip():
        char_to_rename['name'] = new_name.strip()
        save_character_data(char_to_rename)
        update_character_list_display() # Rafraîchir la liste

def delete_character(char_id, char_type):
    """Supprime un personnage après confirmation, ainsi que son image associée."""
    char_to_delete_data = next((c for c in all_characters.get(char_type, []) if c.get('id') == char_id), None)
    if not char_to_delete_data: return

    if messagebox.askyesno("Confirmation", f"Voulez-vous vraiment supprimer '{char_to_delete_data.get('name')}' ?\nCette action est irréversible."):
        card_to_delete = character_card_widgets.get(char_id)

        def perform_deletion():
            char_list = all_characters.get(char_type, [])
            char_to_delete = next((c for c in char_list if c.get('id') == char_id), None)
            if char_to_delete:
                image_path = char_to_delete.get('image_path')
                if image_path:
                    full_image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), image_path)
                    if os.path.exists(full_image_path): os.remove(full_image_path)
                
                # Supprimer le fichier JSON du personnage
                char_file_path = os.path.join(CHAR_DATA_DIR, f"{char_id}.json")
                if os.path.exists(char_file_path): os.remove(char_file_path)
                char_list.remove(char_to_delete)


                if char_id in character_card_widgets:
                    del character_card_widgets[char_id]
                messagebox.showinfo("Succès", f"'{char_to_delete.get('name')}' a été supprimé.")

        if card_to_delete and card_to_delete.winfo_exists():
            animate_card_action(card_to_delete, "danger", on_finish=perform_deletion, is_disappearing=True)
        else:
            perform_deletion()
            update_character_list_display()

def duplicate_character(char_id, char_type):
    """Crée une copie d'un personnage."""
    original_char = next((c for c in all_characters.get(char_type, []) if c.get('id') == char_id), None)
    if not original_char: return

    card_to_animate = character_card_widgets.get(char_id)

    def perform_duplication():
        new_char = original_char.copy()
        new_char['id'] = f"char_{uuid.uuid4().hex[:8]}"
        new_char['name'] = f"{original_char.get('name', 'Sans nom')} (Copie)"
        new_char['creation_timestamp'] = datetime.now().isoformat(timespec="seconds")
        all_characters.get(char_type, []).append(new_char) # Ajouter à la liste en mémoire
        save_character_data(new_char) # Sauvegarder le nouveau fichier
        update_character_list_display() # Rafraîchir l'UI

    if card_to_animate and card_to_animate.winfo_exists():
        animate_card_action(card_to_animate, "success", on_finish=perform_duplication, is_disappearing=False)
    else:
        perform_duplication()

def transfer_character(char_id, char_type):
    """Déplace un personnage de PJ à PNJ ou inversement."""
    card_to_transfer = character_card_widgets.get(char_id)

    def perform_transfer():
        source_list = all_characters.get(char_type, [])
        target_type = "pnjs" if char_type == "pjs" else "pjs"
        target_list = all_characters.get(target_type, [])
        char_to_transfer_data = next((c for c in source_list if c.get('id') == char_id), None)
        if char_to_transfer_data:
            source_list.remove(char_to_transfer_data)
            char_to_transfer_data['char_type'] = target_type
            target_list.append(char_to_transfer_data)
            save_character_data(char_to_transfer_data) # Sauvegarder le fichier avec le nouveau type
            if char_id in character_card_widgets:
                del character_card_widgets[char_id]

    if card_to_transfer and card_to_transfer.winfo_exists():
        animate_card_action(card_to_transfer, "info", on_finish=perform_transfer, is_disappearing=True)
    else:
        perform_transfer()
        update_character_list_display()

def convert_tkinter_tags_to_html(text_content, tags_data):
    """
    Convertit un texte brut et une liste de tags de style Tkinter en une chaîne HTML simple.
    Gère le gras, le souligné et la couleur du texte pour fpdf2.
    """
    if not tags_data or not text_content:
        return text_content.replace('\n', '<br>')

    lines = text_content.split('\n')
    def to_offset(tk_index_str):
        try:
            line, col = map(int, tk_index_str.split('.'))
            # L'offset est la somme des longueurs des lignes précédentes (+1 pour chaque \n) + la colonne sur la ligne actuelle.
            # line est 1-based, donc lines[:line-1] est correct.
            offset = sum(len(l) + 1 for l in lines[:line - 1])
            offset += col
            return offset
        except (ValueError, IndexError):
            return -1 # Gérer les indices invalides

    insertions = []
    for tag_info in tags_data:
        config = tag_info.get('config', {})
        if not config: continue

        opening_tags, closing_tags = "", ""

        font_config = config.get('font')
        if isinstance(font_config, (list, tuple)):
            if 'bold' in font_config:
                opening_tags += '<b>'
                closing_tags = '</b>' + closing_tags
            if 'underline' in font_config:
                opening_tags += '<u>'
                closing_tags = '</u>' + closing_tags
        
        color = config.get('foreground')
        if color and color.lower() != style.colors.fg.lower():
            opening_tags += f'<font color="{color}">'
            closing_tags = '</font>' + closing_tags

        if not opening_tags: continue

        for start, end in tag_info.get('ranges', []):
            start_offset, end_offset = to_offset(start), to_offset(end)
            if start_offset != -1 and end_offset != -1 and start_offset < end_offset:
                insertions.append((start_offset, opening_tags))
                insertions.append((end_offset, closing_tags))

    insertions.sort(key=lambda x: (x[0], x[1].startswith('</')), reverse=True)
    html_list = list(text_content)
    for offset, tag_html in insertions:
        if offset <= len(html_list): html_list.insert(offset, tag_html)

    final_html = "".join(html_list).replace('\n', '<br>')
    return f'<font face="Helvetica" size="10" color="{style.colors.fg}">{final_html}</font>'

def export_character_to_pdf(char_id, char_type):
    """Exporte la fiche d'un personnage en PDF en respectant le style de l'application."""
    if not FPDF:
        messagebox.showerror("Module Manquant", "Le module 'fpdf2' est requis pour exporter en PDF.\n\nVeuillez l'installer avec : pip install fpdf2")
        return

    char_data = next((c for c in all_characters.get(char_type, []) if c.get('id') == char_id), None)
    if not char_data:
        messagebox.showerror("Erreur", "Personnage non trouvé.")
        return

    default_filename = f"{char_data.get('name', 'personnage').replace(' ', '_')}.pdf"
    save_path = filedialog.asksaveasfilename(
        initialfile=default_filename,
        defaultextension=".pdf",
        filetypes=[("Fichiers PDF", "*.pdf"), ("Tous les fichiers", "*.*")],
        title="Enregistrer la fiche personnage en PDF"
    )

    if not save_path:
        return

    try:
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # --- Polices et couleurs ---
        try:
            pdf.add_font(base_font_family, "", uni=True)
            pdf.set_font(base_font_family, size=12)
        except Exception as font_error:
            # Cette erreur se produit si la police système (ex: 'Segoe UI') n'est pas trouvée
            # ou si son fichier .ttf n'est pas fourni. On se rabat sur une police standard.
            print(f"Avertissement : Police '{base_font_family}' non trouvée ou impossible à charger ({font_error}). Utilisation de Helvetica.")
            pdf.set_font("Helvetica", size=12)

        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

        primary_rgb = hex_to_rgb(style.colors.primary)
        secondary_rgb = hex_to_rgb(style.colors.secondary)
        bg_rgb = hex_to_rgb(style.colors.bg)
        fg_rgb = hex_to_rgb(style.colors.fg)

        pdf.set_text_color(*fg_rgb)
        pdf.set_fill_color(*bg_rgb)
        pdf.rect(0, 0, 210, 297, 'F')

        # --- Titre ---
        pdf.set_font_size(24)
        pdf.set_text_color(*primary_rgb)
        pdf.cell(0, 15, char_data.get('name', 'N/A'), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*fg_rgb)
        pdf.ln(5)

        # --- Image ---
        y_before_content = pdf.get_y()
        image_path = char_data.get('image_path', '')
        if image_path:
            full_image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), image_path)
            if os.path.exists(full_image_path):
                try:
                    # Pour les GIFs, on intègre la première image (les PDF ne supportent pas les animations)
                    if image_path.lower().endswith('.gif') and Image:
                        with Image.open(full_image_path) as img:
                            from io import BytesIO
                            buffer = BytesIO()
                            img.seek(0)
                            img.save(buffer, format="PNG")
                            buffer.seek(0)
                            pdf.image(buffer, x=15, y=pdf.get_y(), w=80)
                    else:
                        pdf.image(full_image_path, x=15, y=pdf.get_y(), w=80)
                except Exception as e:
                    print(f"Erreur d'intégration de l'image au PDF : {e}")

        # --- Statistiques (colonne de droite) ---
        pdf.set_xy(105, y_before_content)
        stats = char_data.get('stats', [])
        if stats:
            pdf.set_font_size(14)
            pdf.set_text_color(*primary_rgb)
            pdf.cell(0, 10, "Statistiques", new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(105)
            pdf.set_text_color(*fg_rgb)
            pdf.set_font(style="B", size=11)
            pdf.set_fill_color(*secondary_rgb)
            pdf.cell(60, 8, "Statistique", border=1, align='C', fill=True)
            pdf.cell(25, 8, "Valeur", border=1, align='C', fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(style="", size=10)
            for stat in stats:
                pdf.set_x(105)
                pdf.cell(60, 7, stat.get('name', ''), border=1)
                pdf.cell(25, 7, str(stat.get('value', '')), border=1, align='C', new_x="LMARGIN", new_y="NEXT")

        # --- Inventaire (avec mise en forme) ---
        inventory_content = char_data.get('inventory', '')
        inventory_tags = char_data.get('inventory_tags', [])
        if inventory_content:
            # Positionner l'inventaire sous l'image et les stats
            y_after_image = y_before_content + 85  # Heuristique pour la hauteur de l'image
            y_after_stats = pdf.get_y()
            pdf.set_y(max(y_after_image, y_after_stats) + 5)
            
            pdf.set_x(15)
            pdf.set_font_size(14)
            pdf.set_text_color(*primary_rgb)
            pdf.cell(0, 10, "Inventaire", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*fg_rgb)
            
            # Convertir et écrire le contenu de l'inventaire en HTML
            html_inventory = convert_tkinter_tags_to_html(inventory_content, inventory_tags)
            # Utiliser write_html pour interpréter le formatage
            pdf.write_html(html_inventory)

        # --- Compétences ---
        skills = char_data.get('skills', [])
        if skills:
            # Sauter à une nouvelle page si le contenu est important
            if pdf.get_y() > 150:
                pdf.add_page()
            else:
                pdf.ln(10)

            pdf.set_x(15)
            pdf.set_font_size(14)
            pdf.set_text_color(*primary_rgb)
            pdf.cell(0, 10, "Compétences", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*fg_rgb)

            pdf.set_font(style="B", size=10)
            pdf.set_fill_color(*secondary_rgb)
            pdf.cell(40, 7, "Compétence", border=1, fill=True)
            pdf.cell(25, 7, "Type", border=1, fill=True)
            pdf.cell(15, 7, "Coût", border=1, fill=True)
            pdf.cell(15, 7, "PA", border=1, fill=True)
            pdf.cell(85, 7, "Description", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(style="", size=9)
            for skill in skills:
                pdf.multi_cell(180, 7, f"**{skill.get('nom', '')}** ({skill.get('type', '')}, Coût: {skill.get('cout', 'N/A')}, PA: {skill.get('pa', 'N/A')})\n{skill.get('description', '')}", border=1, markdown=True, new_x="LMARGIN", new_y="NEXT")

        # --- Sauvegarde ---
        pdf.output(save_path)
        messagebox.showinfo("Exportation réussie", f"La fiche a été exportée avec succès vers :\n{save_path}")

    except Exception as e:
        messagebox.showerror("Erreur d'exportation", f"Une erreur est survenue lors de la création du PDF :\n{e}")

def on_create_character():
    """Ouvre la fenêtre de création d'une nouvelle fiche de personnage."""
    popup = ttk.Toplevel(root)
    popup.title("Créer une nouvelle fiche")
    popup.transient(root)
    popup.grab_set()
    popup.resizable(False, False)

    main_frame = ttk.Frame(popup, padding=20)
    main_frame.pack(fill="both", expand=True)

    # Variables pour stocker les données
    name_var = tk.StringVar()
    image_source_var = tk.StringVar()

    # --- Section Nom ---
    name_frame = ttk.Frame(main_frame)
    name_frame.pack(fill='x', pady=(0, 20))
    ttk.Label(name_frame, text="Nom du personnage :", font=(base_font_family, 10, "bold")).pack(side="left", padx=(0, 10))
    ttk.Entry(name_frame, textvariable=name_var, width=40).pack(side="left", expand=True, fill='x')

    # --- Section Image ---
    image_frame = ttk.Frame(main_frame)
    image_frame.pack(fill='x', pady=(0, 20))
    
    image_preview = ttk.Label(image_frame, text="🖼️\nAucune image", font=(base_font_family, 12), bootstyle=SECONDARY, padding=20, width=20, anchor="center", relief="solid", borderwidth=1)
    image_preview.pack(side="left", padx=(0, 20))

    # Frame pour les boutons d'image
    image_buttons_frame = ttk.Frame(image_frame)
    image_buttons_frame.pack(anchor="center")

    ttk.Button(image_buttons_frame, text="Choisir depuis le PC...", command=lambda: select_local_image()).pack(pady=2, fill='x')
    ttk.Button(image_buttons_frame, text="Importer depuis une URL...", command=lambda: import_from_url()).pack(pady=2, fill='x')

    def select_local_image():
        """Ouvre une boîte de dialogue pour sélectionner un fichier image."""
        file_path = filedialog.askopenfilename(
            title="Sélectionner une image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Tous les fichiers", "*.*")],
            parent=popup
        )
        if file_path:
            image_source_var.set(file_path)
            # Mettre à jour l'aperçu
            try:
                img = Image.open(file_path)
                img.thumbnail((128, 128))
                photo = ImageTk.PhotoImage(img)
                image_preview.config(image=photo, text="")
                image_preview.image = photo # Garder la référence
            except Exception as e:
                messagebox.showerror("Erreur d'image", f"Impossible de charger l'image : {e}", parent=popup)
                image_source_var.set("")

    def import_from_url():
        """Demande une URL et tente de télécharger l'image pour l'aperçu."""
        if not requests:
            messagebox.showerror("Module manquant", "Le module 'requests' est nécessaire pour télécharger depuis une URL.\n\nVeuillez l'installer avec : pip install requests", parent=popup)
            return

        url = simpledialog.askstring(
            "Importer depuis une URL",
            "Collez le lien direct de l'image.\n(Sources supportées : Discord, Imgur, Pinterest, etc.)",
            parent=popup
        )
        if url and url.strip():
            url = url.strip()
            image_source_var.set(url)
            try:
                # Ajouter un User-Agent pour éviter d'être bloqué par certains sites
                headers = {'User-Agent': 'Mozilla/5.0'}
                # Ne pas utiliser stream=True si on lit tout le contenu d'un coup
                response = requests.get(url, timeout=10, headers=headers)
                response.raise_for_status()
                
                image_content = None
                content_type = response.headers.get('Content-Type', '').lower()

                if content_type.startswith('image/'):
                    # C'est un lien direct vers une image
                    image_content = response.content
                elif content_type.startswith('text/html'):
                    # C'est une page web (ex: Pinterest), on cherche le lien de l'image
                    print("Page HTML détectée. Recherche de la balise 'og:image'...")
                    # Utiliser une regex pour trouver la balise meta og:image
                    match = re.search(r'<meta\s+property="og:image"\s+content="(.*?)"', response.text)
                    if match:
                        image_url = match.group(1).replace('&amp;', '&') # Remplacer les entités HTML
                        print(f"Image trouvée : {image_url}")
                        # Mettre à jour la source pour la sauvegarde et le téléchargement
                        image_source_var.set(image_url) # Met à jour la variable pour la sauvegarde finale
                        # Télécharger l'image réelle
                        image_response = requests.get(image_url, timeout=10, headers=headers)
                        image_response.raise_for_status()
                        image_content = image_response.content
                    else:
                        raise ValueError("Impossible de trouver un lien d'image direct (balise og:image) sur la page.")
                else:
                    raise ValueError(
                        f"L'URL ne pointe pas vers une image ou une page web reconnue. Type de contenu reçu : '{content_type}'."
                    )

                if image_content:
                    from io import BytesIO
                    image_data = BytesIO(image_content)
                    
                    img = Image.open(image_data)
                    img.thumbnail((256, 256)) # Taille augmentée pour l'aperçu
                    photo = ImageTk.PhotoImage(img)
                    image_preview.config(image=photo, text="")
                    image_preview.image = photo
                else:
                    raise ValueError("Aucun contenu d'image n'a pu être récupéré.")
            except Exception as e:
                messagebox.showerror("Erreur de téléchargement", f"Impossible de charger l'image depuis l'URL.\n\nVérifiez le lien et votre connexion.\n\nErreur: {e}", parent=popup)
                image_source_var.set("")

    def on_save():
        """Sauvegarde le nouveau personnage."""
        name = name_var.get().strip()
        if not name:
            messagebox.showwarning("Nom manquant", "Veuillez entrer un nom pour le personnage.", parent=popup)
            return

        final_image_path = ""
        source = image_source_var.get()
        if source:
            img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "character_images")
            os.makedirs(img_dir, exist_ok=True)

            try:
                if source.startswith(('http://', 'https://')):
                    # Télécharger depuis l'URL
                    response = requests.get(source, stream=True, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                    response.raise_for_status()
                    
                    content_type = response.headers.get('content-type', '').lower()
                    ext = '.jpg' # Par défaut
                    if 'png' in content_type: ext = '.png'
                    elif 'gif' in content_type: ext = '.gif'
                    elif 'jpeg' in content_type: ext = '.jpg'
                    
                    unique_filename = f"{uuid.uuid4().hex[:8]}{ext}"
                    save_path = os.path.join(img_dir, unique_filename)
                    
                    with open(save_path, 'wb') as f:
                        shutil.copyfileobj(response.raw, f)
                    final_image_path = os.path.join("data", "character_images", unique_filename)
                else:
                    # Copier depuis un fichier local
                    ext = os.path.splitext(source)[1]
                    if not ext: ext = ".jpg" # Fallback si pas d'extension
                    unique_filename = f"{uuid.uuid4().hex[:8]}{ext}"
                    save_path = os.path.join(img_dir, unique_filename)
                    shutil.copy(source, save_path)
                    final_image_path = os.path.join("data", "character_images", unique_filename)
            except Exception as e:
                messagebox.showerror("Erreur de sauvegarde d'image", f"Impossible de traiter l'image :\n{e}", parent=popup)
                return # Arrêter la sauvegarde si l'image échoue

        char_type = character_type_var.get()
        new_char = {
            'id': f"char_{uuid.uuid4().hex[:8]}",
            'name': name,
            'char_type': char_type,
            'creation_timestamp': datetime.now().isoformat(timespec="seconds"),
            'image_path': final_image_path.replace("\\", "/"),
            # Initialiser les nouvelles structures de données
            'info': {
                "char_name": name, # Le nom du personnage est initialisé avec le nom de la fiche
                "nickname": "", "age": "", "race": "", "gender": "", "sexuality": "",
                "rank": "", "level": 1, "xp": 0, "money": "", "height": ""
            },
            'info_visibility': {k: True for k in INFO_FIELDS_CONFIG.keys()},
            'stats': [],
            'skills': [],
            'inventory': "",
            'inventory_tags': []
        }

        all_characters[char_type].append(new_char)
        save_character_data(new_char)
        update_character_list_display()
        popup.destroy()

    # --- Boutons d'action ---
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x', pady=(20, 0))
    ttk.Button(button_frame, text="Annuler", command=popup.destroy, bootstyle=SECONDARY).pack(side="right", padx=(10, 0))
    ttk.Button(button_frame, text="💾 Sauvegarder", command=on_save, bootstyle=SUCCESS).pack(side="right")

    # Centrer la popup
    popup.update_idletasks()
    root_x, root_y, root_width, root_height = root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height()
    popup_width, popup_height = popup.winfo_width(), popup.winfo_height()
    center_x = int(root_x + (root_width / 2) - (popup_width / 2))
    center_y = int(root_y + (root_height / 2) - (popup_height / 2))
    popup.geometry(f"+{center_x}+{center_y}")

def update_character_list_display(*args):
    """Filtre, trie et affiche la liste des personnages dans la Listbox."""
    # --- Nettoyage de l'affichage précédent ---
    for widget in character_list_frame.winfo_children():
        widget.destroy()
    character_card_widgets.clear()

    char_type = character_type_var.get()
    search_term = search_var.get().lower()
    sort_mode = sort_var.get()

    character_list = all_characters.get(char_type, [])

    # --- 1. Filtrage par recherche ---
    if search_term:
        filtered_list = [char for char in character_list if search_term in char.get('name', '').lower()]
    else:
        filtered_list = character_list

    # --- 2. Tri ---
    if sort_mode == "Nom (A-Z)":
        sorted_list = sorted(filtered_list, key=lambda x: x.get('name', ''))
    elif sort_mode == "Nom (Z-A)":
        sorted_list = sorted(filtered_list, key=lambda x: x.get('name', ''), reverse=True)
    elif sort_mode == "Date de création":
        sorted_list = sorted(filtered_list, key=lambda x: x.get('creation_timestamp', ''))
    else:  # "Ordre personnalisé" (défaut)
        sorted_list = filtered_list # On respecte l'ordre actuel du fichier

    # --- 3. Affichage des cartes ---
    if not sorted_list:
        ttk.Label(character_list_frame, text="Aucun personnage trouvé.", bootstyle=SECONDARY).pack(pady=20)
        return

    for char_data in sorted_list:
        card = ttk.Frame(character_list_frame, bootstyle="secondary", padding=10)
        card.pack(fill='x', padx=10, pady=5)
        character_card_widgets[char_data['id']] = card

        # --- Affichage de l'image du personnage ---
        img_label = ttk.Label(card, text="🖼️", font=(base_font_family, 48), width=4, anchor="center", background=style.colors.bg)
        img_label.pack(side="left", padx=(0, 15))

        image_path = char_data.get('image_path', '')
        full_image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), image_path)
        is_gif = image_path.lower().endswith('.gif')

        if image_path and os.path.exists(full_image_path) and Image and ImageTk:
            if is_gif:
                try:
                    # Pour les GIFs, on affiche la première image et on prépare l'animation au survol
                    with Image.open(full_image_path) as gif_image:
                        static_frame = gif_image.copy()
                        static_frame.thumbnail((120, 120)) # Taille augmentée
                        static_photo = ImageTk.PhotoImage(static_frame)
                    img_label.config(image=static_photo, text="")
                    img_label.image = static_photo # Garder la référence
                    img_label.static_image = static_photo # Référence pour l'arrêt de l'animation
                    img_label.gif_path = full_image_path # Chemin pour démarrer l'animation
                except Exception as e:
                    print(f"Impossible de charger la miniature du GIF {full_image_path}: {e}")
                    img_label.config(text="⚠️", font=(base_font_family, 48))
            else:
                # Logique existante pour les images statiques
                try:
                    with Image.open(full_image_path) as img:
                        img.thumbnail((120, 120)) # Taille augmentée
                        photo = ImageTk.PhotoImage(img)
                        img_label.config(image=photo, text="")
                        img_label.image = photo
                except Exception as e:
                    print(f"Impossible de charger l'image {full_image_path}: {e}")
                    img_label.config(text="⚠️", font=(base_font_family, 48))

        name_label = ttk.Label(card, text=char_data.get('name', 'N/A'), font=(base_font_family, 14, "bold"))
        name_label.pack(side="left", anchor="w")

        # Lier les événements à la carte et à ses composants pour une meilleure expérience
        widgets_to_bind = [card, img_label, name_label]
        for widget in widgets_to_bind:
            widget.bind("<Double-1>", lambda e, c=char_data, ct=char_type: edit_character(c.get('id'), ct))
            widget.bind("<Button-3>", lambda e, c=char_data, ct=char_type: show_character_context_menu(e, c, ct))
            widget.bind("<ButtonPress-1>", lambda e, card_widget=card, cd=char_data, ct=char_type: drag_start(e, card_widget, cd, ct))
            # Ajout des liaisons pour l'animation du GIF
            if is_gif and Image and ImageTk:
                widget.bind("<Enter>", lambda e, lbl=img_label: start_gif_animation(lbl))
                widget.bind("<Leave>", lambda e, lbl=img_label: stop_gif_animation(lbl))

# --- Widgets de la page Personnages ---
ttk.Button(frame_persos, text="⬅ Menu principal", bootstyle=SECONDARY, command=retour_menu_principal).pack(side="top", anchor="nw", padx=10, pady=10)

persos_title = ttk.Label(frame_persos, text="👤 Fiches Personnages", font=(base_font_family, 18, "bold"), bootstyle=PRIMARY)
persos_title.pack(pady=20)
register_scalable_widget(persos_title, 18)

# --- Sélecteur PJ/PNJ ---
char_type_frame = ttk.Frame(frame_persos)
char_type_frame.pack(pady=(0, 20))
character_type_var = tk.StringVar(value="pjs")
character_type_var.trace_add("write", update_character_list_display)

ttk.Radiobutton(char_type_frame, text="Personnages Joueurs (PJ)", variable=character_type_var, value="pjs", bootstyle="toolbutton").pack(side="left", padx=10)
ttk.Radiobutton(char_type_frame, text="Personnages Non-Joueurs (PNJ)", variable=character_type_var, value="pnjs", bootstyle="toolbutton").pack(side="left", padx=10)

# --- Contrôles (Recherche et Tri) ---
controls_frame = ttk.Frame(frame_persos)
controls_frame.pack(fill='x', padx=40, pady=10)
controls_frame.columnconfigure(1, weight=1)

ttk.Label(controls_frame, text="Rechercher :").grid(row=0, column=0, padx=(0, 10), sticky='w')
search_var = tk.StringVar()
search_var.trace_add("write", update_character_list_display)
search_entry = ttk.Entry(controls_frame, textvariable=search_var)
search_entry.grid(row=0, column=1, sticky='ew')

ttk.Label(controls_frame, text="Trier par :").grid(row=0, column=2, padx=(20, 10), sticky='w')
sort_options = ["Ordre personnalisé", "Nom (A-Z)", "Nom (Z-A)", "Date de création"]
sort_var = tk.StringVar(value=sort_options[0]) # Ordre personnalisé par défaut
sort_combo = ttk.Combobox(controls_frame, textvariable=sort_var, values=sort_options, state="readonly", width=18)
sort_combo.bind("<<ComboboxSelected>>", update_character_list_display)
sort_combo.grid(row=0, column=3, sticky='e')

# --- Liste des personnages ---
list_canvas_container = ttk.Frame(frame_persos)
list_canvas_container.pack(pady=10, padx=40, fill="both", expand=True)

char_canvas = tk.Canvas(list_canvas_container, highlightthickness=0, bg=style.colors.bg)
char_scrollbar = ttk.Scrollbar(list_canvas_container, orient="vertical", command=char_canvas.yview)
char_canvas.configure(yscrollcommand=char_scrollbar.set)

char_scrollbar.pack(side="right", fill="y")
char_canvas.pack(side="left", fill="both", expand=True)

# Frame interne qui contiendra les cartes de personnages
character_list_frame = ttk.Frame(char_canvas)
canvas_window = char_canvas.create_window((0, 0), window=character_list_frame, anchor="nw")

character_list_frame.bind("<Configure>", lambda e: char_canvas.configure(scrollregion=char_canvas.bbox("all")))
char_canvas.bind("<Configure>", lambda e: char_canvas.itemconfig(canvas_window, width=e.width))

# --- Bouton de création ---
create_button_frame = ttk.Frame(frame_persos)
create_button_frame.pack(pady=20)
ttk.Button(create_button_frame, text="➕ Créer une nouvelle fiche", bootstyle=SUCCESS, command=on_create_character).pack()

# === PAGES VIDES POUR LES AUTRES MODULES ===
page_titles = {
    "ia": "🤖 IA Assistante",
    "calendrier": "📅 Calendrier & Journal"
}

for module, title_text in page_titles.items():
    frame = ttk.Frame(root)
    pages[module] = frame
    ttk.Button(frame, text="⬅ Menu principal", bootstyle=SECONDARY, command=retour_menu_principal).pack(side="top", anchor="nw", padx=10, pady=10)
    title_label = ttk.Label(frame, text=title_text, font=(base_font_family, 18, "bold"), bootstyle=PRIMARY)
    title_label.pack(pady=20)
    register_scalable_widget(title_label, 18)
    construction_label = ttk.Label(frame, text="🚧 Page en construction...", font=(base_font_family, 16), bootstyle=SECONDARY)
    construction_label.pack(pady=50)
    register_scalable_widget(construction_label, 16)

# === PAGE PARAMETRES ===
frame_parametres = ttk.Frame(root)
pages["parametres"] = frame_parametres

ttk.Button(frame_parametres, text="⬅ Menu principal", bootstyle=SECONDARY, command=retour_menu_principal).pack(side="top", anchor="nw", padx=10, pady=10)

settings_title = ttk.Label(frame_parametres, text="⚙️ Paramètres", font=(base_font_family, 18, "bold"), bootstyle=PRIMARY)
settings_title.pack(pady=20)
register_scalable_widget(settings_title, 18)

# --- Conteneur principal pour les contrôles, centré ---
main_settings_container = ttk.Frame(frame_parametres)
main_settings_container.pack(pady=10, padx=40, fill="x", expand=False)

# --- Groupe Affichage ---
display_labelframe = ttk.Labelframe(main_settings_container, text=" 🖥️ Affichage et Vidéo ", padding=15)
display_labelframe.pack(fill="x", expand=True, pady=(10, 20))
display_labelframe.columnconfigure(1, weight=1) # Permet au widget de s'étendre

# Résolution
ttk.Label(display_labelframe, text="Résolution :").grid(row=0, column=0, padx=10, pady=10, sticky="w")
resolution_var = tk.StringVar()
resolution_combo = ttk.Combobox(display_labelframe, textvariable=resolution_var, values=RESOLUTIONS, state="readonly", width=20)
resolution_combo.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

# Mode d'affichage
ttk.Label(display_labelframe, text="Mode :").grid(row=1, column=0, padx=10, pady=10, sticky="w")
mode_var = tk.StringVar()
mode_frame = ttk.Frame(display_labelframe)
mode_frame.grid(row=1, column=1, padx=10, pady=10, sticky="w")
ttk.Radiobutton(mode_frame, text="Fenêtré", variable=mode_var, value="Fenêtré", bootstyle="toolbutton").pack(side="left", padx=5)
ttk.Radiobutton(mode_frame, text="Plein écran fenêtré", variable=mode_var, value="Plein écran fenêtré", bootstyle="toolbutton").pack(side="left", padx=5)
ttk.Radiobutton(mode_frame, text="Plein écran", variable=mode_var, value="Plein écran", bootstyle="toolbutton").pack(side="left", padx=5)

# --- Groupe À Propos ---
about_labelframe = ttk.Labelframe(main_settings_container, text=" ℹ️ À Propos ", padding=15)
about_labelframe.pack(fill="x", expand=True, pady=(10, 0))

about_text = "Créé par : AzG0G\nDiscord : @azg0g\nEmail : claudio991991@gmail.com"
about_label = ttk.Label(about_labelframe, text=about_text, justify="left")
about_label.pack(anchor="w", padx=5)

# Lien GitHub
github_link = ttk.Label(about_labelframe, text="GitHub: https://github.com/AzG0G/Azg-GameMasterTool", bootstyle=INFO, cursor="hand2")
github_link.pack(anchor='w', padx=5, pady=5)
github_link.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/AzG0G/Azg-GameMasterTool"))
# Créer une police avec soulignement
link_font = font.Font(font=github_link.cget("font"))
link_font.configure(underline=True)
github_link.configure(font=link_font)

copyright_text = "Copyright © 2025 AzG0G. Tous droits réservés."
copyright_label = ttk.Label(about_labelframe, text=copyright_text, justify="left", font=(base_font_family, 8))
copyright_label.pack(anchor="w", padx=5, pady=(10,0))

def show_confirmation_dialog(old_settings, new_settings):
    """Affiche une boîte de dialogue pour confirmer les changements d'affichage avec un minuteur."""
    dialog = ttk.Toplevel(root)
    dialog.title("Confirmer les paramètres")
    dialog.transient(root)
    dialog.grab_set()
    dialog.resizable(False, False)

    countdown = 5
    countdown_var = tk.StringVar(value=f"Annulation automatique dans {countdown} secondes...")
    timer_id = None

    def confirm():
        nonlocal timer_id
        if timer_id:
            dialog.after_cancel(timer_id)
            timer_id = None
        save_settings(new_settings)
        dialog.destroy()
        messagebox.showinfo("Paramètres", "Paramètres d'affichage sauvegardés.")

    def revert():
        nonlocal timer_id
        if timer_id:
            dialog.after_cancel(timer_id)
            timer_id = None
        apply_settings(old_settings)
        dialog.destroy()

    def update_countdown():
        nonlocal countdown, timer_id
        countdown -= 1
        if countdown > 0:
            countdown_var.set(f"Annulation automatique dans {countdown} secondes...")
            timer_id = dialog.after(1000, update_countdown)
        else:
            countdown_var.set("Annulation...")
            revert()

    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill="both", expand=True)
    
    ttk.Label(main_frame, text="Conserver ces paramètres d'affichage ?", font=(base_font_family, 12, "bold")).pack(pady=(0, 10))
    ttk.Label(main_frame, textvariable=countdown_var, bootstyle=SECONDARY).pack()

    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text="Confirmer", command=confirm, bootstyle=SUCCESS).pack(side="left", padx=10)
    ttk.Button(button_frame, text="Annuler", command=revert, bootstyle=DANGER).pack(side="left", padx=10)

    # Centrer la dialog après avoir ajouté les widgets
    dialog.update_idletasks()
    root_x, root_y, root_width, root_height = root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height()
    dialog_width, dialog_height = dialog.winfo_width(), dialog.winfo_height()
    center_x = int(root_x + (root_width / 2) - (dialog_width / 2))
    center_y = int(root_y + (root_height / 2) - (dialog_height / 2))
    dialog.geometry(f"+{center_x}+{center_y}")

    timer_id = dialog.after(1000, update_countdown)
    dialog.protocol("WM_DELETE_WINDOW", revert)

def on_apply_settings():
    old_settings = app_settings.copy()
    new_settings = {
        "resolution": resolution_var.get(),
        "mode": mode_var.get(),
        # On vide la géométrie sauvegardée pour forcer l'utilisation de la nouvelle résolution.
        # La nouvelle position/taille sera sauvegardée à la fermeture de l'application.
        "last_geometry": ""
    }
    display_changed = (old_settings.get("resolution") != new_settings["resolution"] or 
                       old_settings.get("mode") != new_settings["mode"])
    if not display_changed:
        messagebox.showinfo("Paramètres", "Aucun changement d'affichage à appliquer.")
        return
    apply_settings(new_settings)
    show_confirmation_dialog(old_settings, new_settings)

def load_settings_to_ui():
    # Les paramètres globaux sont déjà chargés, on les utilise pour peupler l'UI
    resolution_var.set(app_settings.get("resolution", DEFAULT_SETTINGS["resolution"]))
    mode_var.set(app_settings.get("mode", DEFAULT_SETTINGS["mode"]))

# --- Boutons d'action ---
action_buttons_frame = ttk.Frame(main_settings_container)
action_buttons_frame.pack(pady=20, fill='x')

ttk.Button(action_buttons_frame, text="Appliquer et Sauvegarder", command=on_apply_settings, bootstyle=SUCCESS).pack(side="right")

# === Démarrage de l'application ===

# --- Initialisation de Discord Rich Presence ---
def start_discord_rpc():
    global rpc_manager
    if DISCORD_CLIENT_ID != "YOUR_DISCORD_APPLICATION_CLIENT_ID_HERE":
        print("Démarrage de Discord Rich Presence...")
        rpc_manager = DiscordRPCManager(client_id=DISCORD_CLIENT_ID)
        rpc_manager.start()
    else:
        print("Avertissement: Discord Client ID non configuré. Rich Presence est désactivé.")

# --- Arrêt propre de l'application ---
def on_closing():
    # Si l'application est en mode fenêtré, on sauvegarde sa taille et position.
    # On ne le fait pas pour les modes plein écran pour éviter les comportements inattendus au redémarrage.
    if app_settings.get("mode") == "Fenêtré":
        app_settings["last_geometry"] = root.geometry()
    else:
        # On s'assure de ne pas sauvegarder une géométrie invalide si on quitte depuis le plein écran
        app_settings["last_geometry"] = ""
    save_settings(app_settings) # Sauvegarde les derniers paramètres connus, y compris la géométrie.

    # Arrêter le gestionnaire RPC proprement.
    if rpc_manager:
        print("Arrêt de Discord Rich Presence...")
        rpc_manager.stop()
    
    # Détruire la fenêtre principale.
    root.destroy()

app_settings = load_settings()

# Appliquer les paramètres une première fois pour la géométrie et le scaling.
apply_settings(app_settings)

# Correctif pour la barre des tâches au démarrage en plein écran ou plein écran fenêtré.
# La fonction `set_appwindow` est appelée une seconde fois après un court délai
# pour s'assurer que la fenêtre est bien initialisée par Windows, ce qui résout
# le problème de l'icône manquante au lancement.
def fix_taskbar_on_startup():
    mode = app_settings.get("mode", DEFAULT_SETTINGS["mode"])
    if os.name == 'nt' and (mode == "Plein écran" or mode == "Plein écran fenêtré"):
        set_appwindow(root)
root.after(150, fix_taskbar_on_startup)
root.protocol("WM_DELETE_WINDOW", on_closing)
# Appel de la fonction de setup de la page des quêtes depuis le nouveau module, en passant les modules nécessaires
secondmain.setup_quest_page(root, pages, base_font_family, retour_menu_principal, register_scalable_widget, style, Image, ImageTk, webbrowser)

afficher_page("menu")
recharger_historique_json() # Charge l'historique depuis le JSON au démarrage
load_custom_rolls() # Charge les jets personnalisés sauvegardés
load_characters() # Charge les fiches de personnages
update_character_list_display() # Affiche la liste initiale

# Démarrer le RPC après que la boucle principale soit prête
start_discord_rpc()

root.mainloop()