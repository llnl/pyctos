# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from symbex.symbolic import factories
from symbex.types.symbolicvalue import SymbolicValue


__all__ = [
  'PyctosAssertionError', 'pyctos_assert', 'pyctos_prove'
]


class PyctosAssertionError(AssertionError):
  """
  Assertion failed in instrumented code; counts as a test failure.
  Usually used to indicate Pyctos is modeling something incorrectly or inconsistently.
  """


def pyctos_assert(expr: bool | SymbolicValue, message: str = "assertion failed") -> None:
  """
  Makes a concrete assertion that fails the pyctos test run if false, rather
  than being treated as a new part of the path condition like plain `assert`.
  """
  # If the expression is concolic, we only care about the concrete part
  if isinstance(expr, SymbolicValue):
    expr = expr.get_value()

  # Raise a specific exception that will be caught by the engine and re-raised
  if not expr:
    raise PyctosAssertionError(message)


def pyctos_prove(expr: bool | SymbolicValue, message: str = "proof failed") -> None:
  """
  Checks whether a concolic condition can be proven to be true under the
  current path condition. If the condition is concretely false, or a proof
  by contradiction fails, this is an immediate test failure.
  """
  if isinstance(expr, SymbolicValue):
    if not expr.get_value():
      raise PyctosAssertionError(message)

    from symbex.globals import globals as engine_globals
    if engine_globals.engine is None:
      # If the engine is unset, we're in pyctat replay; don't try to prove anything
      return

    # If we're in pyctos exploration, attempt the proof
    if not engine_globals.prove(expr):
      raise PyctosAssertionError(message)

    return

  # If we got a concrete value, treat it as a regular assertion
  if not expr:
    raise PyctosAssertionError(message)
