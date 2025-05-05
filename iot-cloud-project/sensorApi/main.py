from flask import Flask, jsonify
from flask_cors import CORS
from google.cloud import bigquery
import os

app = Flask(__name__)
CORS(app)  # autorise les appels depuis le front‑end statique
client = bigquery.Client()

@app.route("/latest-sensors")
def latest_sensors():
    sql = """
    SELECT AS STRUCT capteur_id, region, temperature, anomalie, timestamp
    FROM (
      SELECT *, ROW_NUMBER() OVER (
        PARTITION BY capteur_id ORDER BY timestamp DESC
      ) rn
      FROM `clever-grammar-458517.iot_dataset.iot_data`
    )
    WHERE rn = 1
    ORDER BY capteur_id
    """
    rows = client.query(sql).result()
    return jsonify([dict(r) for r in rows])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
