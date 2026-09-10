# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from typing import Union, Any, Type, Callable, Optional
from types import ModuleType

from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue
from symbex.symbolic.symbolic import SymbolicValueImpl
import symbex.globals as globals
import symbex.overrides.util as util
import symbex.symbolic.util as symutil
import symbex.astmanip as astmanip

import logging

from symbex.smtlib import get_smt_lib
smt = get_smt_lib()

old_len = len
old_range = range

logger = logging.getLogger(__name__)


def intercept_range(*args) -> Union[range, util.RangeIterator]:
  """
  Interceptor for `range` in tested code.

  Generates a path condition (if possible) to mark whether or not at least one iteration of the `range` is taken.
  """
  rangeHelper = util.RangeHelper([*args])
  args = args[2:]

  # If no symbolic variables are seen, just execute the loop as normal
  # This is necessary because symbolic_range is sometimes called inside of PySMT! (Byproduct of injecting this into the builtins)
  if not rangeHelper.has_any_symbolic():
    return old_range(*args)

  # First, we want to mark some path conditions
  # These path conditions basically insert a condition to control whether the loop executes any iterations or not
  # For example, "range(0, x)" will record the path "0 >= x".
  # If false, the loop executes at least once. If true, the loop doesn't execute
  if old_len(args) == 1 and isinstance(args[0], SymbolicValue) and args[0].typ() is int:
    globals.globals.record_path(0 >= args[0])
  elif old_len(args) > 1 and isinstance(args[0], SymbolicValue) and args[0].typ() is int:
    globals.globals.record_path(args[0] >= args[1])
  elif old_len(args) > 1 and isinstance(args[1], SymbolicValue) and args[1].typ() is int:
    globals.globals.record_path(args[0] >= args[1])
  elif old_len(args) > 2 and isinstance(args[2], SymbolicValue) and args[2].typ() is int:
    globals.globals.record_path(args[0] + args[2] > args[1])

  # The starting value is usually a symbolic iterator so that we can peer into the body of the loop
  # The only time the starting value is not an iterator is if the only symbolic value received into the "range"
  # is for the stride.
  starting_value = rangeHelper.capture_symbolic_iterator()
  ending_value = rangeHelper.capture_end_value()
  stride = rangeHelper.capture_stride()

  lineno = rangeHelper.lineno
  colno = rangeHelper.colno

  return util.RangeIterator(lineno, colno, starting_value, ending_value, stride)


def intercept_len(*args) -> Union[SymbolicValue, int]:
  """
  Interceptor for `len` in tested code.

  Permits returning a `SymbolicValue` from `len` instead of requiring an `int` to be returned.
  """
  if isinstance(args[0], SymbolicValue):
    return args[0].__len__()
  else:
    return old_len(*args)


def intercept_int(*args) -> Union[SymbolicValue, int]:
  """
  Interceptor for `int` in tested code.

  Permits returning a `SymbolicValue` from `int` instead of requiring an `int` to be returned.
  """
  if isinstance(args[0], SymbolicValue):
    return args[0].__int__()
  else:
    return int(*args)


def intercept_float(*args) -> Union[SymbolicValue, float]:
  """
  Interceptor for `float` in tested code.

  Permits returning a `SymbolicValue` from `float` instead of requiring an `float` to be returned.
  """
  if isinstance(args[0], SymbolicValue):
    return args[0].__float__()
  else:
    return float(*args)


def intercept_if(lineno: int, colno: int, condition: Union[SymbolicValue, bool]) -> bool:
  """
  Interceptor for `if` in tested code.

  Keeps track of which branches have and have not been taken for further analysis.
  """
  logging.debug(condition)
  key = lineno, colno
  if isinstance(condition, SymbolicValue):
    globals.globals.record_path(condition)
    taken = bool(condition.v)
    util.mark_taken(key, taken)
    logging.debug(taken)
    return taken
  else:
    taken = bool(condition)
    util.mark_taken(key, taken)
    logging.debug(taken)
    return taken


def intercept_open(filename: Union[SymbolicValue, str], mode: Union[SymbolicValue, str] = 'r') -> util.SymbolicIO:
  if isinstance(filename, SymbolicValue):
    isinst_pred = intercept_isinstance(filename, str)
    if isinstance(isinst_pred, SymbolicValue):
      globals.globals.record_path(isinst_pred)
      globals.globals.record_path(filename != "")

  if isinstance(mode, SymbolicValue):
    pass  # Figure out the path conditions here later

  return util.SymbolicIO(filename)


def intercept_while(lineno: int, colno: int, condition: Union[SymbolicValue, bool]) -> bool:
  """
  Interceptor for `while` in tested code.

  Keeps track of whether the loop has been taken or exited for further analysis.
  """
  key = lineno, colno
  if isinstance(condition, SymbolicValue):
    globals.globals.record_path(condition)
    taken = bool(condition.v)
    util.mark_taken(key, taken)
    return taken
  else:
    taken = bool(condition)
    util.mark_taken(key, taken)
    return taken


def intercept_in(var: Any, *comparators) -> Union[bool, SymbolicValue]:
  """
  Interceptor for `in` in tested code.

  Calls `__contains__` on symbolic objects.
  Permits returning a `SymbolicValue` from `in` instead of requiring a `bool` to be returned.
  """
  if old_len(comparators) > 1:
    raise NotImplementedError
  else:
    comparator = comparators[0]

    contains = getattr(comparator, "__contains__", None)
    if callable(contains):
      return comparator.__contains__(var)
    else:
      return var in comparator


def intercept_isinstance(var: Union[Any, SymbolicValue], clas: Type) -> Union[bool, SymbolicValue]:
  """
  Interceptor for `isinstance` in tested code.

  For symbolic values, generates a new symbolic value representing the `isinstance` check.
  """
  if clas == intercept_int:
    clas = int
  elif clas == intercept_float:
    clas = float

  if isinstance(var, SymbolicValue):
    formula = var.get_formula()
    concrete = isinstance(var.get_value(), clas)

    if not symutil.is_any(formula):
      formula = symutil.lift_expr_to_any(formula)

    if clas.__name__ in astmanip.get_all_classes().keys():
      newformula = smt.And(symutil.is_reference(formula), symutil.is_object(symutil.dereference(
        formula)), symutil.class_type_recognizer(clas.__name__)(symutil.get_object_type(symutil.dereference(formula))))
      return makeSymbolicValue(v=concrete, formula=newformula)
    else:
      if clas is int:
        return makeSymbolicValue(v=concrete, formula=symutil.is_int(formula))
      elif clas is bool:
        return makeSymbolicValue(v=concrete, formula=symutil.is_bool(formula))
      elif clas is float:
        return makeSymbolicValue(v=concrete, formula=symutil.is_float(formula))
      elif clas is str:
        return makeSymbolicValue(v=concrete, formula=symutil.is_string(formula))
      elif clas is list:
        return makeSymbolicValue(v=concrete, formula=smt.And(
          symutil.is_reference(formula), symutil.is_list(symutil.dereference(formula)), symutil.get_list_mutable(symutil.dereference(formula))))
      elif clas is tuple:
        return makeSymbolicValue(v=concrete, formula=smt.And(
          symutil.is_reference(formula), symutil.is_list(symutil.dereference(formula)), smt.Not(symutil.get_list_mutable(symutil.dereference(formula)))))
      elif clas is dict:
        return makeSymbolicValue(v=concrete, formula=smt.And(symutil.is_reference(formula), symutil.is_dict(symutil.dereference(formula))))
      elif clas is set:
        return makeSymbolicValue(v=concrete, formula=smt.And(symutil.is_reference(formula), symutil.is_set(symutil.dereference(formula))))
      else:
        return concrete
  else:
    return isinstance(var, clas)


def intercept_function_call(lineno: int, colno: int, function: Callable[..., Optional[Any]], *args, **kwargs) -> Optional[Any]:
  """
  Intercepts function calls in tested code.

  Used to inject conditions for eventual integration with Slasher tool.
  Also will be used for addressing scalability issues.
  """
  if function.__name__ != "callable_wrapper":
    func_name = function.__name__
    self = function.__self__ if hasattr(function, "__self__") else None
  elif function.__name__ == "callable_wrapper" and function.__closure__ is not None:
    func_name = function.__closure__[0].cell_contents.__name__
    self = function.__closure__[1].cell_contents
  else:
    func_name = "!UNKNOWN_FUNCTION_NAME!"
    self = None

  if isinstance(self, SymbolicValue):
    self = self.get_value()

  conc_args = [arg.get_value() if isinstance(arg, SymbolicValue)
               and arg is not SymbolicValue and arg is not SymbolicValueImpl else arg for arg in args]

  retval = function(*args, **kwargs)
  if isinstance(retval, SymbolicValue) and not retval is SymbolicValue and not retval is SymbolicValueImpl:
    conc_retval = retval.get_value()
  else:
    conc_retval = retval

  util.check_function_yaml(func_name, conc_args, args, conc_retval, retval)

  return retval


def install_overrides(module: ModuleType) -> None:
  module.__dict__["len"] = intercept_len
  module.__dict__["int"] = intercept_int
  module.__dict__["float"] = intercept_float
  module.__dict__["open"] = intercept_open
  module.__dict__[
    "_symbex_intercept_for_range"] = intercept_range
  module.__dict__[
    "_symbex_intercept_in_operator"] = intercept_in
  module.__dict__[
    "_symbex_intercept_atomic_if_condition"] = intercept_if
  module.__dict__[
    "_symbex_intercept_atomic_while_condition"] = intercept_while
  module.__dict__[
    "_symbex_intercept_isinstance_call"] = intercept_isinstance
  module.__dict__[
    "_symbex_intercept_function_call"] = intercept_function_call
