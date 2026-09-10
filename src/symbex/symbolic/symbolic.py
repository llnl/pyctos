# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import logging
from dataclasses import dataclass
from typing import Any, Type, Dict, TypeAlias
from functools import partial
from copy import deepcopy

import symbex.symbolic.handleops.arithmetic as handle_arithmetic
import symbex.symbolic.handleops.method as handle_method
import symbex.symbolic.handleops.boolean as handle_boolean
import symbex.symbolic.handleops.generic as handle_generic
import symbex.symbolic.handleops.object as handle_object
from symbex.symbolic.operations import Operations
from symbex.types.symbolicvalue import SymbolicValue
from symbex.symbolic.util import is_not_builtin

from symbex.smtlib import get_smt_lib, ExprRef
smt = get_smt_lib()


logger = logging.getLogger(__name__)

Formula: TypeAlias = ExprRef


@dataclass
class SymbolicValueImpl(SymbolicValue):
  """
  The implementation for concolic objects.
  """
  formula: Formula
  v: Any

  mutations: Dict[Any, Any]
  object_mutations: Dict[str, Any]

  additions: int

  def get_formula(self) -> Formula:
    """
    Gets the symbolic half of the concolic object.
    """
    return self.formula

  def get_value(self) -> Any:
    """
    Gets the concrete half of the concolic object.
    """
    return self.v

  def get_mutations(self) -> Dict[int, Any]:
    """
    Gets a list of mutations on lists.
    The return value indicates a mapping from indexes into the list to their assigned value.
    """
    return self.mutations

  def get_object_mutations(self) -> Dict[str, Any]:
    """
    Gets a list of mutations on objects.
    The return value indicates a mapping from attributes to their assigned value.
    """
    return self.object_mutations

  def get_additions(self) -> int:
    """
    Gets a scalar representing the deviation from the starting length of a list.
    """
    return self.additions

  def typ(self) -> Type:
    """
    Gets the underlying type of this concolic object.
    """
    return type(self.v)

  def __getattr__(self, name: str) -> Any:
    """
    Implementation for `__getattr__` operations on concolic objects.
    """
    if name == "_and":
      return partial(handle_op, self, Operations.AND)
    elif name == "_or":
      return partial(handle_op, self, Operations.OR)
    elif name == "_not":
      return partial(handle_op, self, Operations.NOT)
    elif name == "to_sbool":
      return partial(handle_op, self, Operations.SBOOL)
    elif name[0:2] == "__":
      return self.v.__getattr__(name)
    else:
      return handle_op(self, Operations.MEMBER, name)

  def __setattr__(self, name: str, newv) -> Any:
    """
    Implementation for `__setattr__` operations on concolic objects.
    """
    if name == "v":
      super(SymbolicValue, self).__setattr__(name, newv)
    elif name == "formula":
      super(SymbolicValue, self).__setattr__(name, newv)
    elif name == "mutations":
      super(SymbolicValue, self).__setattr__(name, newv)
    elif name == "object_mutations":
      super(SymbolicValue, self).__setattr__(name, newv)
    elif name == "additions":
      super(SymbolicValue, self).__setattr__(name, newv)
    else:
      return handle_op(self, Operations.SETMEMBER, name, newv)

  def __str__(self) -> str:
    """
    Implementation for `__str__` operations on concolic objects.
    """
    return f"{str(self.v)} : {str(self.typ())} == {str(self.get_formula())}"

  def __gt__(self, other):
    """
    Implementation for `__gt__` operations on concolic objects.
    """
    if has_attr(self, "__gt__"):
      return handle_overloaded_op(self, "__gt__", other)
    else:
      return handle_op(self, Operations.GT, other)

  def __lt__(self, other):
    """
    Implementation for `__lt__` operations on concolic objects.
    """
    if has_attr(self, "__lt__"):
      return handle_overloaded_op(self, "__lt__", other)
    else:
      return handle_op(self, Operations.LT, other)

  def __ge__(self, other):
    """
    Implementation for `__ge__` operations on concolic objects.
    """
    if has_attr(self, "__ge__"):
      return handle_overloaded_op(self, "__ge__", other)
    else:
      return handle_op(self, Operations.GE, other)

  def __le__(self, other):
    """
    Implementation for `__le__` operations on concolic objects.
    """
    if has_attr(self, "__le__"):
      return handle_overloaded_op(self, "__le__", other)
    else:
      return handle_op(self, Operations.LE, other)

  def __eq__(self, other):
    """
    Implementation for `__eq__` operations on concolic objects.
    """
    if has_attr(self, "__eq__"):
      return handle_overloaded_op(self, "__eq__", other)
    else:
      return handle_op(self, Operations.EQ, other)

  def __ne__(self, other):
    """
    Implementation for `__ne__` operations on concolic objects.
    """
    if has_attr(self, "__ne__"):
      return handle_overloaded_op(self, "__ne__", other)
    else:
      return handle_op(self, Operations.NE, other)

  def __add__(self, other):
    """
    Implementation for `__add__` operations on concolic objects.
    """
    if has_attr(self, "__add__"):
      return handle_overloaded_op(self, "__add__", other)
    else:
      return handle_op(self, Operations.ADD, other)

  def __radd__(self, other):
    """
    Implementation for `__radd__` operations on concolic objects.
    """
    if has_attr(self, "__radd__"):
      return handle_overloaded_op(self, "__radd__", other)
    else:
      return handle_op(self, Operations.RADD, other)

  def __sub__(self, other):
    """
    Implementation for `__sub__` operations on concolic objects.
    """
    if has_attr(self, "__sub__"):
      return handle_overloaded_op(self, "__sub__", other)
    else:
      return handle_op(self, Operations.SUB, other)

  def __rsub__(self, other):
    """
    Implementation for `__rsub__` operations on concolic objects.
    """
    if has_attr(self, "__rsub__"):
      return handle_overloaded_op(self, "__rsub__", other)
    else:
      return handle_op(self, Operations.RSUB, other)

  def __mul__(self, other):
    """
    Implementation for `__mul__` operations on concolic objects.
    """
    if has_attr(self, "__mul__"):
      return handle_overloaded_op(self, "__mul__", other)
    else:
      return handle_op(self, Operations.MUL, other)

  def __rmul__(self, other):
    """
    Implementation for `__rmul__` operations on concolic objects.
    """
    if has_attr(self, "__rmul__"):
      return handle_overloaded_op(self, "__rmul__", other)
    else:
      return handle_op(self, Operations.RMUL, other)

  def __truediv__(self, other):
    """
    Implementation for `__truediv__` operations on concolic objects.
    """
    if has_attr(self, "__truediv__"):
      return handle_overloaded_op(self, "__truediv__", other)
    else:
      return handle_op(self, Operations.TRUEDIV, other)

  def __rtruediv__(self, other):
    """
    Implementation for `__rtruediv__` operations on concolic objects.
    """
    if has_attr(self, "__rtruediv__"):
      return handle_overloaded_op(self, "__rtruediv__", other)
    else:
      return handle_op(self, Operations.RTRUEDIV, other)

  def __floordiv__(self, other):
    """
    Implementation for `__floordiv__` operations on concolic objects.
    """
    if has_attr(self, "__floordiv__"):
      return handle_overloaded_op(self, "__floordiv__", other)
    else:
      return handle_op(self, Operations.FLOORDIV, other)

  def __rfloordiv__(self, other):
    """
    Implementation for `__rfloordiv__` operations on concolic objects.
    """
    if has_attr(self, "__rfloordiv__"):
      return handle_overloaded_op(self, "__rfloordiv__", other)
    else:
      return handle_op(self, Operations.RFLOORDIV, other)

  def __bool__(self):
    """
    Implementation for `__bool__` operations on concolic objects.
    """
    if has_attr(self, "__bool__"):
      return handle_overloaded_op(self, "__bool__")
    else:
      return handle_op(self, Operations.BOOL)

  def __int__(self):
    """
    Implementation for `__int__` operations on concolic objects.
    """
    if has_attr(self, "__int__"):
      return handle_overloaded_op(self, "__int__")
    else:
      return handle_op(self, Operations.INT)

  def __float__(self):
    """
    Implementation for `__float__` operations on concolic objects.
    """
    if has_attr(self, "__float__"):
      return handle_overloaded_op(self, "__float__")
    else:
      return handle_op(self, Operations.FLOAT)

  def __getitem__(self, other):
    """
    Implementation for `__getitem__` operations on concolic objects.
    """
    if has_attr(self, "__getitem__"):
      return handle_overloaded_op(self, "__getitem__", other)
    else:
      return handle_op(self, Operations.GETITEM, other)

  def __setitem__(self, other, newv):
    """
    Implementation for `__setitem__` operations on concolic objects.
    """
    if has_attr(self, "__setitem__"):
      return handle_overloaded_op(self, "__setitem__", other, newv)
    else:
      return handle_op(self, Operations.SETITEM, other, newv)

  def __contains__(self, other):
    """
    Implementation for `__contains__` operations on concolic objects.
    """
    if has_attr(self, "__contains__"):
      return handle_overloaded_op(self, "__contains__", other)
    else:
      return handle_op(self, Operations.CONTAINS, other)

  def append(self, *args, **kwargs):
    """
    `append` method on an array.
    """
    if has_attr(self, "append"):
      return handle_overloaded_op(self, "append", *args, **kwargs)
    else:
      return handle_op(self, Operations.APPEND, args[0])

  def pop(self, *args, **kwargs):
    """
    `pop` method on an array.
    """
    if has_attr(self, "pop"):
      return handle_overloaded_op(self, "pop", *args, **kwargs)
    else:
      return handle_op(self, Operations.POP)

  def keys(self, *args, **kwargs):
    """
    `keys` method on a dict.
    """
    if has_attr(self, "keys"):
      return handle_overloaded_op(self, "keys", *args, **kwargs)
    else:
      return handle_op(self, Operations.KEYS)

  def items(self, *args, **kwargs):
    """
    `items` method on a dict.
    """
    if has_attr(self, "items"):
      return handle_overloaded_op(self, "items", *args, **kwargs)
    else:
      return handle_op(self, Operations.ITEMS)

  def get(self, *args, **kwargs):
    """
    `append` method on an array.
    """
    if has_attr(self, "get"):
      return handle_overloaded_op(self, "get", *args, **kwargs)
    elif len(args) >= 2:
      return handle_op(self, Operations.GET, args[0], args[1])
    else:
      return handle_op(self, Operations.GET, args[0], None)

  def split(self, *args, **kwargs):
    """
   `split` method on strings.
    """
    if has_attr(self, "split"):
      return handle_overloaded_op(self, "split", *args, **kwargs)
    elif len(args) >= 2:
      return handle_op(self, Operations.SPLIT, args[0], args[1])
    elif len(args) == 1:
      return handle_op(self, Operations.SPLIT, args[0], -1)
    else:
      return handle_op(self, Operations.SPLIT, None, -1)

  def __iter__(self):
    """
    Implementation for `__iter__` operations on concolic objects.
    """
    if has_attr(self, "__iter__"):
      return handle_overloaded_op(self, "__iter__")
    else:
      return handle_op(self, Operations.ITER)

  def __len__(self):
    """
    Implementation for `__len__` operations on concolic objects.
    """
    if has_attr(self, "__len__"):
      return handle_overloaded_op(self, "__len__")
    else:
      return handle_op(self, Operations.LEN)

  def __deepcopy__(self, memo):
    """
    Deep copies a concolic object.
    """
    return SymbolicValueImpl(v=deepcopy(self.v, memo), formula=self.formula, mutations=deepcopy(
      self.mutations), object_mutations=deepcopy(self.object_mutations), additions=self.additions)


def is_arithmetic_op(op: Operations) -> bool:
  """
  Returns `True` iff `op` is an arithmetic operation.
  """
  return op == Operations.ADD or \
      op == Operations.RADD or \
      op == Operations.SUB or \
      op == Operations.RSUB or \
      op == Operations.MUL or \
      op == Operations.RMUL or \
      op == Operations.TRUEDIV or \
      op == Operations.RTRUEDIV or \
      op == Operations.FLOORDIV or \
      op == Operations.RFLOORDIV or \
      op == Operations.GT or \
      op == Operations.GE or \
      op == Operations.LT or \
      op == Operations.LE or \
      op == Operations.INT or \
      op == Operations.FLOAT


def is_method_op(op: Operations) -> bool:
  """
  Returns `True` iff `op` is a method called on an object (e.g., `obj.method()`).
  """
  return op == Operations.LEN or \
      op == Operations.ITER or \
      op == Operations.GETITEM or \
      op == Operations.SETITEM or \
      op == Operations.CONTAINS or \
      op == Operations.APPEND or \
      op == Operations.POP or \
      op == Operations.KEYS or \
      op == Operations.ITEMS or \
      op == Operations.GET or \
      op == Operations.SPLIT


def is_boolean_op(op: Operations) -> bool:
  """
  Returns `True` iff `op` is a boolean operation.
  """
  return op == Operations.AND or \
      op == Operations.OR or \
      op == Operations.NOT or \
      op == Operations.BOOL


def is_object_op(op: Operations) -> bool:
  """
  Returns `True` iff `op` is an object membership access operation.
  """
  return op == Operations.MEMBER or \
      op == Operations.SETMEMBER


def is_generic_op(op: Operations) -> bool:
  """
  Returns `True` iff `op` is a "generic" operator.
  This is an in-house term which loosely means that `op` works on all Python types.
  """
  return op == Operations.EQ or \
      op == Operations.NE or \
      op == Operations.SBOOL


def has_attr(sv: SymbolicValue, method: str) -> bool:
  """
  Returns `True` iff `sv`'s concrete value is a user-defined type containing the method `method`.
  """
  conc = sv.get_value()
  return is_not_builtin(type(conc)) and hasattr(conc, method) and callable(getattr(conc, method))


def handle_overloaded_op(sv: SymbolicValue, method: str, *args, **kwargs):
  """
  Calls a user-defined method instead of the SymbolicValueImpl's overloaded version.
  Still uses symbolic values.
  """
  func = getattr(type(sv.get_value()), method)
  return func(sv, *args, **kwargs)


def handle_op(sv: SymbolicValue, op: Operations, *args, **kwargs) -> Any:
  """
  Calls the specific handler on `sv` given the classification of `op`.
  """
  if is_arithmetic_op(op):
    return handle_arithmetic.handle_arithmetic_op(sv, op, *args, **kwargs)
  elif is_boolean_op(op):
    return handle_boolean.handle_boolean_op(sv, op, *args, **kwargs)
  elif is_method_op(op):
    return handle_method.handle_method_op(sv, op, *args, **kwargs)
  elif is_object_op(op):
    return handle_object.handle_object_op(sv, op, *args, **kwargs)
  elif is_generic_op(op):
    return handle_generic.handle_generic_op(sv, op, *args, **kwargs)
  else:
    logger.debug(f"Unhandled op: {sv} {op.name} {args} {kwargs}")
    raise AttributeError
