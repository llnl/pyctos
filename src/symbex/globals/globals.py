# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from typing import Optional, TYPE_CHECKING
from symbex.types.symbolicvalue import SymbolicValue

if TYPE_CHECKING:
  from symbex.engine.engine import ConcolicEngine


engine: Optional["ConcolicEngine"] = None


def set_engine(e: "ConcolicEngine") -> None:
  """
  Set the concolic engine.
  """
  global engine
  engine = e


def get_engine() -> "ConcolicEngine":
  """
  Get the concolic engine.
  """
  global engine
  assert engine is not None
  return engine


def record_path(x: SymbolicValue) -> None:
  """
  Record a new path to the path condition.
  The negation is taken and is solved for by the SMT solver.
  If `SAT` is returned, the SMT model is converted into concrete python objects and added to the list of unexplored inputs.
  """
  global engine
  assert engine
  return engine.record_path(x)


def make_assertion(x: SymbolicValue) -> None:
  """
  Make an assertion to the path condition. Assertions are different from path conditions in that their negation is never attempted.
  """
  global engine
  assert engine
  return engine.make_assertion(x)


def prove(x: SymbolicValue) -> bool:
  """
  Returns whether the expression can be proven true against the current path
  condition and axioms. Does not modify the path condition or global state.
  """
  global engine
  assert engine
  return engine.prove(x)
