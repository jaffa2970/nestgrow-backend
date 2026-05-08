#!/usr/bin/env python3
"""
Quick MQTT test script.
Usage:  python test_mqtt.py {device_id} {numero_zona} {umidita}
        python test_mqtt.py culla-test 1 45.5
"""
import json
import sys
import time
import paho.mqtt.client as mqtt

HOST = "localhost"
PORT = 1883
DEVICE_ID = sys.argv[1] if len(sys.argv) > 1 else "culla-test"
ZONA_NUM  = int(sys.argv[2]) if len(sys.argv) > 2 else 1
UMIDITA   = float(sys.argv[3]) if len(sys.argv) > 3 else 67.3

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(HOST, PORT, 60)

# Publish humidity reading
topic_umidita = f"nestgrow/{DEVICE_ID}/zona/{ZONA_NUM}/umidita"
payload_umidita = json.dumps({"v": UMIDITA, "ts": int(time.time())})
client.publish(topic_umidita, payload_umidita, qos=1).wait_for_publish(timeout=2.0)
print(f"Published → {topic_umidita}: {payload_umidita}")

# Publish tank level
topic_tank = f"nestgrow/{DEVICE_ID}/serbatoio/livello"
payload_tank = json.dumps({"v": 82.0, "ts": int(time.time())})
client.publish(topic_tank, payload_tank, qos=1).wait_for_publish(timeout=2.0)
print(f"Published → {topic_tank}: {payload_tank}")

# Publish heartbeat
topic_hb = f"nestgrow/{DEVICE_ID}/heartbeat"
payload_hb = json.dumps({"uptime_sec": 3600, "wifi_rssi": -55, "ts": int(time.time())})
client.publish(topic_hb, payload_hb, qos=1).wait_for_publish(timeout=2.0)
print(f"Published → {topic_hb}: {payload_hb}")

client.disconnect()
