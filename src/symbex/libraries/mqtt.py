# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from typing import Callable, Any, List, Union
from paho.mqtt.reasoncodes import ReasonCode
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.client import CallbackAPIVersion
from symbex import run_concolic_execution
import sys


class MQTTMessage:
  """MQTT Message"""

  payload: bytes

  def __init__(self, payload):
    self.payload = payload


class Client:
  """MQTT mock client for Py-Symbex"""

  version: CallbackAPIVersion
  """Version of the callback API to use"""

  on_connect: Callable[[Any, Any, Any, Any, Any], None]
  """Callback to be called on connection"""

  on_message: Callable[["Client", Any, MQTTMessage], None]
  """Callback to be called upon receiving a message"""

  on_subscribe: Callable[[Any, Any, Any, Any, Any], None]
  """Callback to be called upon subscribing"""

  on_unsubscribe: Callable[[Any, Any, Any, Any, Any], None]
  """Callback to be called upon unsubscribing"""

  _user_data: Any
  """Associated user data"""

  _url: Union[str, None]
  """URL of the publisher we've connected to"""

  _connected_topics: List[str]
  """List of all the topics we've connected to"""

  def __init__(self, version: CallbackAPIVersion):
    self._version = version
    self._url = None
    self._connected_topics = []
    pass

  def user_data_set(self, user_data: Any) -> None:
    """Sets the user data associated with this client"""
    self._user_data = user_data

  def user_data_get(self) -> Any:
    """Returns the user data associated with this client"""
    return self._user_data

  def connect(self, url: str) -> None:
    """Connect to a publishing server"""
    self._url = url
    self.on_connect(self, self._user_data, None,
                    ReasonCode(PacketTypes.CONNACK), None)

  def loop_forever(self) -> None:
    def publish_message(userdata, message):
      self.on_message(self, userdata, message)
    run_concolic_execution(
      publish_message, "on_message", __name__, False, sys.modules[__name__])

  def subscribe(self, topic: str) -> None:
    self._connected_topics.append(topic)

  def unsubscribe(self, topic: str) -> None:
    self._connected_topics.remove(topic)
