# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from typing import Any, List, Optional, Generator
from dataclasses import dataclass, field
from abc import ABC
import yaml

try:
  from typing import override  # type: ignore
except ImportError:
  from typing import Callable, TypeAlias
  _Func: TypeAlias = Callable[..., Any]

  def override(func: _Func, /) -> _Func:  # type: ignore
    return func


@dataclass
class YamlFeature(ABC):
  triggered: bool = field(init=False, default=False)

  def set(self):
    self.triggered = True

  def reset(self):
    self.triggered = False

  def propagate(self):
    pass


@dataclass
class YamlAnd(YamlFeature):
  conjuncts: List[YamlFeature]

  @override
  def reset(self):
    self.triggered = False
    for conjunct in self.conjuncts:
      conjunct.reset()

  @override
  def propagate(self):
    all_triggered = True

    for conjunct in self.conjuncts:
      conjunct.propagate()
      all_triggered = all_triggered and conjunct.triggered

    if all_triggered:
      self.set()


@dataclass
class YamlOr(YamlFeature):
  disjuncts: List[YamlFeature]

  @override
  def reset(self):
    self.triggered = False
    for disjunct in self.disjuncts:
      disjunct.reset()

  @override
  def propagate(self):
    one_triggered = False

    for disjunct in self.disjuncts:
      disjunct.propagate()
      one_triggered = one_triggered or disjunct.triggered

    if one_triggered:
      self.set()


@dataclass(frozen=True)
class YamlArgument:
  id: int
  expression: str


@dataclass
class YamlApi(YamlFeature):
  name: str
  args: List[YamlArgument]
  ret: Optional[Any]


def get_all_Api(feature: YamlFeature) -> Generator[YamlApi, None, None]:
  if isinstance(feature, YamlApi):
    yield feature
  elif isinstance(feature, YamlAnd):
    for conjunct in feature.conjuncts:
      for api in get_all_Api(conjunct):
        yield api
  elif isinstance(feature, YamlOr):
    for disjunct in feature.disjuncts:
      for api in get_all_Api(disjunct):
        yield api
  else:
    raise NotImplementedError(
      f"Unknown YAML feature: {feature.__class__.__name__}")


def get_rule(data: dict) -> YamlFeature:
  if "api" in data:
    api = data["api"]
    name = api["name"]
    args: List[YamlArgument] = []
    for arg in api.get("args", []):
      id = arg["id"]
      expression = str(arg["expression"])
      args.append(YamlArgument(id, expression))
    if "return" in api:
      ret = api["return"]
    else:
      ret = None
    return YamlApi(name, args, ret)
  elif "and" in data:
    features: List[YamlFeature] = []
    for conjunct in data["and"]:
      features.append(get_rule(conjunct))
    return YamlAnd(features)
  elif "or" in data:
    features = []
    for conjunct in data["or"]:
      features.append(get_rule(conjunct))
    return YamlOr(features)
  else:
    raise NotImplementedError(f"Cannot parse YAML feature: {data}")


def parse_yaml(filename: str) -> List[YamlFeature]:
  with open(filename, "r") as file:
    data = yaml.safe_load(file.read())

  features: List[YamlFeature] = []

  for feature in data["features"]:
    features.append(get_rule(feature))

  return features
