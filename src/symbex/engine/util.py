# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from dataclasses import dataclass
from typing import List, Any, Dict, Optional, Tuple, Set, Union
from inspect import BoundArguments

from symbex.overrides.util import get_taken
from symbex.types.array import Array
from symbex.types.symbolicvalue import SymbolicValue
from symbex.engine.globalvar import GlobalVar
import symbex.lib as lib
import symbex.symbolic.util as util

import random
import logging
import traceback
import math

from symbex.smtlib import get_smt_lib, ModelRef, ExprRef, SetRef, Solver, configured_library, SMTLibrary
smt = get_smt_lib()

logger = logging.getLogger(__name__)


@dataclass
class TraceResult:
  input_args: BoundArguments  # Symbolic input arguments
  global_vars: Dict[GlobalVar, SymbolicValue]  # Symbolic global variables
  file_vars: Dict[Tuple[str, str], str]  # Concrete file contents
  path_condition: Optional[SymbolicValue]


class ExecutionDepthExceeded(Exception):
  def __init__(self, *args: object) -> None:
    super().__init__(*args)


class DuplicateInputConfiguration(Exception):
  def __init__(self, *args: object) -> None:
    super().__init__(*args)


def Solver_(timeout, *args, **kwargs) -> Solver:
  """
  Create a new solver object based on the currently configured SMT library.
  """
  solver = smt.Solver(*args, **kwargs)

  if configured_library == SMTLibrary.Z3:
    solver.set("timeout", timeout)
    solver.set("solver2_unknown", 2)
  elif configured_library == SMTLibrary.CVC5:
    solver.setOption("tlimit-per", timeout)
    solver.setOption("mbqi", True)

  return solver


def untaken_branches() -> List[Tuple[int, int]]:
  """
  Creates a list of all untaken branch locations in the tested module.
  Branches are only indexed if they are executed at least once
  (i.e., branches never hit at all are not registered as untaken).
  """
  history = get_taken()
  ret: List[Tuple[int, int]] = []

  for key, value in history.items():
    if value != (True, True):
      ret.append(key)

  return ret


def generate_arbitrary(depth: int) -> Any:
  """
  Generates an arbitrary Python object with a maximum nesting of `depth`.

  The following Python types are supported:
  - `int`
  - `float`
  - `list`
  - `None`
  - Objects which appear in the tested module
  """
  if depth > 0:
    if len(lib.get_all_fields()) > 0:
      type = random.choice([int, float, list, object, None])
    else:
      type = random.choice([int, float, list, None])
  else:
    type = random.choice([int, float, None])

  if type is None:
    return None
  elif type is int:
    return random.randint(-100, 100)
  elif type is float:
    return (random.random() - 0.5) * 200
  elif type is list:
    length = random.randint(0, 50)
    newlist = []
    for _ in range(length):
      newlist.append(generate_arbitrary(depth - 1))
    return newlist
  else:
    assert type is object
    possible_objects = [
      *map(lambda clas: lib.get_class(clas), util.get_all_classes().keys())]
    if len(possible_objects) == 0:
      possible_objects = [lib.get_class("object")]
    object_type = random.choice(possible_objects)
    newobj = object_type.__new__(object_type)
    for field in lib.get_all_fields():
      # Don't try to set an @property with no setter
      class_attr = getattr(object_type, field, None)
      if isinstance(class_attr, property) and class_attr.fset is None:
        continue

      if random.getrandbits(1):
        setattr(newobj, field, generate_arbitrary(depth - 1))
    return newobj


references: Dict[ExprRef, Any] = {}


def convert_reference(heap: ModelRef, reference: ExprRef, model: ModelRef) -> Any:
  """
  Converts an SMT reference value into a concrete Python object.

  May return either an object or a list.
  """
  global references

  if reference not in references:
    indexed = smt.simplify(heap[reference])
    try:
      if smt.simplify(util.is_list(indexed)):
        length = smt.simplify(util.get_list_length(indexed)).as_long()
        lst: Union[List[Any], Tuple[Any]] = []
        assert isinstance(lst, list)
        references[reference] = lst

        for i in range(length):
          item = convert_model(smt.simplify(
            util.get_list(indexed)[i]), model)
          lst.append(item)

        if not smt.simplify(util.get_list_mutable(indexed)):
          lst = tuple(lst)
          references[reference] = lst
      elif smt.simplify(util.is_object(indexed)):
        type = smt.simplify(util.get_object_type(indexed))
        constructor = util.get_class_type(type)
        assert constructor is not None
        obj = constructor.__new__(constructor)

        references[reference] = obj

        for field in lib.get_all_fields():
          # Don't try to set an @property with no setter
          class_attr = getattr(constructor, field, None)
          if isinstance(class_attr, property) and class_attr.fset is None:
            continue

          if smt.simplify(util.get_object_members(indexed)[smt.StringVal(field)]):
            item = convert_model(smt.simplify(
              util.get_object(indexed)[smt.StringVal(field)]), model)
            setattr(obj, field, item)
      elif smt.simplify(util.is_dict(indexed)):
        dct: Dict[Any, Any] = {}
        references[reference] = dct

        cardinality = smt.simplify(
          model.evaluate(util.get_dict_cardinality(util.heap[reference]))).as_long()

        for i in range(cardinality):
          key_raw = smt.simplify(util.get_dict_keys(indexed)[i])
          value_raw = smt.simplify(util.get_dict(indexed)[key_raw])
          key = convert_model(key_raw, model)
          value = convert_model(value_raw, model)

          dct[key] = value
      elif smt.simplify(util.is_set(indexed)):
        st: Set[Any] = set()
        references[reference] = st

        if configured_library == SMTLibrary.Z3:
          cardinality = smt.simplify(
            model.evaluate(util.bound(reference))).as_long()

          for i in range(cardinality):
            value_raw = smt.simplify(util.get_set(indexed)[i])
            value = convert_model(value_raw, model)

            st.add(value)
        else:
          values: SetRef = model.evaluate(util.get_set(indexed))
          assert isinstance(values, smt.SetRef)

          def recursively_solve_set(values: SetRef):
            if values.kind() == smt.Kind.SET_SINGLETON:
              value_raw = smt.simplify(values.arg(0))
              value = convert_model(value_raw, model)

              st.add(value)
            elif values.kind() == smt.Kind.SET_UNION:
              recursively_solve_set(smt.simplify(values.arg(0)))
              recursively_solve_set(smt.simplify(values.arg(1)))
            else:
              return

          recursively_solve_set(values)
      elif smt.simplify(util.is_intarray(indexed)):
        iarr: List[int] = []

        cardinality = smt.simplify(model.evaluate(smt.Length(
          util.get_intarray(util.heap[reference])))).as_long()

        for i in range(cardinality):
          value = smt.simplify(util.get_intarray(indexed)[i]).as_long()
          iarr.append(value)

        references[reference] = Array(int, len(iarr), iarr)
      elif smt.simplify(util.is_floatarray(indexed)):
        farr: List[float] = []

        cardinality = smt.simplify(model.evaluate(smt.Length(
          util.get_floatarray(util.heap[reference])))).as_long()

        for i in range(cardinality):
          value = convert_float(util.get_floatarray(indexed)[i])
          farr.append(value)

        references[reference] = Array(float, len(farr), farr)
      elif smt.simplify(util.is_boolarray(indexed)):
        barr: List[bool] = []

        cardinality = smt.simplify(model.evaluate(smt.Length(
          util.get_boolarray(util.heap[reference])))).as_long()

        for i in range(cardinality):
          value = bool(smt.simplify(util.get_boolarray(indexed)[i]))
          barr.append(value)

        references[reference] = Array(bool, len(barr), barr)
      else:
        raise TypeError
    except:
      logger.debug(traceback.format_exc())
      return []

  return references[reference]


def reset_references():
  """
  Reset the cached references.
  Should be called before converting a new SMT model.
  """
  global references
  references = {}


def convert_float(floatval: ExprRef) -> float:
  floatval = smt.simplify(floatval)
  if isinstance(floatval, smt.FPNumRef):
    if configured_library == SMTLibrary.CVC5:
      NaN = math.nan
      oo = math.inf
    else:
      def FPVal(x, _): return x
      def FPSort(*_): return None
    return float(eval(floatval.as_string()))
  elif isinstance(floatval, smt.RatNumRef):
    frac = floatval.as_fraction()
    return frac.numerator / frac.denominator
  else:
    if smt.simplify(util.is_finite(floatval)):
      frac = smt.simplify(util.float_sort.accessor(0, 0)
                          (floatval)).as_fraction()
      return frac.numerator / frac.denominator
    elif smt.simplify(util.is_nan(floatval)):
      return math.nan
    elif smt.simplify(util.is_pos_inf(floatval)):
      return math.inf
    elif smt.simplify(util.is_neg_inf(floatval)):
      return -math.inf
    else:
      logger.debug("Couldn't identify type of SMT exreal object!")
      raise NotImplementedError


def convert_model(evaluated: ExprRef, model: ModelRef) -> Any:
  """
  Convert a value `evaluated` in the model `model` to a concrete Python value.
  """
  import z3

  try:
    if evaluated.sort() == util.any_sort:
      if smt.simplify(util.is_int(evaluated)):
        return smt.simplify(util.get_int(evaluated)).as_long()
      elif smt.simplify(util.is_float(evaluated)):
        return convert_float(util.get_float(evaluated))
      elif smt.simplify(util.is_bool(evaluated)):
        return bool(smt.simplify(util.get_bool(evaluated)))
      elif smt.simplify(util.is_none(evaluated)):
        return None
      elif smt.simplify(util.is_string(evaluated)):
        return smt.simplify(util.get_string(evaluated)).as_string()
      elif smt.simplify(util.is_reference(evaluated)):
        return convert_reference(model.evaluate(util.heap), util.get_reference(evaluated), model)
      else:
        logger.debug("Couldn't identify type of SMT object!")
        raise NotImplementedError
    else:
      logger.debug("Couldn't identify type of SMT object!")
      raise NotImplementedError
  except z3.z3types.Z3Exception:
    # To my knowledge this only occurs when Z3 is used and it decides not to provide a model for a particular variable
    # because it is unused. In this case, smt.simplify fails because the variable has no concrete `any` type.
    # Just return 0...
    return 0


def get_path_condition_append(v: SymbolicValue) -> SymbolicValue:
  """
  Gets the version of the symbolic value to append to the path condition.

  This will call `_not()` on the symbolic value if its concrete value is `False`.
  """
  value: SymbolicValue = v.to_sbool()

  if not value.get_value():
    value = value._not()

  return value


def are_same_concrete_object(first, second, depth=0) -> bool:
  if depth >= 64:
    return first == second
  elif type(first) is int and type(second) is int:
    return first == second
  elif type(first) is float and type(second) is float:
    return first == second
  elif type(first) is bool and type(second) is bool:
    return first == second
  elif first is None and second is None:
    return True
  elif type(first) is str and type(second) is str:
    return first == second
  elif type(first) is list and type(second) is list:
    if len(first) != len(second):
      return False
    else:
      for i in range(0, len(first)):
        if not are_same_concrete_object(first[i], second[i], depth + 1):
          return False
      return True
  elif type(first) is tuple and type(second) is tuple:
    if len(first) != len(second):
      return False
    else:
      for i in range(0, len(first)):
        if not are_same_concrete_object(first[i], second[i], depth + 1):
          return False
      return True
  elif type(first) is dict and type(second) is dict:
    if len(first) != len(second):
      return False
    else:
      first_items = list(first.items())
      second_items = list(second.items())
      return are_same_concrete_object(first_items, second_items, depth + 1)
  elif type(first) is set and type(second) is set:
    return False
  elif hasattr(first, "__class__") and hasattr(second, "__class__") and hasattr(first, "__dict__") and hasattr(second, "__dict__"):
    if first.__class__.__name__ != second.__class__.__name__:
      return False
    else:
      return are_same_concrete_object(first.__dict__, second.__dict__, depth + 1)
  else:
    return False
