import logging
import time
import os
import json
import pandas as pd
from datetime import datetime, timedelta, timezone

from paho.mqtt.client import Client, MQTTv311, CallbackAPIVersion

import psycopg2
from psycopg2.extras import execute_values

# For local testing
local_env_path = os.path.join(os.getcwd(),'.env')
if os.path.isfile(local_env_path):
    from dotenv import load_dotenv
    load_dotenv(local_env_path)

logging.basicConfig(
    level=logging.INFO,  # <- Ohne das wird INFO nicht ausgegeben
    format='%(asctime)s [%(levelname)s] %(message)s'
)

logging.info('Hello world')\

mqttBroker = os.getenv('MQTT_BROKER')
logging.info('Received MQTT-Broker %s' % mqttBroker)

mqttUser = os.getenv('MQTT_USER')
logging.info('Received MQTT-User %s' % mqttUser)

mqttPass = os.getenv('MQTT_PASS')
logging.info('Received MQTT-Password')

logging.info('Logging all incoming MQTT messages is ' + ('enabled' if os.getenv('LOG_ALL_MQTT_DATA',False) else 'disabled'))

pollInterval = int(os.getenv('POLL_INTERVAL'))
logging.info('Received POLL_INTERVAL %s' % pollInterval)

meters_df = pd.read_csv('/data/meters.csv')
all_meter_ids = meters_df['id'].tolist()
logging.info('Read meters.csv and got list of meter IDs as %s' % all_meter_ids)

db_params = {
    'host': os.getenv('POSTGRES_HOST', 'db'),
    'port': os.getenv('POSTGRES_PORT', '5432'),
    'dbname': os.getenv('POSTGRES_DB', 'metering'),
    'user': os.getenv('POSTGRES_USER', 'metering'),
    'password': os.getenv('POSTGRES_PASSWORD', 'metering'),
}

def create_message_df():
    return pd.DataFrame(
        columns=['timestamp','msg_timestamp','meter_id','total_import','total_export']
    )

messages = create_message_df()

timestamp = datetime.now(timezone.utc)

def on_connect(client, userdata, flags, reasonCode, properties):
    logging.info(f"Connected with reason code {reasonCode}")

def on_message(client, userdata, msg):
    global messages
    global timestamp

    payload = msg.payload.decode("utf-8", errors="replace")
    if os.getenv('LOG_ALL_MQTT_DATA',False):
        print(f"Received: {msg.topic} → {payload}")

    topic = msg.topic.replace('metering/','')

    if topic in all_meter_ids:
        if not topic in messages['meter_id'].values:
            if msg.retain:
                logging.info(
                    'Received retained message for topic %s.' % topic
                )
            else:
                logging.warning(
                    'Received non-retained message for topic %s. Make sure that messages are retained!' % topic
                )
            
            payload = json.loads(payload)
            if "timestamp" in payload.keys():
                msg_timestamp = datetime.fromisoformat(payload["timestamp"])
            else:
                msg_timestamp = datetime.now(timezone.utc)
            
            meter_id = topic

            if "total_import" in payload.keys():
                imp = payload["total_import"]
                try:
                    imp = float(imp)
                except Exception as e:
                    logging.warning('Could not convert import value %s for %s to float!' % (imp,meter_id))
                    imp = None
            else:
                imp = None

            if "total_export" in payload.keys():
                exp = payload["total_export"]
                try:
                    exp = float(exp)
                except Exception as e:
                    logging.warning('Could not convert export value %s for %s to float!' % (exp,meter_id))
                    exp = None
            else:
                exp = None

                              
            messages.loc[len(messages)] = {
                "timestamp": timestamp,
                'msg_timestamp': msg_timestamp,
                "meter_id": meter_id,
                "total_import": imp,
                "total_export": exp
                }
    
    if all(meter_id in messages['meter_id'].values for meter_id in all_meter_ids):
        logging.info("All expected topics received. Stopping loop.")
        for ind, row in messages.iterrows():
            logging.info(row)
        client.loop_stop()

def store_latest_values():
    global messages
    global timestamp

    timestamp = datetime.now(timezone.utc)

    client = Client(protocol=MQTTv311, callback_api_version=CallbackAPIVersion.VERSION2)
    client.username_pw_set(mqttUser, mqttPass)
    client.on_message = on_message
    client.on_connect = on_connect
    client.connect(mqttBroker, 1883)

    logging.info('Subscribing')
    client.subscribe("#")  # Wildcard: alle Topics
    client.loop_start()

    while not all(topic in messages['meter_id'].values for topic in all_meter_ids):
        time.sleep(0.1)

    client.loop_stop()
    client.disconnect()

    insert_messages_to_db(messages)

    messages = create_message_df()

def insert_messages_to_db(df):
    if df.empty:
        logging.info("No messages to insert.")
        return

    try:
        if not os.getenv('IGNORE_DB', False):
            conn = psycopg2.connect(**db_params)
            cursor = conn.cursor()

        # Prepare insert
        insert_query = """
            INSERT INTO meterreadings (timestamp, msg_timestamp, meter_id, total_import, total_export)
            VALUES %s
        """

        # Convert DataFrame to list of tuples
        values = [
            (
                row['timestamp'],
                row['msg_timestamp'],
                row['meter_id'],
                row['total_import'],
                row['total_export']
            )
            for _, row in df.iterrows()
        ]

        if not os.getenv('IGNORE_DB', False):
            execute_values(cursor, insert_query, values)
            conn.commit()
            logging.info(f"Inserted {len(values)} rows into meterreadings.")

    except Exception as e:
        logging.error(f"DB insert failed: {e}")
    finally:
        if not os.getenv('IGNORE_DB', False):
            cursor.close()
            conn.close()

def ensure_table_exists():
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()

        # 1. Tabelle erstellen (Spalten im Primary Key MÜSSEN "NOT NULL" sein)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meterreadings (
                timestamp TIMESTAMPTZ NOT NULL,
                msg_timestamp TIMESTAMPTZ NOT NULL,
                meter_id TEXT NOT NULL,
                total_import NUMERIC(12, 4), -- NULL erlaubt, falls ein Zähler nur exportiert
                total_export NUMERIC(12, 4), -- NULL erlaubt für Wasser/Wärme oder reine Verbraucher
                PRIMARY KEY (meter_id, msg_timestamp)
            );
        """)
        
        # 2. Der create_hypertable-Aufruf wurde hier komplett entfernt.

        conn.commit()
        logging.info("Ensured meterreadings table exists in PostgreSQL.")
    except Exception as e:
        logging.error(f"Failed to ensure table exists: {e}")
    finally:
        # Sicherstellen, dass Variablen existieren, bevor sie geschlossen werden
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


def wait_until_next_schedule():
    now = datetime.now()
    next_quarter = (now + timedelta(minutes=pollInterval)).replace(second=0, microsecond=0)
    next_quarter = next_quarter - timedelta(minutes=next_quarter.minute % pollInterval)
    wait_seconds = (next_quarter - now).total_seconds()
    time.sleep(wait_seconds)

ensure_table_exists()

#logging.info('Waiting to start logging in %s min schedule...' % pollInterval)
#wait_until_next_schedule()
#logging.info('Done waiting')

while True:
    logging.info('Wait until polling interval is reached')
    wait_until_next_schedule()
    logging.info('Done waiting')
    store_latest_values()
   
