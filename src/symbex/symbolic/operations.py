# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from enum import Enum, auto


class Operations(Enum):
  """
  Enum of all the different operations supported by symbolic variables.
  """
  GT = auto()
  LT = auto()
  GE = auto()
  LE = auto()
  EQ = auto()
  NE = auto()
  ADD = auto()
  RADD = auto()
  SUB = auto()
  RSUB = auto()
  MUL = auto()
  RMUL = auto()
  TRUEDIV = auto()
  RTRUEDIV = auto()
  FLOORDIV = auto()
  RFLOORDIV = auto()
  BOOL = auto()
  SBOOL = auto()
  GETITEM = auto()
  SETITEM = auto()
  CONTAINS = auto()
  ITER = auto()
  LEN = auto()
  MEMBER = auto()
  SETMEMBER = auto()
  AND = auto()
  OR = auto()
  NOT = auto()
  APPEND = auto()
  POP = auto()
  KEYS = auto()
  ITEMS = auto()
  GET = auto()
  SPLIT = auto()
  INT = auto()
  FLOAT = auto()
