# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import symbex.symbolic.util as util
from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue
from inspect import Signature, BoundArguments
from typing import Any, Union
from symbex.smtlib import get_smt_lib, ExprRef
smt = get_smt_lib()


def make_var(name: str) -> ExprRef:
  """
  Makes a symbolic variable of type `any_sort` with name `name`.
  """
  return smt.Const(name, util.any_sort)


def make_symbolic_var(v: Any, name: str) -> SymbolicValue:
  """
  Create a symbolic variable with concrete value `v` and name `name`.
  """
  return makeSymbolicValue(v=v, formula=make_var(name))


def make_default_symbolic_var(name: str) -> SymbolicValue:
  """
  Create a symbolic variable with the default concrete value and name `name`.

  For the default concrete value, see `symbex.symbolic.util.get_default_value()`.
  """
  return make_symbolic_var(util.get_default_value(), name)


lift_idx: int = 0


def lift_value(v: Union[None, SymbolicValue, int, float, bool, str]) -> SymbolicValue:
  """
  Lifts a value to a symbolic variable. Supported types are integers, floats, and booleans.
  Heap types (e.g., lists, objects) raise a `NotImplementedError`.

  `None` and symbolic values just return the input, and nothing is done to them.
  """
  if isinstance(v, SymbolicValue):
    return v
  elif v is None:
    return makeSymbolicValue(v=v, formula=util.create_none())
  elif type(v) is int:
    return makeSymbolicValue(v=v, formula=smt.IntVal(v))
  elif type(v) is float:
    return makeSymbolicValue(v=v, formula=util.float_val(v))
  elif type(v) is bool:
    return makeSymbolicValue(v=v, formula=smt.BoolVal(v))
  elif type(v) is str:
    return makeSymbolicValue(v=v, formula=smt.StringVal(v))
  else:
    raise NotImplementedError


def concretize_args(sig: Signature, symb_args: BoundArguments) -> BoundArguments:
  """
  Replace symbolic parameters with concretized values in a list of function args.
  """
  return sig.bind(**{k: v.get_value() if isinstance(v, SymbolicValue) else v for k, v in symb_args.arguments.items()})


def lift_args(sig: Signature, args: BoundArguments) -> BoundArguments:
  """
  Make a list of bound function args fully symbolic.
  """
  return sig.bind(**{k: lift_value(v) for k, v in args.arguments.items()})
