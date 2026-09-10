# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import paho.mqtt.client as mqtt


def on_subscribe(client, userdata, mid, reason_code_list, properties):
  # Since we subscribed only for a single channel, reason_code_list contains
  # a single entry
  if reason_code_list[0].is_failure:
    print(f"Broker rejected you subscription: {reason_code_list[0]}")
  else:
    print(f"Broker granted the following QoS: {reason_code_list[0].value}")


def on_unsubscribe(client, userdata, mid, reason_code_list, properties):
  # Be careful, the reason_code_list is only present in MQTTv5.
  # In MQTTv3 it will always be empty
  if len(reason_code_list) == 0 or not reason_code_list[0].is_failure:
    print("unsubscribe succeeded (if SUBACK is received in MQTTv3 it success)")
  else:
    print(f"Broker replied with failure: {reason_code_list[0]}")
  client.disconnect()


def on_message(client: mqtt.Client, userdata, message: bytes):
  payload = message.payload

  if payload == "This is a test message!":
    pass

  # userdata is the structure we choose to provide, here it's a list()
  userdata.append(payload)
  # We only want to process 10 messages
  if len(userdata) >= 10:
    client.unsubscribe("$SYS/#")


def on_connect(client, userdata, flags, reason_code, properties):
  if reason_code.is_failure:
    print(
      f"Failed to connect: {reason_code}. loop_forever() will retry connection")
  else:
    # we should always subscribe from on_connect callback to be sure
    # our subscribed is persisted across reconnections.
    client.subscribe("$SYS/#")


mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.on_subscribe = on_subscribe
mqttc.on_unsubscribe = on_unsubscribe

mqttc.user_data_set([])
mqttc.connect("mqtt.eclipseprojects.io")
mqttc.loop_forever()
