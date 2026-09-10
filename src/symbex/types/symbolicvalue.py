# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from abc import abstractmethod
from typing import Protocol, Any, Type, runtime_checkable, Dict, TypeAlias
from symbex.smtlib import get_smt_lib, ExprRef
smt = get_smt_lib()


Formula: TypeAlias = ExprRef


@runtime_checkable
class SymbolicValue(Protocol):
  """
  The base protocol for concolic objects.
  """
  @abstractmethod
  def get_formula(self) -> Formula:
    """
    Gets the symbolic half of the concolic object.
    """
    raise NotImplementedError

  @abstractmethod
  def get_value(self) -> Any:
    """
    Gets the concrete half of the concolic object.
    """
    raise NotImplementedError

  @abstractmethod
  def get_mutations(self) -> Dict[Any, Any]:
    """
    Gets a list of mutations on lists and dictionaries.
    The return value indicates a mapping from keys into the list to their assigned value.
    """
    raise NotImplementedError

  @abstractmethod
  def get_object_mutations(self) -> Dict[str, Any]:
    """
    Gets a list of mutations on objects.
    The return value indicates a mapping from attributes to their assigned value.
    """
    raise NotImplementedError

  @abstractmethod
  def get_additions(self) -> int:
    """
    Gets a scalar representing the deviation from the starting length of a list.
    """
    raise NotImplementedError

  @abstractmethod
  def typ(self) -> Type:
    """
    Gets the underlying type of this concolic object.
    """
    raise NotImplementedError

  @abstractmethod
  def __getattr__(self, name: str) -> Any:
    """
    Base handler for `__getattr__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __setattr__(self, name: str, newv) -> Any:
    """
    Base handler for `__setattr__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __str__(self) -> str:
    """
    Base handler for `__str__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __gt__(self, other):
    """
    Base handler for `__gt__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __lt__(self, other):
    """
    Base handler for `__lt__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __ge__(self, other):
    """
    Base handler for `__ge__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __le__(self, other):
    """
    Base handler for `__le__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __eq__(self, other):
    """
    Base handler for `__eq__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __ne__(self, other):
    """
    Base handler for `__ne__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __add__(self, other):
    """
    Base handler for `__add__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __radd__(self, other):
    """
    Base handler for `__radd__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __sub__(self, other):
    """
    Base handler for `__sub__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __rsub__(self, other):
    """
    Base handler for `__rsub__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __mul__(self, other):
    """
    Base handler for `__mul__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __rmul__(self, other):
    """
    Base handler for `__rmul__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __truediv__(self, other):
    """
    Base handler for `__truediv__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __rtruediv__(self, other):
    """
    Base handler for `__rtruediv__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __floordiv__(self, other):
    """
    Base handler for `__floordiv__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __rfloordiv__(self, other):
    """
    Base handler for `__rfloordiv__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __bool__(self):
    """
    Base handler for `__bool__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __int__(self):
    """
    Base handler for `__int__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __float__(self):
    """
    Base handler for `__float__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __getitem__(self, other):
    """
    Base handler for `__getitem__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __setitem__(self, other, newv):
    """
    Base handler for `__setitem__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __contains__(self, other):
    """
    Base handler for `__contains__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def append(self, *args, **kwargs):
    """
    Base handler for `append` method on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def pop(self, *args, **kwargs):
    """
    Base handler for `pop` method on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def keys(self, *args, **kwargs):
    """
    Base handler for `keys` method on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def items(self, *args, **kwargs):
    """
    Base handler for `items` method on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def get(self, *args, **kwargs):
    """
    Base handler for `get` method on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def split(self, *args, **kwargs):
    """
    Base handler for `split` method on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __iter__(self):
    """
    Base handler for `__iter__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __len__(self):
    """
    Base handler for `__len__` operations on concolic objects.
    """
    raise NotImplementedError

  @abstractmethod
  def __deepcopy__(self, memo):
    """
    Deep copies a concolic object.
    """
    raise NotImplementedError


def makeSymbolicValue(*args, **kwargs) -> SymbolicValue:
  """
  Factory for creating symbolic values. Required fields are `v=` and `formula=`.
  """
  import symbex.symbolic.symbolic as symbolic
  if "mutations" not in kwargs.keys():
    kwargs["mutations"] = {}
  if "object_mutations" not in kwargs.keys():
    kwargs["object_mutations"] = {}
  if "additions" not in kwargs.keys():
    kwargs["additions"] = 0
  return symbolic.SymbolicValueImpl(*args, **kwargs)
