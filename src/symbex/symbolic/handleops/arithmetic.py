# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from typing import Any
import logging
import traceback

import symbex.symbolic.factories as factories
import symbex.symbolic.util as util
from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue
from symbex.symbolic.operations import Operations
from symbex.globals.globals import record_path, make_assertion
from typing import Callable, Any, List, Tuple
from math import nan, inf, isnan, isfinite

from symbex.smtlib import get_smt_lib, ExprRef, configured_float_theory, FloatTheory
smt = get_smt_lib()

logger = logging.getLogger(__name__)


def is_float_64(item) -> bool:
  try:
    # This works if we're operating on an SMT formula
    return item.sort() == smt.Float64()
  except:
    # This is triggered if we are operating on the concrete half
    return False


def is_exreal(item) -> bool:
  try:
    # This works if we're operating on an SMT formula
    return item.sort().name() == "exreal"
  except:
    # This is triggered if we are operating on the concrete half
    return False


def build_inf_term_prop(l, r, *args: Tuple[float, float, float]) -> ExprRef:
  """
  Builts an SMT term which is a series of If-Then-Else expressions, building up the rules around ExReal operations.

  - `l` - the left-hand operand
  - `r` - the right-hand operand
  - `args` - a series of 3-tuples specifying the result from the left- and right-hand operands.

  This function propagates NaN, so the default case is to return NaN.

  `args` processing:

  - `0.0` - Represents the literal `0`
  - `1.0` - Represents a positive finite number
  - `-1.0` - Represents a negative finite number
  - `NaN` - Represents not-a-number
  - `+Inf` - Represents positive infinity
  - `-Inf` - Represents negative infinity

  Example:

  ```
  build_inf_term(lhs, rhs, (inf, inf, inf), (inf, -inf, nan), (1.0, inf, -inf))
  ```

  builds the following term:

  ```
  If(And(is_inf(lhs), is_inf(rhs)),
     create_inf,
     If(And(is_inf(lhs), is_neginf(rhs)),
        create_nan,
        If(And(lhs > 0, is_inf(rhs)),
           create_neginf,
           create_nan)))
  ```
  """
  term = util.nan

  def convert_constant(expr, constant: float) -> ExprRef:
    if constant == 0.0:
      return smt.And(util.is_finite(expr), util.float_sort.accessor(0, 0)(expr) == 0)
    if constant == 1.0:
      return smt.And(util.is_finite(expr), util.float_sort.accessor(0, 0)(expr) > 0)
    if constant == -1.0:
      return smt.And(util.is_finite(expr), util.float_sort.accessor(0, 0)(expr) < 0)
    elif isnan(constant):
      return util.is_nan(expr)
    elif constant == inf:
      return util.is_pos_inf(expr)
    elif constant == -inf:
      return util.is_neg_inf(expr)
    else:
      raise NotImplementedError

  for (p1, p2, res) in reversed(args):
    cp1 = convert_constant(l, p1)
    cp2 = convert_constant(r, p2)

    if isnan(res):
      cres = util.nan
    elif res == inf:
      cres = util.pos_inf
    elif res == -inf:
      cres = util.neg_inf
    elif res == 0.0:
      cres = util.float_val(0.0)
    else:
      raise NotImplementedError

    term = smt.If(smt.And(cp1, cp2), cres, term)

  return term


def build_inf_term_comp(l, r, *args: Tuple[float, float]) -> ExprRef:
  """
  Builts an SMT term which is a disjunction of conjunctions, building up the rules around ExReal operations.

  - `l` - the left-hand operand
  - `r` - the right-hand operand
  - `args` - a series of 2-tuples specifying which pairs of operands can return True.

  This function compares against NaN, so the default case is to return False.

  `args` processing:

  - `0.0` - Represents a finite number
  - `NaN` - Represents not-a-number
  - `+Inf` - Represents positive infinity
  - `-Inf` - Represents negative infinity

  Example:

  ```
  build_inf_term(lhs, rhs, (inf, -inf), (0.0, -inf), (inf, 0.0))
  ```

  builds the following term:

  ```
  Or(And(is_inf(lhs), is_neginf(rhs)),
     And(is_finite(lhs), is_neginf(rhs)),
     And(is_inf(lhs), is_finite(rhs))
  ```
  """
  terms: List[ExprRef] = []

  def convert_constant(expr, constant: float) -> ExprRef:
    if constant == 0.0:
      return util.is_finite(expr)
    elif isnan(constant):
      return util.is_nan(expr)
    elif constant == inf:
      return util.is_pos_inf(expr)
    elif constant == -inf:
      return util.is_neg_inf(expr)
    else:
      raise NotImplementedError

  for (p1, p2) in reversed(args):
    cp1 = convert_constant(l, p1)
    cp2 = convert_constant(r, p2)

    terms.append(smt.And(cp1, cp2))

  return smt.Or(*terms)


def exreal_prop_op(l, r, op: Callable[[Any, Any], Any], opl: Operations):
  """
  Handles ExReal operations where NaNs are propagated.
  """
  if opl == Operations.ADD:
    inf_term = build_inf_term_prop(
      l, r,
      (inf, inf, inf),
      (inf, -inf, nan),
      (-inf, inf, nan),
      (inf, 0.0, inf),
      (-inf, 0.0, -inf),
      (0.0, inf, inf),
      (0.0, -inf, -inf),
      (inf, 1.0, inf),
      (-inf, 1.0, -inf),
      (1.0, inf, inf),
      (1.0, -inf, -inf),
      (inf, -1.0, inf),
      (-inf, -1.0, -inf),
      (-1.0, inf, inf),
      (-1.0, -inf, -inf))
  elif opl == Operations.SUB:
    inf_term = build_inf_term_prop(
      l, r,
      (inf, inf, nan),
      (inf, -inf, inf),
      (-inf, inf, -inf),
      (inf, 0.0, inf),
      (-inf, 0.0, -inf),
      (0.0, inf, -inf),
      (0.0, -inf, inf),
      (inf, 1.0, inf),
      (-inf, 1.0, -inf),
      (1.0, inf, -inf),
      (1.0, -inf, inf),
      (inf, -1.0, inf),
      (-inf, -1.0, -inf),
      (-1.0, inf, -inf),
      (-1.0, -inf, inf))
  elif opl == Operations.MUL:
    inf_term = build_inf_term_prop(
      l, r,
      (inf, inf, inf),
      (inf, -inf, -inf),
      (-inf, inf, -inf),
      (inf, 0.0, nan),
      (-inf, 0.0, nan),
      (0.0, inf, nan),
      (0.0, -inf, nan),
      (inf, 1.0, inf),
      (-inf, 1.0, -inf),
      (1.0, inf, inf),
      (1.0, -inf, -inf),
      (inf, -1.0, -inf),
      (-inf, -1.0, inf),
      (-1.0, inf, -inf),
      (-1.0, -inf, inf))
  elif opl == Operations.TRUEDIV:
    inf_term = build_inf_term_prop(
      l, r,
      (inf, inf, nan),
      (inf, -inf, nan),
      (-inf, inf, nan),
      (inf, 0.0, nan),
      (-inf, 0.0, nan),
      (0.0, inf, 0.0),
      (0.0, -inf, 0.0),
      (inf, 1.0, inf),
      (-inf, 1.0, -inf),
      (1.0, inf, 0.0),
      (1.0, -inf, 0.0),
      (inf, -1.0, -inf),
      (-inf, -1.0, inf),
      (-1.0, inf, 0.0),
      (-1.0, -inf, 0.0))
  else:
    inf_term = util.nan

  return smt.If(
    # if l and r are both finite numbers
    smt.And(
      util.is_finite(l),
      util.is_finite(r)),
    # perform the operation
    util.float_sort.constructor(0)(
      op(util.float_sort.accessor(0, 0)(l),
         util.float_sort.accessor(0, 0)(r))),
    smt.If(
      # if either l or r is a NaN
      smt.Or(
        util.is_nan(l),
        util.is_nan(r)),
      # propagate NaN
      util.nan,
      # correct behavior for infinity based off the current operation
      inf_term))


def exreal_comp_op(l, r, op: Callable[[Any, Any], Any], opl: Operations):
  """
  Handles ExReal operations around comparison.
  """
  if opl == Operations.GT:
    inf_term = build_inf_term_comp(
      l, r,
      (inf, -inf),
      (inf, 0.0),
      (0.0, -inf))
  elif opl == Operations.GE:
    inf_term = build_inf_term_comp(
      l, r,
      (inf, -inf),
      (inf, inf),
      (inf, 0.0),
      (0.0, -inf),
      (-inf, -inf))
  elif opl == Operations.LT:
    inf_term = build_inf_term_comp(
      l, r,
      (-inf, inf),
      (0.0, inf),
      (-inf, 0.0))
  elif opl == Operations.LE:
    inf_term = build_inf_term_comp(
      l, r,
      (-inf, inf),
      (inf, inf),
      (0.0, inf),
      (-inf, 0.0),
      (-inf, -inf))
  else:
    inf_term = smt.BoolVal(False)

  return smt.If(
    # if l and r are both finite numbers
    smt.And(
      util.is_finite(l),
      util.is_finite(r)),
    # perform the operation
    op(util.float_sort.accessor(0, 0)(l),
       util.float_sort.accessor(0, 0)(r)),
    smt.If(
      # if either l or r is a NaN
      smt.Or(
        util.is_nan(l),
        util.is_nan(r)),
      # propagate NaN
      smt.BoolVal(False),
      # correct behavior for infinity based off the current operation
      inf_term))


def add(l, r):
  if is_float_64(l) and is_float_64(r):
    return smt.fpAdd(smt.RNE(), l, r)
  elif is_exreal(l) and is_exreal(r):
    return exreal_prop_op(l, r, (lambda l, r: l + r), Operations.ADD)
  else:
    return l + r


def sub(l, r):
  if is_float_64(l) and is_float_64(r):
    return smt.fpSub(smt.RNE(), l, r)
  elif is_exreal(l) and is_exreal(r):
    return exreal_prop_op(l, r, (lambda l, r: l - r), Operations.SUB)
  else:
    return l - r


def mul(l, r):
  if is_float_64(l) and is_float_64(r):
    return smt.fpMul(smt.RNE(), l, r)
  elif is_exreal(l) and is_exreal(r):
    return exreal_prop_op(l, r, (lambda l, r: l * r), Operations.MUL)
  else:
    return l * r


def div(l, r):
  if is_float_64(l) and is_float_64(r):
    return smt.fpDiv(smt.RNE(), l, r)
  elif is_exreal(l) and is_exreal(r):
    return exreal_prop_op(l, r, (lambda l, r: l / r), Operations.TRUEDIV)
  else:
    return l / r


def gt(l, r):
  if is_float_64(l) and is_float_64(r):
    return smt.fpGT(l, r)
  elif is_exreal(l) and is_exreal(r):
    return exreal_comp_op(l, r, (lambda l, r: l > r), Operations.GT)
  else:
    return l > r


def lt(l, r):
  if is_float_64(l) and is_float_64(r):
    return smt.fpLT(l, r)
  elif is_exreal(l) and is_exreal(r):
    return exreal_comp_op(l, r, (lambda l, r: l < r), Operations.LT)
  else:
    return l < r


def ge(l, r):
  if is_float_64(l) and is_float_64(r):
    return smt.fpGEQ(l, r)
  elif is_exreal(l) and is_exreal(r):
    return exreal_comp_op(l, r, (lambda l, r: l >= r), Operations.GE)
  else:
    return l >= r


def le(l, r):
  if is_float_64(l) and is_float_64(r):
    return smt.fpLEQ(l, r)
  elif is_exreal(l) and is_exreal(r):
    return exreal_comp_op(l, r, (lambda l, r: l <= r), Operations.LE)
  else:
    return l <= r


binary_op_lambdas = {
    Operations.ADD: add,
    Operations.RADD: lambda r, l: add(l, r),
    Operations.SUB: sub,
    Operations.RSUB: lambda r, l: sub(l, r),
    Operations.MUL: mul,
    Operations.RMUL: lambda r, l: mul(l, r),
    Operations.TRUEDIV: div,
    Operations.RTRUEDIV: lambda r, l: div(l, r),
    Operations.FLOORDIV: lambda l, r: l // r,
    Operations.RFLOORDIV: lambda r, l: l // r,
    Operations.GT: gt,
    Operations.LT: lt,
    Operations.GE: ge,
    Operations.LE: le
}

newvar_id: int = 0


def handle_multiply(sv: SymbolicValue, *args) -> SymbolicValue:
  global newvar_id

  if isinstance(sv, SymbolicValue) and util.is_any(sv.get_formula()):
    record_path(makeSymbolicValue(v=type(sv.get_value()) is int or
                                  type(sv.get_value()) is float or
                                  type(sv.get_value()) is bool or
                                  type(sv.get_value()) is list or
                                  type(sv.get_value()) is str,
                                  formula=smt.Or(
        util.is_int(sv.get_formula()),
        util.is_float(sv.get_formula()),
        util.is_bool(sv.get_formula()),
        util.is_string(sv.get_formula()),
        smt.And(
          util.is_reference(sv.get_formula()),
          util.is_list(util.dereference(sv.get_formula()))))))

  assert type(sv.get_value()) is int or \
      type(sv.get_value()) is float or \
      type(sv.get_value()) is bool or \
      type(sv.get_value()) is list or \
      type(sv.get_value()) is str

  if type(sv.get_value()) is int or \
          type(sv.get_value()) is float or \
          type(sv.get_value()) is bool:
    return handle_regular_op(sv, Operations.MUL, *args)
  else:
    assert type(sv.get_value()) is list or \
      type(sv.get_value()) is str

    other: SymbolicValue = args[0]

    if isinstance(other, SymbolicValue) and util.is_any(other.get_formula()):
      record_path(makeSymbolicValue(v=type(other.get_value()) is int or
                                    type(other.get_value()) is bool,
                                    formula=smt.Or(
        util.is_int(other.get_formula()),
        util.is_bool(other.get_formula()))))

    else:
      other = factories.lift_value(other)

    assert type(other.get_value()) is int or \
        type(other.get_value()) is bool

    sv_value = sv.get_value()
    other_value = other.get_value()
    sv_formula = sv.get_formula()
    other_formula = other.get_formula()

    if util.is_any(other_formula):
      other_formula = smt.If(util.is_bool(other_formula), smt.If(
        util.get_bool(other_formula), 1, 0), util.get_int(other_formula))
      record_path(makeSymbolicValue(
        v=other_value >= 0, formula=other_formula >= 0))
      assert other_value >= 0
    else:
      assert other_formula.sort() == smt.IntSort()

    if type(sv.get_value()) is str:
      newstring = smt.String("__newstring" + str(newvar_id))
      newvar_id += 1
      i = smt.Int("i")
      string = util.get_string(sv_formula)
      make_assertion(makeSymbolicValue(v=True, formula=smt.Length(
        newstring) == smt.Length(string) * other_formula))
      make_assertion(makeSymbolicValue(v=True, formula=smt.ForAll([i], smt.Implies(smt.And(0 <= i, i < other_formula),
                                                                                   smt.SubString(newstring, i * smt.Length(string), smt.Length(string)) == string))))
      return makeSymbolicValue(v=sv_value * other_value, formula=util.lift_expr_to_any(newstring))
    else:
      assert type(sv.get_value()) is list
      raise NotImplementedError


def handle_regular_op(sv: SymbolicValue, op: Operations, *args, **kwargs) -> SymbolicValue:
  if isinstance(sv, SymbolicValue) and util.is_any(sv.get_formula()):
    record_path(makeSymbolicValue(v=type(sv.get_value()) is int or
                                  type(sv.get_value()) is float or
                                  type(sv.get_value()) is bool,
                                  formula=smt.Or(
        util.is_int(sv.get_formula()),
        util.is_float(sv.get_formula()),
        util.is_bool(sv.get_formula()))))

  assert type(sv.get_value()) is int or \
      type(sv.get_value()) is float or \
      type(sv.get_value()) is bool

  other: SymbolicValue = args[0]

  if isinstance(other, SymbolicValue) and util.is_any(other.get_formula()):
    record_path(makeSymbolicValue(v=type(other.get_value()) is int or
                                  type(other.get_value()) is float or
                                  type(other.get_value()) is bool,
                                  formula=smt.Or(
        util.is_int(other.get_formula()),
        util.is_float(other.get_formula()),
        util.is_bool(other.get_formula()))))

  else:
    other = factories.lift_value(other)

  assert type(other.get_value()) is int or \
      type(other.get_value()) is float or \
      type(other.get_value()) is bool

  # Branch to catch zero-division
  if op in (Operations.TRUEDIV, Operations.RTRUEDIV, Operations.FLOORDIV, Operations.RFLOORDIV):
    # Get the concrete and symbolic parts of the denominator
    den = sv if op in (Operations.RTRUEDIV, Operations.RFLOORDIV) else other
    den = util.narrow_from_any_t(den, type(den.get_value()))
    den_value = den.get_value()
    den_formula = den.get_formula()

    # Branch on whether the denominator is zero
    zero = smt.RealVal(0.0) if den_formula.sort(
    ) == smt.RealSort() else smt.IntVal(0)
    record_path(makeSymbolicValue(
      v=(den_value != 0), formula=den_formula != zero))
    if den_value == 0:
      raise ZeroDivisionError

  # Handle floored division (not defined on symbolic types)
  if op in (Operations.FLOORDIV, Operations.RFLOORDIV):
    left, right = (other, sv) if op == Operations.RFLOORDIV else (sv, other)
    left, right = util.convert_both_halves(left, right)

    left_value, left_formula = left.get_value(), left.get_formula()
    right_value, right_formula = right.get_value(), right.get_formula()

    # Convert booleans to integers
    if left_formula.sort() == smt.BoolSort():
      # By convert_both_halves, we know that if left is bool, so is right
      left_formula = smt.If(left_formula, smt.IntVal(1), smt.IntVal(0))
      right_formula = smt.If(right_formula, smt.IntVal(1), smt.IntVal(0))

    # Now convert to reals for division
    if left_formula.sort() != smt.RealSort():
      # Again, both have the same sort so if one is not real, neither is
      left_formula = smt.ToReal(left_formula)
      right_formula = smt.ToReal(right_formula)

    # Get integer division result, then cast back to real if an input was nonintegral
    result_formula = smt.ToInt(left_formula / right_formula)
    if type(left_value) is float or type(right_value) is float:
      result_formula = smt.ToReal(result_formula)

    return makeSymbolicValue(v=left_value // right_value,
                             formula=util.lift_expr_to_any(result_formula))

  if (op in binary_op_lambdas):
    operation = binary_op_lambdas[op]

    if isinstance(other, SymbolicValue):
      try:
        sv, other = util.convert_both_halves(sv, other)
        sv_value = sv.get_value()
        other_value = other.get_value()
        sv_formula = sv.get_formula()
        other_formula = other.get_formula()

        if sv_formula.sort() == smt.BoolSort():
          sv_formula = smt.If(sv_formula, 1, 0)
        if other_formula.sort() == smt.BoolSort():
          other_formula = smt.If(other_formula, 1, 0)

        oper: ExprRef = util.lift_expr_to_any(
          operation(sv_formula, other_formula))
        return makeSymbolicValue(v=operation(sv_value, other_value), formula=oper)
      except:
        logger.debug(f"In handleint: {traceback.format_exc()}")
        # logger.debug(f"{sv.get_formula()}, {other.get_formula()}")
        raise NotImplementedError
    else:
      raise NotImplementedError

  else:
    raise NotImplementedError


def handle_int(sv: SymbolicValue) -> SymbolicValue:
  # For raw types, we can skip some of the extra branch conditions and directly lift them
  if not util.is_any(sv.get_formula()):
    expr = sv.get_formula()

    if expr.sort() == smt.IntSort():
      return makeSymbolicValue(v=int(sv.get_value()), formula=util.lift_expr_to_any(expr))

    if expr.sort() == util.float_sort:
      if configured_float_theory == FloatTheory.EXREAL:
        record_path(makeSymbolicValue(v=isfinite(sv.get_value()),
                    formula=util.is_finite(expr)))
      return makeSymbolicValue(v=int(sv.get_value()), formula=util.lift_expr_to_any(util.to_int(expr)))

    if expr.sort() == smt.BoolSort():
      return makeSymbolicValue(v=int(sv.get_value()), formula=util.lift_expr_to_any(smt.If(expr, 1, 0)))

    if smt.is_string(expr):
      # For strings, we need to duplicate the condition for validity used below
      record_path(makeSymbolicValue(v=(type(sv.get_value()) is not str) or sv.get_value().isdigit(),
                                    formula=smt.StrToInt(expr) != -1))
      return makeSymbolicValue(v=int(sv.get_value()),
                               formula=util.lift_expr_to_any(smt.StrToInt(expr)))

    # If we have a concrete sort but it's not one of int, real/fp, bool, or string, the conversion fails
    raise NotImplementedError

  # Otherwise, the value is an Any
  record_path(makeSymbolicValue(v=type(sv.get_value()) is int or type(sv.get_value()) is float or type(sv.get_value()) is bool or type(sv.get_value()) is str,
                                formula=smt.Or(util.is_int(sv.get_formula()), util.is_float(sv.get_formula()), util.is_bool(sv.get_formula()), util.is_string(sv.get_formula()))))

  record_path(makeSymbolicValue(v=not type(sv.get_value()) is str or sv.get_value().isdigit(),
                                formula=smt.Implies(util.is_string(sv.get_formula()), smt.StrToInt(util.get_string(sv.get_formula())) != -1)))

  assert type(sv.get_value()) is int or \
      type(sv.get_value()) is float or \
      type(sv.get_value()) is bool or \
      type(sv.get_value()) is str

  return makeSymbolicValue(v=int(sv.get_value()),
                           formula=util.lift_expr_to_any(smt.If(util.is_int(sv.get_formula()), util.get_int(sv.get_formula()),
                                                                smt.If(util.is_float(sv.get_formula()), util.to_int(util.get_float(
                                                                    sv.get_formula())),
                               smt.If(util.is_bool(sv.get_formula()), smt.If(util.get_bool(sv.get_formula()), 1, 0),
                                                                    smt.StrToInt(util.get_string(sv.get_formula())))))))


def handle_float(sv: SymbolicValue) -> SymbolicValue:
  # Again, for raw types, we can skip some of the extra branch conditions and directly lift them
  if not util.is_any(sv.get_formula()):
    expr = sv.get_formula()

    if expr.sort() == util.float_sort:
      return makeSymbolicValue(v=float(sv.get_value()), formula=util.lift_expr_to_any(expr))

    if expr.sort() == smt.IntSort():
      return makeSymbolicValue(v=float(sv.get_value()), formula=util.lift_expr_to_any(util.to_float(expr)))

    if expr.sort() == smt.BoolSort():
      return makeSymbolicValue(v=float(sv.get_value()), formula=util.lift_expr_to_any(smt.If(expr, util.float_val(1.0), util.float_val(0.0))))

    if smt.is_string(expr):
      # For strings, we need to duplicate the condition for validity used below
      record_path(makeSymbolicValue(v=(type(sv.get_value()) is not str) or sv.get_value().isdigit(),
                                    formula=smt.StrToInt(expr) != -1))
      return makeSymbolicValue(v=float(sv.get_value()),
                               formula=util.lift_expr_to_any(util.to_float(smt.StrToInt(expr))))

    # If we have a concrete sort but it's not one of int, real/fp, bool, or string, the conversion fails
    raise NotImplementedError

  # Otherwise, the value is an Any
  record_path(makeSymbolicValue(v=type(sv.get_value()) is int or type(sv.get_value()) is float or type(sv.get_value()) is bool or type(sv.get_value()) is str,
                                formula=smt.Or(util.is_int(sv.get_formula()), util.is_float(sv.get_formula()), util.is_bool(sv.get_formula()), util.is_string(sv.get_formula()))))

  record_path(makeSymbolicValue(v=not type(sv.get_value()) is str or sv.get_value().isdigit(),
                                formula=smt.Implies(util.is_string(sv.get_formula()), smt.StrToInt(util.get_string(sv.get_formula())) != -1)))

  assert type(sv.get_value()) is int or \
      type(sv.get_value()) is float or \
      type(sv.get_value()) is bool or \
      type(sv.get_value()) is str

  return makeSymbolicValue(v=float(sv.get_value()),
                           formula=util.lift_expr_to_any(smt.If(util.is_int(sv.get_formula()), util.to_float(util.get_int(sv.get_formula())), smt.If(util.is_float(sv.get_formula()),
                                                                                                                                                     util.get_float(
                               sv.get_formula()),
                               smt.If(util.is_bool(sv.get_formula()),
                                      smt.If(util.get_bool(sv.get_formula()),
                                             util.float_val(
                                          1.0),
                                   util.float_val(0.0)),
                               util.to_float(smt.StrToInt(util.get_string(sv.get_formula()))))))))


def handle_arithmetic_op(sv: SymbolicValue, op: Operations, *args, **kwargs) -> SymbolicValue:
  """
  Handler for arithmetic operations on symbolic values (such as those commonly performed on `int`, `float`, and `bool`).
  """
  if op == Operations.MUL:
    return handle_multiply(sv, *args)
  elif op == Operations.INT:
    return handle_int(sv)
  elif op == Operations.FLOAT:
    return handle_float(sv)
  else:
    return handle_regular_op(sv, op, *args, **kwargs)
