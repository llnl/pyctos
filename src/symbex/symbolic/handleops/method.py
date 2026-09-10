# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from typing import Any, Union, Optional, List
import logging
import traceback

import symbex.symbolic.util as util
from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue
from symbex.globals.globals import record_path, make_assertion
from symbex.symbolic.operations import Operations
import symbex.symbolic.factories as factories


from symbex.smtlib import get_smt_lib, configured_library, SMTLibrary, ExprRef
smt = get_smt_lib()

logger = logging.getLogger(__name__)

temp_name: int = 0


class SymbolicListIterator:
  """
  Iterator over symbolic lists.
  """
  sv: SymbolicValue
  index: int
  length: int

  def __init__(self, sv: SymbolicValue):
    """
    Initializes the iterator.
    """
    self.sv = sv
    self.index = 0

    length: SymbolicValue = sv.__len__()
    self.length = length.get_value()

    record_path(length > 0)

  def __next__(self) -> SymbolicValue:
    """
    Gets the next item. Raises `StopIteration` if there are no more items.
    """
    index = self.index
    self.index += 1

    if index == self.length:
      raise StopIteration
    else:
      return self.sv[index]


def handle_get(sv: SymbolicValue, other: Union[SymbolicValue, Any], default: Union[SymbolicValue, Any]) -> Union[SymbolicValue, Any]:
  """
  Handles the `.get()` function on dictionaries
  """
  record_path(makeSymbolicValue(v=type(sv.get_value()) is dict, formula=smt.And(
    util.is_reference(sv.get_formula()), util.is_dict(util.dereference(sv.get_formula())))))

  assert type(sv.get_value()) is dict

  dct_formula = util.get_dict(util.dereference(sv.get_formula()))

  if isinstance(other, SymbolicValue):
    other_formula = other.get_formula()
    other_concrete = other.get_value()

    if other_concrete in sv.get_mutations().keys():
      return sv.get_mutations()[other_concrete]
  else:
    other_formula = factories.lift_value(other).get_formula()
    other_concrete = other

    if other_concrete in sv.get_mutations().keys():
      return sv.get_mutations()[other_concrete]

  if isinstance(default, SymbolicValue):
    default_formula = default.get_formula()
    default_concrete = default.get_value()
  else:
    default_formula = factories.lift_value(default).get_formula()
    default_concrete = default

  record_path(makeSymbolicValue(v=other_concrete in sv.get_value(), formula=smt.And(util.is_reference(sv.get_formula()), util.is_dict(
    util.dereference(sv.get_formula())), util.exists_in_dict_keys(util.lift_expr_to_any(other_formula), util.get_reference(
      sv.get_formula()), len(sv.get_value()), sv.get_mutations()))))

  return makeSymbolicValue(v=sv.get_value().get(other_concrete, default_concrete), formula=smt.If(util.exists_in_dict_keys(
    util.lift_expr_to_any(other_formula), util.get_reference(sv.get_formula()), len(sv.get_value()), sv.get_mutations()), dct_formula[
      util.lift_expr_to_any(other_formula)], default_formula))


def handle_getslice(sv: SymbolicValue, other: slice) -> SymbolicValue:
  """
  Handles slicing into a symbolic value (e.g., `symbolic[i:j:k]`).
  """

  record_path(makeSymbolicValue(v=type(sv.get_value()) is str or type(sv.get_value()) is list, formula=smt.Or(
    util.is_string(sv.get_formula()), smt.And(util.is_reference(sv.get_formula()), util.is_list(util.dereference(sv.get_formula()))))))

  assert type(sv.get_value()) is str or type(sv.get_value()) is list

  concrete_conjuncts: List[bool] = []
  symbolic_conjuncts: List[ExprRef] = []

  start = other.start
  stop = other.stop
  step = other.step

  if isinstance(start, SymbolicValue):
    start_concrete = start.get_value()
    start_formula = util.get_int(start.get_formula())
    concrete_conjuncts.append(type(start_concrete) is int)
    symbolic_conjuncts.append(util.is_int(start.get_formula()))
  elif start is None:
    start_concrete = 0
    start_formula = factories.lift_value(0).get_formula()
  else:
    start_concrete = start
    start_formula = factories.lift_value(start).get_formula()

  if isinstance(stop, SymbolicValue):
    stop_concrete = stop.get_value()
    stop_formula = util.get_int(stop.get_formula())
    concrete_conjuncts.append(type(stop_concrete) is int)
    symbolic_conjuncts.append(util.is_int(stop.get_formula()))
  elif stop is None:
    stop_concrete = len(sv.get_value())
    stop_formula = smt.If(util.is_string(sv.get_formula()), smt.Length(util.get_string(
      sv.get_formula())), util.get_list_length(util.dereference(sv.get_formula())))
  else:
    stop_concrete = stop
    stop_formula = factories.lift_value(stop).get_formula()

  if isinstance(step, SymbolicValue):
    step_concrete = step.get_value()
    step_formula = util.get_int(step.get_formula())
    concrete_conjuncts.append(type(step_concrete) is int)
    symbolic_conjuncts.append(util.is_int(step.get_formula()))
  else:
    step_concrete = step
    step_formula = factories.lift_value(step).get_formula()

  if start_concrete is None:
    start_concrete = 0
    start_formula = smt.IntVal(0)

  if len(symbolic_conjuncts) == 1:
    record_path(makeSymbolicValue(
      v=concrete_conjuncts[0], formula=symbolic_conjuncts[0]))
  elif len(symbolic_conjuncts) > 1:
    record_path(makeSymbolicValue(v=all(concrete_conjuncts),
                formula=smt.And(*symbolic_conjuncts)))

  concrete_other = slice(start_concrete, stop_concrete, step_concrete)
  concrete = sv.get_value()[concrete_other]

  # TODO: Implement stepping! Temporary solution right here to disable the step parameter!
  assert step_concrete is None

  length_formula = smt.If(util.is_string(sv.get_formula()), smt.Length(util.get_string(
    sv.get_formula())), util.get_list_length(util.dereference(sv.get_formula())))
  stop_formula = smt.If(stop_formula >= 0, stop_formula,
                        stop_formula + length_formula)

  if stop_concrete > 0:
    record_path(makeSymbolicValue(v=len(sv.get_value()) >=
                stop_concrete, formula=length_formula >= stop_formula))
  else:
    stop_concrete = stop_concrete + len(sv.get_value())
    record_path(makeSymbolicValue(v=len(sv.get_value()) >=
                start_concrete, formula=length_formula >= start_formula))

  newvar = smt.Const(
    "__slicevar" + str(sv.get_formula().hash()), util.any_sort)
  i = smt.Const('i', smt.IntSort())

  make_assertion(makeSymbolicValue(v=True, formula=smt.If(util.is_string(sv.get_formula()), util.is_string(newvar), smt.And(
    util.is_reference(newvar), util.is_list(util.dereference(newvar))))))

  make_assertion(makeSymbolicValue(v=True, formula=smt.Implies(util.is_string(sv.get_formula()), smt.SubString(
    util.get_string(sv.get_formula()), start_formula, stop_formula - start_formula) == util.get_string(newvar))))

  make_assertion(makeSymbolicValue(v=True, formula=smt.ForAll([i], smt.Implies(smt.And(util.is_reference(
    sv.get_formula()), util.is_list(util.dereference(sv.get_formula())), 0 <= i, i < stop_formula - start_formula), smt.And(
    util.is_reference(newvar), util.is_list(util.dereference(newvar)), util.get_list_length(util.dereference(newvar)) == stop_formula -
    start_formula, util.get_list(util.dereference(newvar))[i] == util.get_list(util.dereference(sv.get_formula()))[i + start_formula])))))

  return makeSymbolicValue(v=concrete, formula=newvar)


def handle_getitem(sv: SymbolicValue, other: Union[SymbolicValue, Any]) -> SymbolicValue:
  """
  Handles indexing into a symbolic value (e.g., `symbolic[i]`).
  """
  record_path(makeSymbolicValue(v=type(sv.get_value()) is not set, formula=smt.Not(smt.And(
    util.is_reference(sv.get_formula()), util.is_set(util.dereference(sv.get_formula()))))))

  assert type(sv.get_value()) is not set

  lst_formula = util.get_list(util.dereference(sv.get_formula()))
  length_formula = smt.If(util.is_reference(sv.get_formula()), util.get_list_length(
    util.dereference(sv.get_formula())), smt.Length(util.get_string(sv.get_formula())))
  string_formula = util.get_string(sv.get_formula())
  dct_formula = util.get_dict(util.dereference(sv.get_formula()))

  if isinstance(other, SymbolicValue):
    other_formula = other.get_formula()
    other_concrete = other.get_value()

    if other_concrete in sv.get_mutations().keys():
      return sv.get_mutations()[other_concrete]

    record_path(makeSymbolicValue(v=type(other_concrete) is int,
                                  formula=util.is_int(other_formula)))

    if type(other_concrete) is int:
      other_formula = util.get_int(other_formula)
  else:
    other_formula = factories.lift_value(other).get_formula()
    other_concrete = other

    if other_concrete in sv.get_mutations().keys():
      return sv.get_mutations()[other_concrete]

  # If the index is an integer
  if type(other_concrete) is int:
    # If not a dictionary, the index must be in bounds
    record_path(makeSymbolicValue(v=type(sv.get_value()) is dict or (0 <= other_concrete and other_concrete < len(
      sv.get_value())), formula=smt.Implies(smt.Not(smt.And(util.is_reference(sv.get_formula()), util.is_dict(
        util.dereference(sv.get_formula())))), smt.And(0 <= other_formula, other_formula < length_formula))))
  # If the index is not an integer
  else:
    # This must be a dictionary
    record_path(makeSymbolicValue(v=type(sv.get_value()) is dict, formula=smt.And(util.is_reference(
        sv.get_formula()), util.is_dict(util.dereference(sv.get_formula())))))

  record_path(makeSymbolicValue(v=type(sv.get_value()) is not dict or other_concrete in sv.get_value(), formula=smt.Implies(
    smt.And(util.is_reference(sv.get_formula()), util.is_dict(util.dereference(sv.get_formula()))), util.exists_in_dict_keys(
      util.lift_expr_to_any(other_formula), util.get_reference(sv.get_formula()), len(sv.get_value()), sv.get_mutations()))))

  if other_formula.sort() == smt.IntSort():
    return makeSymbolicValue(v=sv.get_value()[other_concrete], formula=smt.If(util.is_reference(
      sv.get_formula()), smt.If(util.is_list(util.dereference(sv.get_formula())), lst_formula[other_formula], dct_formula[
        util.lift_expr_to_any(other_formula)]), util.lift_expr_to_any(string_formula[other_formula])))
  else:
    return makeSymbolicValue(v=sv.get_value()[other_concrete], formula=dct_formula[util.lift_expr_to_any(other_formula)])


def handle_setitem(sv: SymbolicValue, other: Union[SymbolicValue, Any], newv: Any) -> None:
  """
  Handles assignment to symbolic lists (e.g., `symbolic[a] = b`).
  """
  record_path(makeSymbolicValue(v=type(sv.get_value()) is list or type(sv.get_value()) is dict, formula=smt.And(util.is_reference(
    sv.get_formula()), smt.Or(smt.And(util.is_list(util.dereference(sv.get_formula())), util.get_list_mutable(util.dereference(
      sv.get_formula()))), util.is_dict(util.dereference(sv.get_formula()))))))

  if type(sv.get_value()) is not list and type(sv.get_value()) is not dict:
    raise TypeError

  length_formula = util.get_list_length(
    util.dereference(sv.get_formula()))

  if isinstance(other, SymbolicValue):
    other_formula = other.get_formula()
    other_concrete = other.get_value()

    record_path(makeSymbolicValue(v=type(sv.get_value()) is not list or type(other_concrete) is int,
                                  formula=smt.Implies(util.is_list(util.dereference(sv.get_formula())), util.is_int(other_formula))))

    if type(other_concrete) is int:
      other_formula = util.get_int(other_formula)
    else:
      assert type(sv.get_value()) is dict
  else:
    other_formula = other
    other_concrete = other

    if type(other_concrete) is not int:
      record_path(makeSymbolicValue(v=type(sv.get_value()) is dict,
                  formula=util.is_dict(util.dereference(sv.get_formula()))))
      assert type(sv.get_value()) is dict

  if type(other_concrete) is int:
    record_path(makeSymbolicValue(v=type(sv.get_value()) is not list or (0 <= other_concrete and other_concrete < len(
      sv.get_value())), formula=smt.Implies(util.is_list(util.dereference(sv.get_formula())), smt.And(
        0 <= other_formula, other_formula < length_formula))))

  if other_concrete not in sv.get_value() and other_concrete not in sv.get_mutations():
    sv.additions += 1

  if isinstance(newv, SymbolicValue):
    sv.get_value()[other_concrete] = newv.get_value()
  else:
    sv.get_value()[other_concrete] = newv
  sv.get_mutations()[other_concrete] = newv


def handle_contains(sv: SymbolicValue, other: Union[SymbolicValue, Any]) -> Union[SymbolicValue, bool]:
  """
  Handles the `__contains__` operation on symbolic values.
  """
  if not isinstance(other, SymbolicValue):
    other = factories.lift_value(other)

  other_formula = other.get_formula()
  other_concrete = other.get_value()

  for i in sv.get_mutations().values():
    if isinstance(i, SymbolicValue):
      if i.get_value() == other_concrete:
        return True
    else:
      if i == other_concrete:
        return True

  record_path(makeSymbolicValue(v=type(other_concrete) is str or type(sv.get_value()) is not str,
                                formula=smt.Implies(util.is_string(sv.get_formula()), util.is_string(util.lift_expr_to_any(other_formula)))))

  i = smt.Int("i")
  concrete = other_concrete in sv.get_value()

  if type(sv.get_value()) is list or type(sv.get_value()) is tuple:
    length = len(sv.get_value())
    disjuncts: List[ExprRef] = [smt.And(util.get_list_length(util.dereference(sv.get_formula(
    ))) >= length + 1, util.get_list(util.dereference(sv.get_formula()))[length] == util.lift_expr_to_any(other_formula))]

    for i in range(length):
      disjuncts.append(smt.And(i < util.get_list_length(util.dereference(sv.get_formula(
      ))), util.get_list(util.dereference(sv.get_formula()))[i] == util.lift_expr_to_any(other_formula)))

    if len(disjuncts) > 1:
      return makeSymbolicValue(v=concrete, formula=smt.Or(*disjuncts))
    else:
      return makeSymbolicValue(v=concrete, formula=disjuncts[0])
  elif type(sv.get_value()) is str:
    return makeSymbolicValue(v=concrete, formula=smt.IndexOf(util.get_string(sv.get_formula()), other_formula, 0) >= 0)
  elif type(sv.get_value()) is dict:
    return makeSymbolicValue(v=concrete, formula=util.exists_in_dict_keys(
      util.lift_expr_to_any(other_formula), util.get_reference(sv.get_formula()), len(sv.get_value()), sv.get_mutations()))
  elif type(sv.get_value()) is set:
    return makeSymbolicValue(v=concrete, formula=util.exists_in_set(
      util.lift_expr_to_any(other_formula), util.get_reference(sv.get_formula())))
  else:
    raise TypeError


def handle_iter(sv: SymbolicValue) -> SymbolicListIterator:
  """
  Generates an iterator over a symbolic list.
  """
  return SymbolicListIterator(sv)


def handle_len(sv: SymbolicValue) -> SymbolicValue:
  """
  Handles the `__len__` operation on symbolic values.
  """
  make_assertion(makeSymbolicValue(v=True, formula=smt.Implies(smt.And(util.is_reference(sv.get_formula()), util.is_list(
    util.dereference(sv.get_formula()))), util.get_list_length(util.dereference(sv.get_formula())) >= 0)))

  # assert configured_library == SMTLibrary.CVC5 or type(
  #  sv.get_value()) is not dict

  added_length = sv.get_additions()

  if configured_library == SMTLibrary.Z3:
    return makeSymbolicValue(v=len(sv.get_value()) + sv.get_additions(), formula=util.lift_expr_to_any(smt.If(util.is_reference(sv.get_formula()), smt.If(util.is_list(
      util.dereference(sv.get_formula())), util.get_list_length(util.dereference(sv.get_formula())), smt.If(util.is_dict(util.dereference(
        sv.get_formula())), util.get_dict_cardinality(util.dereference(sv.get_formula())), util.bound(util.get_reference(
          sv.get_formula())))), smt.Length(util.get_string(sv.get_formula()))) + added_length))
  else:
    return makeSymbolicValue(v=len(sv.get_value()) + sv.get_additions(), formula=util.lift_expr_to_any(smt.If(util.is_reference(sv.get_formula()), smt.If(util.is_list(
     util.dereference(sv.get_formula())), util.get_list_length(util.dereference(sv.get_formula())), smt.If(util.is_dict(
       util.dereference(sv.get_formula())), util.get_dict_cardinality(util.dereference(sv.get_formula())), util.get_cardinality(
         util.get_set(util.dereference(sv.get_formula()))))), smt.Length(util.get_string(sv.get_formula()))) + added_length))


def handle_append(sv: SymbolicValue, other: Any) -> None:
  record_path(makeSymbolicValue(v=type(sv.get_value()) is list, formula=smt.And(util.is_reference(sv.get_formula()), util.is_list(
    util.dereference(sv.get_formula())), util.get_list_mutable(util.dereference(sv.get_formula())))))

  assert type(sv.get_value()) is list

  length = len(sv.get_value())

  sv.get_mutations()[length] = other
  sv.additions += 1


def handle_pop(sv: SymbolicValue) -> SymbolicValue:
  record_path(makeSymbolicValue(v=type(sv.get_value()) is list, formula=smt.And(util.is_reference(sv.get_formula()), util.is_list(
    util.dereference(sv.get_formula())), util.get_list_mutable(util.dereference(sv.get_formula())))))

  assert type(sv.get_value()) is list

  conc_len = len(sv.get_value()) - 1

  if conc_len in sv.get_mutations():
    ret = sv.get_mutations()[conc_len]
    del sv.get_mutations()[conc_len]
    sv.additions -= 1
    return ret

  ret = sv[sv.__len__() - 1]
  sv.additions -= 1
  return ret


def handle_keys(sv: SymbolicValue) -> SymbolicValue:
  """
  Handles the `.keys()` method on dictionaries.
  """
  global temp_name

  record_path(makeSymbolicValue(v=type(sv.get_value()) is dict,
                                formula=smt.And(util.is_reference(sv.get_formula()),
                                                util.is_dict(util.dereference(sv.get_formula())))))

  assert type(sv.get_value()) is dict

  newvar = factories.make_symbolic_var(
    list(sv.get_value().keys()), "__temp_keys" + str(temp_name))
  temp_name += 1

  cardinality = util.get_dict_cardinality(util.dereference(sv.get_formula()))

  make_assertion(makeSymbolicValue(v=True, formula=smt.And(util.is_reference(newvar.get_formula()), util.is_list(
    util.dereference(newvar.get_formula())), util.get_list_length(util.dereference(newvar.get_formula())) == cardinality, util.get_list(
      util.dereference(newvar.get_formula())) == util.get_dict_keys(util.dereference(sv.get_formula())))))

  return newvar


def handle_items(sv: SymbolicValue) -> SymbolicValue:
  """
  Handles the `.items()` method on dictionaries.
  """
  global temp_name

  record_path(makeSymbolicValue(v=type(sv.get_value()) is dict,
                                formula=smt.And(util.is_reference(sv.get_formula()),
                                                util.is_dict(util.dereference(sv.get_formula())))))

  assert type(sv.get_value()) is dict

  newvar = factories.make_symbolic_var(
    list(sv.get_value().items()), "__temp_items" + str(temp_name))
  temp_name += 1

  cardinality = util.get_dict_cardinality(util.dereference(sv.get_formula()))

  conjuncts: List[ExprRef] = []

  for i in range(len(sv.get_value())):
    conjuncts.append(
      smt.And(
        i < cardinality,
        util.is_reference(util.get_list(
          util.dereference(newvar.get_formula()))[i]),
        util.is_list(util.dereference(util.get_list(
          util.dereference(newvar.get_formula()))[i])),
        util.get_list_length(util.dereference(util.get_list(
          util.dereference(newvar.get_formula()))[i])) == 2,
        util.get_list_mutable(util.dereference(util.get_list(
          util.dereference(newvar.get_formula()))[i])) == False,
        util.get_list(util.dereference(util.get_list(util.dereference(newvar.get_formula()))[i]))[0] ==
          util.get_dict_keys(util.dereference(sv.get_formula()))[i],
        util.get_list(util.dereference(util.get_list(util.dereference(newvar.get_formula()))[i]))[1] ==
          util.get_dict(util.dereference(sv.get_formula()))[util.get_dict_keys(util.dereference(sv.get_formula()))[i]]))

  make_assertion(makeSymbolicValue(v=True, formula=smt.And(util.is_reference(newvar.get_formula()), util.is_list(
    util.dereference(newvar.get_formula())), util.get_list_length(util.dereference(newvar.get_formula())) == cardinality, smt.And(*conjuncts))))

  return newvar


def handle_split(sv: SymbolicValue, sep: Union[SymbolicValue, Any], maxsplit: Union[SymbolicValue, Any]) -> Union[SymbolicValue, List[str]]:
  """
  Handles the `.split()` method on strings.
  """
  record_path(makeSymbolicValue(v=type(sv.get_value()) is str,
              formula=util.is_string(sv.get_formula())))

  concrete = sv.get_value()
  assert type(concrete) is str
  formula = util.get_string(sv.get_formula())

  # TODO: We don't support `sep` being None, it must be set!
  assert sep is not None
  # TODO: We don't yet support maxsplit, fix this!
  assert maxsplit is -1

  if isinstance(sep, SymbolicValue):
    sep_concrete = sep.get_value()
    sep_formula = sep.get_formula()

    record_path(makeSymbolicValue(v=type(sep_concrete)
                is str, formula=util.is_string(sep_formula)))
  else:
    sep_concrete = sep
    sep_formula = factories.lift_value(sep).get_formula()

  assert type(sep_concrete) is str
  concrete = concrete.split(sep_concrete)

  newvar = smt.Const("__splitvar" + str(formula.hash()), util.any_sort)
  i = smt.Const('i', smt.IntSort())

  existentials: List[ExprRef] = []
  actual_length = len(concrete)
  split_vars = actual_length

  terms: List[ExprRef] = []
  for i in range(split_vars):
    if i == 0:
      existentials.append(smt.IndexOf(formula, sep_formula))
      terms.append(existentials[i] != -1)
    else:
      existentials.append(smt.IndexOf(
        formula, sep_formula, existentials[i - 1] + 1))
      terms.append(existentials[i] > existentials[i - 1])

  if len(terms) > 1:
    split_constraint = smt.And(*terms)
  else:
    split_constraint = terms[0]

  if split_vars < 3:
    record_path(makeSymbolicValue(v=actual_length >
                split_vars, formula=split_constraint))

  assertion_constraint: ExprRef
  assertion_vars: List[ExprRef] = []
  assertion_terms: List[ExprRef] = []

  if actual_length == 0:
    assertion_constraint = util.get_list(util.dereference(newvar))[
        0] == sv.get_formula()
  else:
    for i in range(actual_length):
      if i == 0:
        assertion_vars.append(smt.IndexOf(formula, sep_formula))
        assertion_terms.append(assertion_vars[i] != -1)
        assertion_terms.append(util.get_list(util.dereference(newvar))[
                               i] == util.lift_expr_to_any(smt.SubString(formula, 0, assertion_vars[i])))
      elif i == actual_length - 1:
        assertion_terms.append(util.get_list(util.dereference(newvar))[i] == util.lift_expr_to_any(
          smt.SubString(formula, assertion_vars[i - 1] + 1, smt.Length(formula) - assertion_vars[i - 1] - 1)))
      else:
        assertion_vars.append(smt.IndexOf(
          formula, sep_formula, assertion_vars[i - 1] + 1))
        assertion_terms.append(assertion_vars[i] != -1)
        assertion_terms.append(util.get_list(util.dereference(newvar))[i] == util.lift_expr_to_any(
          smt.SubString(formula, assertion_vars[i - 1] + 1, assertion_vars[i] - assertion_vars[i - 1] - 1)))
    assertion_constraint = smt.And(*assertion_terms)

  make_assertion(makeSymbolicValue(v=True, formula=smt.And(util.is_reference(newvar), util.is_list(util.dereference(
    newvar)), util.get_list_length(util.dereference(newvar)) == actual_length, assertion_constraint)))

  return makeSymbolicValue(v=concrete, formula=newvar)


def handle_method_op(sv: SymbolicValue, op: Operations, *args, **kwargs) -> Optional[Union[SymbolicValue, SymbolicListIterator, Any]]:
  """
  Handler for miscellaneous method calls on symbolic values.
  """
  record_path(makeSymbolicValue(v=type(sv.get_value()) is list or
                                type(sv.get_value()) is str or
                                type(sv.get_value()) is dict or
                                type(sv.get_value()) is set or
                                type(sv.get_value()) is tuple,
                                formula=smt.Or(util.is_string(sv.get_formula()),
                                               smt.And(util.is_reference(sv.get_formula()),
                                                       smt.Or(util.is_list(util.dereference(sv.get_formula())),
                                                              util.is_dict(
                                                           util.dereference(sv.get_formula())),
                                                   util.is_set(util.dereference(sv.get_formula())))))))

  if op == Operations.LEN:
    return handle_len(sv)
  elif op == Operations.GET:
    return handle_get(sv, args[0], args[1])
  elif op == Operations.SPLIT:
    return handle_split(sv, args[0], args[1])
  elif op == Operations.CONTAINS:
    return handle_contains(sv, args[0])
  elif op == Operations.ITER:
    return handle_iter(sv)
  elif op == Operations.POP:
    return handle_pop(sv)
  elif op == Operations.KEYS:
    return handle_keys(sv)
  elif op == Operations.ITEMS:
    return handle_items(sv)
  elif op == Operations.GETITEM:
    if isinstance(args[0], slice):
      return handle_getslice(sv, args[0])
    else:
      return handle_getitem(sv, args[0])
  elif op == Operations.APPEND:
    handle_append(sv, args[0])
    return None
  elif op == Operations.SETITEM:
    handle_setitem(sv, args[0], args[1])
    return None
  else:
    raise NotImplementedError
