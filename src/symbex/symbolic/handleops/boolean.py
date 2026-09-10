# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from typing import Any, List, Union
import symbex.symbolic.util as util
from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue
from symbex.symbolic.operations import Operations
# from symbex.globals.globals import record_path

from symbex.smtlib import get_smt_lib
smt = get_smt_lib()

boolean_op_lambdas = {
  Operations.AND: (lambda p, q: p and q, lambda p, q: smt.And(p, q)),
  Operations.OR: (lambda p, q: p or q, lambda p, q: smt.Or(p, q))
}


def handle_boolean_op(sv: SymbolicValue, op: Operations, *args, **kwargs) -> Union[SymbolicValue, bool]:
  """
  Handler for boolean operations on symbolic values.
  """
  if op in boolean_op_lambdas:
    if isinstance(sv, SymbolicValue) and util.is_any(sv.get_formula()):
      sv = makeSymbolicValue(
        v=sv.get_value(), formula=util.get_bool(sv.get_formula()))

    newargs: List[Any] = []

    for i in range(len(args)):
      if isinstance(args[i], SymbolicValue) and util.is_any(args[i].get_formula()):
        newargs.append(makeSymbolicValue(
          v=args[i].get_value(), formula=util.get_bool(args[i].get_formula())))
      else:
        newargs.append(args[i])

    concop, symbop = boolean_op_lambdas[op]
    other = newargs[0]
    assert isinstance(other, SymbolicValue)

    if isinstance(other, SymbolicValue):
      return makeSymbolicValue(v=concop(sv.v, other.v), formula=symbop(sv.get_formula(), other.get_formula()))
    else:
      return NotImplemented

  elif op == Operations.NOT:
    newsv = util.narrow_from_any_t(sv, bool)
    return makeSymbolicValue(v=not newsv.get_value(), formula=smt.Not(newsv.get_formula()))

  elif op == Operations.SBOOL:
    return sv

  elif op == Operations.BOOL:
    # if util.is_any(sv.get_formula()):
    #  record_path(makeSymbolicValue(v=type(sv.get_value())
    #              is bool, formula=util.is_bool(sv.get_formula())))

    return bool(sv.get_value())

  raise NotImplementedError
