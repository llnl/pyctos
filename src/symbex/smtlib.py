# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from enum import Enum, auto
from typing import Union, TypeAlias

import z3
import cvc5
import cvc5.pythonic


class SMTLibrary(Enum):
  Z3 = auto()
  CVC5 = auto()


class FloatTheory(Enum):
  FP64 = auto()
  REAL = auto()
  EXREAL = auto()


configured_library: SMTLibrary = SMTLibrary.CVC5
configured_float_theory: FloatTheory = FloatTheory.REAL


def set_smt_lib(lib: SMTLibrary):
  """
  Sets the configured SMT library.
  """
  global configured_library
  configured_library = lib


def get_smt_lib():
  """
  Gets the SMT module associated with the configured SMT library.

  Returns either `z3` or `cvc5.pythonic`.
  Default is `cvc5.pythonic`.
  """
  global configured_library
  if configured_library == SMTLibrary.Z3:
    return z3
  elif configured_library == SMTLibrary.CVC5:
    return cvc5.pythonic
  else:
    # Default solver
    return cvc5.pythonic


def set_float_theory(theory: FloatTheory):
  """
  Set the configured theory to reason about floating-point arithmetic.
  """
  global configured_float_theory
  configured_float_theory = theory


def get_float_theory():
  """
  Get the configured theory to reason about floating-point arithmetic.
  """
  return configured_float_theory


SortRef: TypeAlias = Union[z3.SortRef, cvc5.pythonic.SortRef]
ArithRef: TypeAlias = Union[z3.ArithRef, cvc5.pythonic.ArithRef]
DatatypeRef: TypeAlias = Union[z3.DatatypeRef, cvc5.pythonic.DatatypeRef]
DatatypeSortRef: TypeAlias = Union[z3.DatatypeSortRef,
                                   cvc5.pythonic.DatatypeSortRef]
ModelRef: TypeAlias = Union[z3.ModelRef, cvc5.pythonic.ModelRef]
Solver: TypeAlias = Union[z3.Solver, cvc5.pythonic.Solver]
FuncDeclRef: TypeAlias = Union[z3.FuncDeclRef, cvc5.pythonic.FuncDeclRef]
ExprRef: TypeAlias = Union[z3.ExprRef, cvc5.pythonic.ExprRef]
SetRef: TypeAlias = cvc5.pythonic.SetRef
FPSortRef: TypeAlias = Union[z3.FPSortRef, cvc5.pythonic.FPSortRef]
IntNumRef: TypeAlias = Union[z3.IntNumRef, cvc5.pythonic.IntNumRef]
