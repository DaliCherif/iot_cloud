#!/usr/bin/env python3
"""
sensor_simulator.py

Script de simulation de capteurs IoT :
- Envoi asynchrone vers Pub/Sub
- Paramètres configurables (project_id, topic, nombre de capteurs, intervalle)
- Attribution unique de régions par capteur (configurable via CLI)
- Option --once pour n'envoyer qu'une itération
- Logging structuré et gestion des erreurs
- Graceful shutdown au Ctrl+C
"""

import argparse
import json
import logging
import random
import signal
import sys
import time
from datetime import datetime, timezone
from concurrent.futures import TimeoutError

from google.cloud import pubsub_v1

# Configuration du logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)

# Flag pour arrêt gracieux
running = True


def signal_handler(sig, frame):
    """Gestion de l'arrêt gracieux via Ctrl+C."""
    global running
    logger.info("Arrêt demandé, fermeture...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def parse_args():
    """Parse les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Simulateur de capteurs IoT vers Pub/Sub avec régions configurables"
    )
    parser.add_argument(
        "--project", "-p", required=True, help="ID de projet GCP"
    )
    parser.add_argument(
        "--topic", "-t", required=True, help="Nom du topic Pub/Sub"
    )
    parser.add_argument(
        "--sensors", "-n", type=int, default=5,
        help="Nombre de capteurs simulés (défaut : 5)"
    )
    parser.add_argument(
        "--interval", "-i", type=float, default=5.0,
        help="Intervalle entre les itérations (secondes, défaut : 5)"
    )
    parser.add_argument(
        "--regions", type=str,
        default="Tunis,Gafsa,Sfax,Sousse,Nabeul",
        help="Liste de régions (virgule séparées)"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Envoyer une seule itération puis quitter"
    )
    return parser.parse_args()


def make_publisher_client():
    """Crée un client Pub/Sub standard."""
    return pubsub_v1.PublisherClient()


def simulate_and_publish(
    publisher: pubsub_v1.PublisherClient,
    topic_path: str,
    sensor_regions: dict,
    interval: float,
    once: bool
):
    """Boucle de simulation : chaque capteur envoie ses données périodiquement."""
    futures = []
    sensor_ids = list(sensor_regions.keys())
    while running:
        for sensor_id in sensor_ids:
            region = sensor_regions[sensor_id]
            payload = {
                "capteur_id": sensor_id,
                "region": region,
                "temperature": round(random.uniform(20, 100), 2),
                "humidite": round(random.uniform(30, 80), 2),
                "vibration": round(random.uniform(0, 1), 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            data_bytes = json.dumps(payload).encode("utf-8")
            try:
                fut = publisher.publish(topic_path, data_bytes)
                futures.append((fut, payload))
                logger.info(f"Envoyé : {payload}")
            except Exception as e:
                logger.error(f"Erreur publish: {e}")

        # Attendre que les messages soient publiés
        for fut, pl in futures[:]:
            try:
                msg_id = fut.result(timeout=0)
                logger.debug(f"Publié ID={msg_id}")
                futures.remove((fut, pl))
            except TimeoutError:
                pass
            except Exception as e:
                logger.error(f"Erreur futur: {e}")
                futures.remove((fut, pl))

        if once:
            logger.info("--once activé, arrêt après une itération.")
            break

        time.sleep(interval)

    logger.info("Arrêt de la simulation, nettoyage...")
    try:
        publisher.stop()
    except AttributeError:
        pass


def main():
    args = parse_args()
    regions_list = [r.strip() for r in args.regions.split(',') if r.strip()]
    if args.sensors > len(regions_list):
        logger.error("Trop de capteurs pour régions fournies.")
        sys.exit(1)

    random.seed(42)
    random.shuffle(regions_list)
    sensor_regions = {
        f"sensor-{i}": regions_list[i-1]
        for i in range(1, args.sensors + 1)
    }
    logger.info(f"Régions par capteur : {sensor_regions}")

    publisher = make_publisher_client()
    topic_path = publisher.topic_path(args.project, args.topic)

    simulate_and_publish(
        publisher, topic_path, sensor_regions, args.interval, args.once
    )

if __name__ == "__main__":
    main()
