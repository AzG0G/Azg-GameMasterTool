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
import colorsys
import webbrowser

# === Constantes et Variables globales ===
# Pour la sauvegarde des jets
details_lancers = []
# Pour la gestion des paramètres
SETTINGS_FILE = os.path.join("data", "settings.json")
CUSTOM_ROLLS_FILE = os.path.join("data", "custom_rolls.json")
saved_rolls = {} # Dictionnaire pour les jets personnalisés sauvegardés {nom: expression}
DEFAULT_SETTINGS = {"resolution": "1920x1080", "mode": "Fenêtré"}
app_settings = {} # Dictionnaire pour les paramètres chargés
RESOLUTIONS = ["800x600", "1280x720", "1440x900", "1920x1080", "2560x1440"]
# Pour le scaling de l'UI
BASE_WIDTH = 800.0
scaled_widgets = []
# Pour la navigation animée
current_page_name = None
is_animating = False

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

# === Icône de l'application ===
# Note : Pillow (pip install Pillow) est requis pour les formats .jpeg ou .png
try:
    from PIL import Image, ImageTk
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(base_dir, "media", "logo_logiciel.jpeg")
    if os.path.exists(logo_path):
        logo_image = Image.open(logo_path)
        logo_photo = ImageTk.PhotoImage(logo_image)
        # IMPORTANT: Il faut garder une référence à l'objet PhotoImage,
        # sinon Python le supprime (garbage collection) et l'icône disparaît.
        root.logo_photo = logo_photo
        root.iconphoto(False, root.logo_photo)
except Exception as e:
    print("NOTE: Pillow non installé ou logo 'media/logo_logiciel.jpeg' non trouvé. L'icône par défaut sera utilisée.")
    print(f"Erreur détaillée : {e}")

pages = {}  # Dictionnaire pour stocker les différentes pages

# === PAGE MENU PRINCIPAL ===
frame_menu = ttk.Frame(root)
pages["menu"] = frame_menu

menu_title = ttk.Label(frame_menu, text="Azg GameMasterTool", font=(base_font_family, 32, "bold"), bootstyle=PRIMARY)
menu_title.pack(pady=(50, 10))
register_scalable_widget(menu_title, 32)

menu_subtitle = ttk.Label(frame_menu, text="Votre compagnon pour des parties inoubliables", font=(base_font_family, 12), bootstyle=SECONDARY)
menu_subtitle.pack(pady=(0, 40))
register_scalable_widget(menu_subtitle, 12)

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
ttk.Button(bottom_frame, text="🚪 Fermer", bootstyle=(DANGER, OUTLINE), width=15, command=root.destroy).pack(side="left", padx=10, ipady=5)

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

# === PAGES VIDES POUR LES AUTRES MODULES ===
page_titles = {
    "quetes": "📜 Gestion des Quêtes",
    "persos": "👤 Fiches Personnages",
    "ia": "🤖 IA Assistante",
    "calendrier": "📅 Calendrier & Journal"
}

for module, title_text in page_titles.items():
    frame = ttk.Frame(root)
    pages[module] = frame
    # Bouton de retour en haut à gauche, comme dans les autres pages
    ttk.Button(frame, text="⬅ Menu principal", bootstyle=SECONDARY, command=retour_menu_principal).pack(side="top", anchor="nw", padx=10, pady=10)
    # Titre de la page avec icône
    title_label = ttk.Label(frame, text=title_text, font=(base_font_family, 18, "bold"), bootstyle=PRIMARY)
    title_label.pack(pady=20)
    register_scalable_widget(title_label, 18)
    # Message "en construction"
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
        "mode": mode_var.get()
    }
    display_changed = (old_settings.get("resolution") != new_settings["resolution"] or old_settings.get("mode") != new_settings["mode"])
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

app_settings = load_settings()

# Appliquer les paramètres une première fois pour la géométrie et le scaling.
apply_settings(app_settings)

# Correctif pour la barre des tâches au démarrage en plein écran.
# La fonction `set_appwindow` est appelée une seconde fois après un court délai
# pour s'assurer que la fenêtre est bien initialisée par Windows, ce qui résout
# le problème de l'icône manquante au lancement.
def fix_taskbar_on_startup():
    mode = app_settings.get("mode", DEFAULT_SETTINGS["mode"])
    if os.name == 'nt' and (mode == "Plein écran" or mode == "Plein écran fenêtré"):
        set_appwindow(root)
root.after(150, fix_taskbar_on_startup)

afficher_page("menu")
recharger_historique_json() # Charge l'historique depuis le JSON au démarrage
load_custom_rolls() # Charge les jets personnalisés sauvegardés

root.mainloop()
