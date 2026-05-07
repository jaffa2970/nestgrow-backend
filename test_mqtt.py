#!/usr/bin/env python3
"""
Quick MQTT test script.
Usage:  python test_mqtt.py [zona_id] [umidita]
        python test_mqtt.py 1 45.5
"""
import json
import sys
import time
import paho.mqtt.client as mqtt

HOST = "localhost"
PORT = 1883
ZONA_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 1
UMIDITA = float(sys.argv[2]) if len(sys.argv) > 2 else 67.3

payload = json.dumps({"v": UMIDITA, "ts": int(time.time()), "device_id": "nestgrow-test"})
topic = f"nestgrow/zona/{ZONA_ID}/umidita"

client = mqtt.Client()
client.connect(HOST, PORT, 60)
result = client.publish(topic, payload, qos=1)
result.wait_for_publish()
client.disconnect()

print(f"Published → {topic}: {payload}")

# Also send a tank level
tank_payload = json.dumps({"v": 82.0, "ts": int(time.time()), "device_id": "nestgrow-test"})
client2 = mqtt.Client()
client2.connect(HOST, PORT, 60)
client2.publish("nestgrow/serbatoio/livello", tank_payload, qos=1).wait_for_publish()
client2.disconnect()
print(f"Published → nestgrow/serbatoio/livello: {tank_payload}")
