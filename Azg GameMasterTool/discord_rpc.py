# © 2025 AzG0G
# Ce logiciel est protégé par le droit d'auteur.
# Tous droits réservés.

import pypresence
import time
import threading
import asyncio

class DiscordRPCManager:
    """Gère la connexion et les mises à jour pour Discord Rich Presence."""
    def __init__(self, client_id):
        self.client_id = client_id
        self.rpc = None
        self.start_time = int(time.time())
        self.connection_thread = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()

    def _connect_loop(self):
        """Boucle dans un thread pour tenter de se connecter à Discord."""
        while not self.stop_event.is_set():
            if self.rpc is None:
                try:
                    # Verrouiller pour éviter une condition de concurrence avec stop()
                    with self.lock:
                        if self.stop_event.is_set():
                            break
                        # On passe une nouvelle boucle d'événements à chaque tentative de connexion
                        self.rpc = pypresence.Presence(self.client_id, loop=asyncio.new_event_loop())
                        self.rpc.connect()
                    
                    print("Connecté à Discord RPC.")
                    self.update_presence("Dans le menu principal", "Prêt à jouer")

                except pypresence.exceptions.DiscordNotFound:
                    print("Discord non détecté. Nouvelle tentative dans 20 secondes.")
                    self.rpc = None
                    self.stop_event.wait(20)
                    continue
                except Exception as e:
                    print(f"Erreur de connexion RPC non gérée : {e}")
                    self.rpc = None
                    self.stop_event.wait(20)
                    continue
            
            # Attendre 15 secondes ou jusqu'à ce que l'arrêt soit demandé
            self.stop_event.wait(15)

        print("Thread de connexion RPC terminé.")

    def start(self):
        """Démarre la connexion RPC dans un thread séparé."""
        if self.connection_thread and self.connection_thread.is_alive():
            return
        self.stop_event.clear()
        self.connection_thread = threading.Thread(target=self._connect_loop, daemon=True)
        self.connection_thread.start()

    def stop(self):
        """Arrête la connexion RPC et attend la fin du thread."""
        if not self.connection_thread or not self.connection_thread.is_alive():
            return

        self.stop_event.set()

        with self.lock:
            if self.rpc:
                try:
                    self.rpc.close()
                    print("Connexion RPC fermée.")
                except Exception as e:
                    print(f"Erreur lors de la fermeture du RPC : {e}")
                self.rpc = None
        
        self.connection_thread.join(timeout=3.0)

        if self.connection_thread.is_alive():
            print("Avertissement: Le thread RPC n'a pas terminé à temps.")
        else:
            print("Gestionnaire RPC arrêté avec succès.")

    def update_presence(self, details, state):
        """Met à jour le statut Rich Presence. Peut être appelé depuis n'importe quel thread."""
        with self.lock:
            if not self.rpc or self.stop_event.is_set():
                return
            try:
                self.rpc.update(
                    details=details,
                    state=state,
                    start=self.start_time,
                    large_image="logo_large",
                    large_text="Azg GameMasterTool",
                    small_image="d20_icon",
                    small_text="Jeu de Rôle"
                )
            except pypresence.exceptions.PipeClosed:
                print("Pipe RPC fermée, la reconnexion sera tentée.")
                # En mettant rpc à None, la boucle de connexion tentera de se reconnecter
                self.rpc = None
            except Exception as e:
                print(f"Erreur lors de la mise à jour de la présence : {e}")
                self.rpc = None
