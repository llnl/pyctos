# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from symbex.types.symbolicvalue import makeSymbolicValue, SymbolicValue
from symbex.symbolic.operations import Operations
from symbex.globals.globals import record_path
import symbex.symbolic.util as util
import symbex.astmanip as astmanip
import symbex.lib as lib
import logging

from typing import Any, List, Union, Callable, Optional
from symbex.smtlib import get_smt_lib, ExprRef
smt = get_smt_lib()

logger = logging.getLogger(__name__)


def handle_member(sv: SymbolicValue, member: str) -> Union[Callable[..., Any], SymbolicValue]:
  """
  Handles the `__getitem__` operation on symbolic values.

  If we detect that we are retrieving a method call, wrap the method call and pass in `sv` as `self`.
  """
  # make sure that we terminate if not an object
  if not util.is_not_builtin(type(sv.get_value())):
    logger.debug(
      f"Encounted member access \"{member}\", but this is not an object. Falling back to fully concrete execution.")
    return getattr(sv.get_value(), member)

  # check the mutations first
  if member in sv.get_object_mutations().keys():
    return sv.get_object_mutations()[member]

  # Handle @property getters
  class_attr = getattr(type(sv.get_value()), member, None)
  if isinstance(class_attr, property) and class_attr.fget is not None:
    # Run the getter with the symbolic value for self
    return class_attr.fget(sv)

  # check if this data member doesn't exist in get_all_fields, indicating it's a method
  if member not in astmanip.get_all_fields():
    # if it exists and is callable, just return the method
    if hasattr(sv.get_value(), member) and callable(getattr(sv.get_value(), member)):
      attr = getattr(type(sv.get_value()), member)
      # Make sure we call with the "self" parameter as the SymbolicValue

      def callable_wrapper(*args, **kwargs) -> Any:
        return attr(sv, *args, **kwargs)
      return callable_wrapper
    # if it's not in get_all_fields, it should be a method, but we've found it exists yet isn't callable!
    elif hasattr(sv.get_value(), member):
      raise TypeError
    else:  # it doesn't exist, so we need to add an SMT constraint on the type of this class
      classes = astmanip.get_all_classes()
      recognizers: List[ExprRef] = []
      instances: bool = False
      for class_name, properties in classes.items():
        methods = properties[0]
        if member in methods:
          instances = instances or isinstance(
            sv.get_value(), lib.get_class(class_name))
          recognizers.append(util.class_type_recognizer(class_name)(
            util.get_object_type(util.dereference(sv.get_formula()))))

      assert len(recognizers) > 0
      if len(recognizers) > 1:
        recognizers = smt.Or(*recognizers)
      else:
        recognizers = recognizers[0]

      record_path(makeSymbolicValue(v=instances, formula=smt.And(util.is_reference(
        sv.get_formula()), util.is_object(util.dereference(sv.get_formula())), recognizers)))
  else:
    contains_member = util.get_object_members(
      util.dereference(sv.get_formula()))[smt.StringVal(member)]

    record_path(makeSymbolicValue(
      v=hasattr(sv.get_value(), member), formula=contains_member))

  return makeSymbolicValue(v=getattr(sv.get_value(), member),
                           formula=util.get_object(util.dereference(sv.get_formula()))[smt.StringVal(member)])


def handle_setmember(sv: SymbolicValue, member: str, newv: Any) -> None:
  """
  Handles the `__setattr__` operation on symbolic values.
  """
  if not util.is_not_builtin(type(sv.get_value())):
    raise TypeError
  sv.get_object_mutations()[member] = newv


def handle_object_op(sv: SymbolicValue, op: Operations, *args, **kwargs) -> Optional[Union[SymbolicValue, Callable[..., Any]]]:
  """
  Handler for object operations on symbolic values.
  """
  record_path(makeSymbolicValue(v=util.is_not_builtin(type(sv.get_value())), formula=smt.And(util.is_reference(
    sv.get_formula()), util.is_object(util.dereference(sv.get_formula())))))
  if op == Operations.MEMBER:
    return handle_member(sv, args[0])
  elif op == Operations.SETMEMBER:
    handle_setmember(sv, args[0], args[1])
    return None
  else:
    raise NotImplementedError
