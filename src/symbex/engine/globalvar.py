# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from dataclasses import dataclass
from typing import Callable, Any, Set
from types import ModuleType, FunctionType, BuiltinFunctionType
from inspect import getclosurevars, getmodule

import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GlobalVar:
  name: str
  origin: ModuleType

  def get(self):
    """
    Get this global variable from the module.
    """
    return self.origin.__getattribute__(self.name)

  def put(self, v: Any):
    """
    Assign this global variable in the module.
    """
    self.origin.__setattr__(self.name, v)


def gather_globals(f: Callable[..., Any], origin: ModuleType) -> Set[GlobalVar]:
  """
  Gathers a set of all the global variables in the origin module given a function `f`.
  """
  ret: Set[GlobalVar] = set()
  if origin is None:
    logger.debug("Missing module for:", f)
    return ret

  assert origin
  for gname, gval in getclosurevars(f).globals.items():
    if callable(gval) and isinstance(gval, FunctionType):
      try:
        ret |= gather_globals(gval, origin)
      except:
        pass
    elif type(gval) == ModuleType or type(gval) == FunctionType or isinstance(gval, type) or type(gval) == BuiltinFunctionType:
      logger.debug(f"Skipping type: {gval}")
    else:
      logger.debug(f"Adding global: {gname}")
      ret.add(GlobalVar(gname, origin))

  return ret
