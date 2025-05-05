import base64
import json
import logging
from google.cloud import bigquery, storage

# Configuration du logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)

# Identifiants des ressources
BQ_TABLE = "clever-grammar-458517.iot_dataset.iot_data"
BUCKET_NAME = "iot-sensor-archive"

# Clients partagés
client_bq = bigquery.Client()
client_storage = storage.Client()
bucket = client_storage.bucket(BUCKET_NAME)


def process_sensor_data(event, context):
    """
    Cloud Function déclenchée par Pub/Sub.
    Traite le message, détecte les anomalies, insère en BigQuery et archive en Cloud Storage.
    """
    try:
        # Décodage du message Pub/Sub
        raw = base64.b64decode(event["data"]).decode("utf-8")
        data = json.loads(raw)
        capteur = data.get("capteur_id", "unknown")
        region = data.get("region", "unknown")

        # Détection d'anomalie
        temp = data.get("temperature", 0)
        data["anomalie"] = temp > 70
        anomalie = data["anomalie"]

        # Insertion en BigQuery
        errors = client_bq.insert_rows_json(BQ_TABLE, [data])
        if errors:
            logger.error(f"Erreur insertion BigQuery pour {capteur} ({region}): {errors}")
        else:
            logger.info(f"Ligne insérée en BigQuery: {capteur} ({region}), anomalie={anomalie}")

        # Archivage dans Cloud Storage
        timestamp = data.get("timestamp", "no-timestamp")
        blob = bucket.blob(f"archive/{timestamp}.json")
        blob.upload_from_string(json.dumps(data))
        logger.info(f"Message archivé: {capteur} ({region}) -> {timestamp}.json")

    except Exception as e:
        logger.exception(f"Erreur lors du traitement du message Pub/Sub: {e}")
        # Optionnel: ré-émettre l'erreur pour re-essaie selon la configuration
        raise
