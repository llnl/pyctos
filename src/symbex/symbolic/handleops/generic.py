# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from typing import Union, List

import symbex.symbolic.util as util
from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue
from symbex.symbolic.operations import Operations
import symbex.symbolic.factories as factories

from symbex.smtlib import get_smt_lib, ExprRef, configured_library, SMTLibrary
smt = get_smt_lib()


def generate_set_eq(expr1: SymbolicValue, expr2: Union[SymbolicValue, set]) -> ExprRef:
  """
  Generates an equality check between two sets.

  The following operations are performed:
  - If `expr2` is a symbolic value, we emit a check that demonstrates that `expr1` and `expr2` are sets, and they dereference to the same value.
  - If `expr2` is a concrete set, we emit a check that `len(expr1) == len(expr2)` and discrete checks for every element of `expr2` that that element is in `expr1`.
  """
  e1formula = expr1.get_formula()
  if isinstance(expr2, SymbolicValue):
    e2formula = expr2.get_formula()
    conjuncts: List[ExprRef] = []
    if util.is_any(e1formula):
      conjuncts.append(util.is_reference(e1formula))
      conjuncts.append(util.is_set(util.dereference(e1formula)))
      conjuncts.append(util.is_reference(e2formula))
      conjuncts.append(util.is_set(util.dereference(e2formula)))
    conjuncts.append(util.dereference(e1formula) ==
                     util.dereference(e2formula))
    return smt.And(*conjuncts)
  elif isinstance(expr2, set):
    conjuncts = []
    if util.is_any(e1formula):
      conjuncts.append(util.is_reference(e1formula))
      conjuncts.append(util.is_set(util.dereference(e1formula)))
    if configured_library == SMTLibrary.CVC5:
      conjuncts.append(util.get_cardinality(util.get_set(
        util.dereference(e1formula))) == len(expr2))
    else:
      conjuncts.append(util.bound(util.get_reference(e1formula)) == len(expr2))
    for item in expr2:
      in_test: SymbolicValue = expr1.__contains__(item)
      conjuncts.append(in_test.get_formula())
    return smt.And(*conjuncts)
  else:
    raise NotImplementedError


def generate_dict_eq(expr1: SymbolicValue, expr2: Union[SymbolicValue, dict]) -> ExprRef:
  """
  Generates an equality check between two dicts.

  The following operations are performed:
  - If `expr2` is a symbolic value, we emit a check that demonstrates that `expr1` and `expr2` are dicts, and they dereference to the same value.
  - If `expr2` is a concrete dict, we emit a check that `len(expr1) == len(expr2)` and discrete checks for every element of `expr2` that `expr1[i] == expr2[i]`.
  """
  e1formula = expr1.get_formula()
  if isinstance(expr2, SymbolicValue):
    e2formula = expr2.get_formula()
    conjuncts: List[ExprRef] = []
    if util.is_any(e1formula):
      conjuncts.append(util.is_reference(e1formula))
      conjuncts.append(util.is_dict(util.dereference(e1formula)))
      conjuncts.append(util.is_reference(e2formula))
      conjuncts.append(util.is_dict(util.dereference(e2formula)))
    conjuncts.append(util.dereference(e1formula) ==
                     util.dereference(e2formula))
    return smt.And(*conjuncts)
  elif isinstance(expr2, dict):
    conjuncts = []
    if util.is_any(e1formula):
      conjuncts.append(util.is_reference(e1formula))
      conjuncts.append(util.is_dict(util.dereference(e1formula)))
    conjuncts.append(util.get_dict_cardinality(
      util.dereference(e1formula)) == len(expr2))
    for key, value in expr2.items():
      in_test: SymbolicValue = expr1.__contains__(key)
      conjuncts.append(in_test.get_formula())
      eq_test: SymbolicValue = expr1[key] == value
      conjuncts.append(eq_test.get_formula())
    return smt.And(*conjuncts)
  else:
    raise NotImplementedError


def generate_list_eq(expr1: SymbolicValue, expr2: Union[SymbolicValue, list, tuple]) -> ExprRef:
  """
  Generates an equality check between two lists or tuples.

  The following operations are performed:
  - If `expr2` is a symbolic value, we emit a check that demonstrates that `expr1` and `expr2` are lists, and they dereference to the same value.
  - If `expr2` is a concrete list, we emit a check that `len(expr1) == len(expr2)` and discrete checks for every element of `expr2` that `expr1[i] == expr2[i]`.
  """
  e1formula = expr1.get_formula()
  if isinstance(expr2, SymbolicValue):
    e2formula = expr2.get_formula()
    conjuncts: List[ExprRef] = []
    if util.is_any(e1formula):
      conjuncts.append(util.is_reference(e1formula))
      conjuncts.append(util.is_list(util.dereference(e1formula)))
      conjuncts.append(util.is_reference(e2formula))
      conjuncts.append(util.is_list(util.dereference(e2formula)))
    conjuncts.append(util.dereference(e1formula) ==
                     util.dereference(e2formula))
    return smt.And(*conjuncts)
  elif isinstance(expr2, list) or isinstance(expr2, tuple):
    conjuncts = []
    if util.is_any(e1formula):
      conjuncts.append(util.is_reference(e1formula))
      conjuncts.append(util.is_list(util.dereference(e1formula)))
    conjuncts.append(util.get_list_length(
      util.dereference(e1formula)) == len(expr2))
    for idx, item in enumerate(expr2):
      eq_test: SymbolicValue = expr1[idx] == item
      conjuncts.append(eq_test.get_formula())
    if isinstance(expr2, list):
      conjuncts.append(util.get_list_mutable(util.dereference(e1formula)))
    else:
      assert isinstance(expr2, tuple)
      conjuncts.append(
        smt.Not(util.get_list_mutable(util.dereference(e1formula))))
    return smt.And(*conjuncts)
  else:
    raise NotImplementedError


def handle_eq(sv: SymbolicValue, other: Union[SymbolicValue, int, bool, float, list, object], op: Operations) -> SymbolicValue:
  """
  Handler for `__eq__` and `__ne__` on symbolic values.
  """
  if not isinstance(other, SymbolicValue) and \
          (type(other) is int or type(other) is bool or type(other) is float or other is None or type(other) is str):
    other = factories.lift_value(other)

  # If both operands are numeric values or booleans
  if isinstance(other, SymbolicValue) and \
          (type(sv.get_value()) is int or type(sv.get_value()) is float or type(sv.get_value()) is bool) and \
          (type(other.get_value()) is int or type(other.get_value()) is float or type(other.get_value()) is bool):
    # This ensures that we coerce the types and that they aren't `any`!
    sv, other = util.convert_both_halves(sv, other)
    # Need to handle float equality differently
    if sv.get_formula().sort() == smt.Float64():
      # For Float64, we use fpEQ
      eq_expr = smt.fpEQ(sv.get_formula(), other.get_formula())
    elif sv.get_formula().sort().name() == "exreal":
      # For ExReal, we need to explicitly check for NaN
      # If one of the arguments is NaN, return false, otherwise just check for equality
      eq_expr = sv.get_formula() == other.get_formula()
      eq_expr = smt.If(
        smt.Or(util.is_nan(sv.get_formula()),
               util.is_nan(other.get_formula())),
          smt.BoolVal(False),
          eq_expr)
    else:
      # For everything else, we can just compare for equality
      eq_expr = sv.get_formula() == other.get_formula()
    # Check EQ vs. NEQ
    if op == Operations.EQ:
      return makeSymbolicValue(v=sv.get_value() == other.get_value(), formula=eq_expr)
    else:
      return makeSymbolicValue(v=sv.get_value() != other.get_value(), formula=smt.Not(eq_expr))
  # If both operands are a list or tuple and the right operand is a symbolic list or tuple
  elif (type(sv.get_value()) is list and isinstance(other, SymbolicValue) and type(other.get_value()) is list) or \
          (type(sv.get_value()) is tuple and isinstance(other, SymbolicValue) and type(other.get_value()) is tuple):
    formula = generate_list_eq(sv, other)

    if op == Operations.EQ:
      return makeSymbolicValue(v=sv.get_value() == other.get_value(), formula=formula)
    else:
      return makeSymbolicValue(v=sv.get_value() != other.get_value(), formula=smt.Not(formula))
  # If both operands are a list or tuple and the right operand is a non-symbolic list or tuple
  elif (type(sv.get_value()) is list and not isinstance(other, SymbolicValue) and type(other) is list) or \
          (type(sv.get_value()) is tuple and not isinstance(other, SymbolicValue) and type(other) is tuple):
    formula = generate_list_eq(sv, other)

    if op == Operations.EQ:
      return makeSymbolicValue(v=sv.get_value() == other, formula=formula)
    else:
      return makeSymbolicValue(v=sv.get_value() != other, formula=smt.Not(formula))
  # If both operands are a set and the right operand is a symbolic set
  elif type(sv.get_value()) is set and isinstance(other, SymbolicValue) and type(other.get_value()) is set:
    formula = generate_set_eq(sv, other)

    if op == Operations.EQ:
      return makeSymbolicValue(v=sv.get_value() == other.get_value(), formula=formula)
    else:
      return makeSymbolicValue(v=sv.get_value() != other.get_value(), formula=smt.Not(formula))
  # If both operands are a set and the right operand is a non-symbolic set
  elif type(sv.get_value()) is set and not isinstance(other, SymbolicValue) and type(other) is set:
    formula = generate_set_eq(sv, other)

    if op == Operations.EQ:
      return makeSymbolicValue(v=sv.get_value() == other, formula=formula)
    else:
      return makeSymbolicValue(v=sv.get_value() != other, formula=smt.Not(formula))
  # If both operands are a dict and the right operand is a symbolic dict
  elif type(sv.get_value()) is dict and isinstance(other, SymbolicValue) and type(other.get_value()) is dict:
    formula = generate_dict_eq(sv, other)

    if op == Operations.EQ:
      return makeSymbolicValue(v=sv.get_value() == other.get_value(), formula=formula)
    else:
      return makeSymbolicValue(v=sv.get_value() != other.get_value(), formula=smt.Not(formula))
  # If both operands are a dict and the right operand is a non-symbolic dict
  elif type(sv.get_value()) is dict and not isinstance(other, SymbolicValue) and type(other) is dict:
    formula = generate_dict_eq(sv, other)

    if op == Operations.EQ:
      return makeSymbolicValue(v=sv.get_value() == other, formula=formula)
    else:
      return makeSymbolicValue(v=sv.get_value() != other, formula=smt.Not(formula))
  # Equality between either two object types or two distinct types, where both sides are symbolic
  elif op == Operations.EQ and isinstance(other, SymbolicValue):
    return makeSymbolicValue(v=sv.get_value() == other.get_value(),
                             formula=smt.And(util.are_same_any_type(sv.get_formula(), other.get_formula()),
                                             util.lift_expr_to_any(sv.get_formula()) == util.lift_expr_to_any(other.get_formula())))
  # Equality between either two object types or two distinct types, where only the left side is symbolic
  elif op == Operations.EQ and not isinstance(other, SymbolicValue):
    # Comparing a symbolic and a concrete object always returns false for equality
    if util.is_not_builtin(type(sv.get_value())) and util.is_not_builtin(type(other)):
      return makeSymbolicValue(v=sv.get_value() == other, formula=smt.BoolVal(False))
    # Otherwise they are different types, for now just put a constraint that they are the same type
    else:
      return makeSymbolicValue(v=sv.get_value() == other,
                               formula=util.is_type(sv.get_formula(), type(other)))
  # Inquality between either two object types or two distinct types, where both sides are symbolic
  elif op == Operations.NE and isinstance(other, SymbolicValue):
    return makeSymbolicValue(v=sv.get_value() != other.get_value(),
                             formula=smt.Not(smt.And(util.are_same_any_type(sv.get_formula(), other.get_formula()),
                                             util.lift_expr_to_any(sv.get_formula()) == util.lift_expr_to_any(other.get_formula()))))
  # Inequality between either two object types or two distinct types, where only the left side is symbolic
  elif op == Operations.NE and not isinstance(other, SymbolicValue):
    # Comparing a symbolic and a concrete object always returns true for inequality
    if util.is_not_builtin(type(sv.get_value())) and util.is_not_builtin(type(other)):
      return makeSymbolicValue(v=sv.get_value() != other, formula=smt.BoolVal(True))
    # Otherwise they are different types, for now just put a constraint that they are the same type
    else:
      return makeSymbolicValue(v=sv.get_value() != other,
                               formula=smt.Not(util.is_type(sv.get_formula(), type(other))))
  # Should never be reached
  else:
    raise NotImplementedError


def handle_generic_op(sv: SymbolicValue, op: Operations, *args, **kwargs) -> SymbolicValue:
  """
  Handler for generic operations on symbolic values.
  Generic operations are those which are not tied to any specific type (e.g., `__eq__`).
  """
  if op == Operations.SBOOL:
    return makeSymbolicValue(v=bool(sv.get_value()), formula=sv.get_formula())
  elif op == Operations.EQ or op == Operations.NE:
    return handle_eq(sv, args[0], op)

  raise NotImplementedError
