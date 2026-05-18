import logging
import time
import os
import json
import pandas as pd
from datetime import datetime, timedelta, timezone

from paho.mqtt.client import Client, MQTTv311, CallbackAPIVersion


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

pollInterval = int(os.getenv('POLL_INTERVAL'))
logging.info('Received POLL_INTERVAL %s' % pollInterval)

units_df = pd.read_csv('/data/units.csv')

meterNamesMqttTopics = os.getenv('METER_NAMES_AND_MQTT_TOPICS')
logging.info('Read units.csv and got list of meter IDs as %s' % units_df['meter_id'].tolist())

if not meterNamesMqttTopics is None:
    meterNamesMqttTopics = json.loads(meterNamesMqttTopics)

if not os.getenv('IGNORE_DB', False):
    import psycopg2
    from psycopg2.extras import execute_values
    
    db_params = {
        'host': os.getenv('TIMESCALE_HOST', 'timescaledb'),
        'port': os.getenv('TIMESCALE_PORT', '5432'),
        'dbname': os.getenv('TIMESCALE_DB', 'einzaehler'),
        'user': os.getenv('TIMESCALE_USER', 'einzaehler'),
        'password': os.getenv('TIMESCALE_PASSWORD', 'einzaehler'),
    }

meterNamesTopicsKeys = pd.DataFrame(
    columns=['name','topic','import_key','export_key'])

meterNamesTopicsKeys.loc[len(meterNamesTopicsKeys)] = {
    'name': 'grid',
    'topic': gridMqttTopic['topic'],
    'import_key': gridMqttTopic['import_key'],
    'export_key': gridMqttTopic['export_key'] if 'export_key' in gridMqttTopic.keys() else None
}

for key in meterNamesMqttTopics.keys():
    assert key != 'grid', 'The name ''grid'' is a reserved name for the grid meter!'
    assert not key in meterNamesTopicsKeys['name'].values, 'The name %s is already used!' % key

    topic = meterNamesMqttTopics[key]['topic']
    assert not topic in meterNamesTopicsKeys['topic'].values, 'The topic %s is already assigned to another meeter!' % topic

    meterNamesTopicsKeys.loc[len(meterNamesTopicsKeys)] = {
        'name': key,
        'topic': topic,
        'import_key': meterNamesMqttTopics[key]['import_key'] if 'import_key' in meterNamesMqttTopics[key].keys() else None,
        'export_key': meterNamesMqttTopics[key]['export_key'] if 'export_key' in meterNamesMqttTopics[key].keys() else None
    }

messages = pd.DataFrame(
    columns=['timestamp','msg_timestamp','name','topic','import','export']
)

timestamp = datetime.now(timezone.utc)

def on_connect(client, userdata, flags, reasonCode, properties):
    logging.info(f"Connected with reason code {reasonCode}")

def on_message(client, userdata, msg):
    global messages
    global timestamp

    payload = msg.payload.decode("utf-8", errors="replace")
    if os.getenv('LOG_ALL_MQTT_DATA',False):
        print(f"Received: {msg.topic} → {payload}")

    topic = msg.topic

    if topic in meterNamesTopicsKeys['topic'].values:
        if not msg.topic in messages['topic'].values:
            if msg.retain:
                logging.info(
                    'Received non-retained message for topic %s.' % topic
                )
            else:
                logging.warning(
                    'Received non-retained message for topic %s. Make sure that messages are retained!' % topic
                )
            
            payload = json.loads(payload)
            if "Time" in payload.keys():
                msg_timestamp = datetime.fromisoformat(payload["Time"])
            else:
                msg_timestamp = datetime.now(timezone.utc)
            
            name = meterNamesTopicsKeys.loc[meterNamesTopicsKeys['topic']==topic,'name'].iloc[0]
            
            imp = payload
            if meterNamesTopicsKeys.loc[meterNamesTopicsKeys['topic']==topic,'import_key'].iloc[0] is None:
                imp = None
            else:
                for k in meterNamesTopicsKeys.loc[meterNamesTopicsKeys['topic']==topic,'import_key'].iloc[0]:
                    imp = imp[k]
                try:
                    imp = float(imp)
                except Exception as e:
                    logging.warning('Could not convert import value %s for %s to float!' % (imp,name))
                    imp = None

            if meterNamesTopicsKeys.loc[meterNamesTopicsKeys['topic']==topic,'export_key'].iloc[0] is None:
                exp = None
            else:
                exp = payload
                for k in meterNamesTopicsKeys.loc[meterNamesTopicsKeys['topic']==topic,'export_key'].iloc[0]:
                    exp = exp[k]
                try:
                    exp = float(exp)
                except Exception as e:
                    logging.warning('Could not convert export value %s for %s to float!' % (imp,name))
                    imp = None
            
                              
            messages.loc[len(messages)] = {
                "timestamp": timestamp,
                'msg_timestamp': msg_timestamp,
                "name": name, 
                "topic": topic,
                "import": imp,
                "export": exp
                }
    
    if all(topic in messages['topic'].values for topic in meterNamesTopicsKeys['topic'].values):
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

    while not all(topic in messages['topic'].values for topic in meterNamesTopicsKeys['topic'].values):
        time.sleep(0.1)

    client.loop_stop()
    client.disconnect()

    insert_messages_to_db(messages)

    messages = pd.DataFrame(
        columns=['timestamp','msg_timestamp','name','topic','import','export']
    )

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
            INSERT INTO meterreadings (timestamp, msg_timestamp, name, topic, import, export)
            VALUES %s
        """

        # Convert DataFrame to list of tuples
        values = [
            (
                row['timestamp'],
                row['msg_timestamp'],
                row['name'],
                row['topic'],
                row['import'],
                row['export']
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meterreadings (
                timestamp TIMESTAMPTZ NOT NULL,
                msg_timestamp TIMESTAMPTZ,
                name TEXT,
                topic TEXT,
                import DOUBLE PRECISION,
                export DOUBLE PRECISION
            );
        """)
        cursor.execute("SELECT create_hypertable('meterreadings', 'timestamp', if_not_exists => TRUE);")

        conn.commit()
        logging.info("Ensured meterreadings table exists and is hypertable.")
    except Exception as e:
        logging.error(f"Failed to ensure table exists: {e}")
    finally:
        cursor.close()
        conn.close()

def wait_until_next_schedule():
    now = datetime.now()
    next_quarter = (now + timedelta(minutes=pollInterval)).replace(second=0, microsecond=0)
    next_quarter = next_quarter - timedelta(minutes=next_quarter.minute % pollInterval)
    wait_seconds = (next_quarter - now).total_seconds()
    time.sleep(wait_seconds)

if not os.getenv('IGNORE_DB', False):
    ensure_table_exists()

#logging.info('Waiting to start logging in %s min schedule...' % pollInterval)
#wait_until_next_schedule()
#logging.info('Done waiting')

while True:
    logging.info('Wait until polling interval is reached')
    wait_until_next_schedule()
    logging.info('Done waiting')
    store_latest_values()
   
