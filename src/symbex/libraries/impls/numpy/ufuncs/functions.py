# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from abc import abstractmethod
import sys
from typing import Any, Callable, TypeVar, cast

try:
  from typing import override  # type: ignore
except ImportError:
  from typing import Callable
  _F = TypeVar('_F', bound=Callable[..., Any])

  def override(func: _F, /) -> _F:  # type: ignore
    return func

from symbex.symbolic import factories
from symbex.types.symbolicvalue import SymbolicValue

from .bases import *
from .names import *
from ..util import *

from symbex.smtlib import get_smt_lib
smt = get_smt_lib()


# In this module, we programatically add ufunc instances to exports via @register_ufunc
__all__: list[str] = []


# Type parameter for @register_ufunc
_UFuncT = TypeVar('_UFuncT', bound=type[UFunc])


def register_ufunc(*aliases: UFuncName) -> Callable[[_UFuncT], _UFuncT]:
  """
  Instantiates a ufunc subclass with its canonical name, assigning it
  as a module property under that name and all of its aliases.

  Also adds the canonical name and aliases to the module exports.
  """

  def wrap(cls: _UFuncT) -> _UFuncT:
    # Create the canonical instance of the ufunc
    new = cast(Callable[[], UFunc], cls)
    instance = new()

    # Get the module object to assign on
    module = sys.modules[cls.__module__]

    # Assign alises on the module and add to __all__
    for alias in aliases:
      if alias in __all__ or hasattr(module, alias):
        raise RuntimeError(f'Attempted to register duplicate ufunc "{alias}"')

      setattr(module, alias, instance)
      __all__.append(alias)

    return cls

  return wrap


class UnaryUFunc(UFunc):
  """
  Base for a ufunc that performs a unary single-output operation and
  coerces to the result type of the signature, wrapping a basic scalar
  operation callback.
  """

  def __init__(self, name: UFuncName, identity: SymbolicValue | Unset | None = UNSET, reorderable: bool = False):
    super().__init__(name, nin=1, nout=1, identity=identity, reorderable=reorderable)

  @override
  def _apply(self, values: tuple[SymbolicValue, ...], signature: UFuncSignature) -> tuple[SymbolicValue, ...]:
    value, = values
    result_type, = signature.outputs

    return (_cast_scalar_unsafe(self._op(value), result_type),)

  @abstractmethod
  def _op(self, value: SymbolicValue) -> SymbolicValue:
    """
    Performs the unary operation defining this ufunc.
    """
    raise NotImplementedError


class BinaryUFunc(UFunc):
  """
  Base for a ufunc that performs a binary single-output operation and
  coerces to the result type of the signature, wrapping a basic scalar
  operation callback.
  """

  def __init__(self, name: UFuncName, identity: SymbolicValue | Unset | None = UNSET, reorderable: bool = False):
    super().__init__(name, nin=2, nout=1, identity=identity, reorderable=reorderable)

  @override
  def _apply(self, values: tuple[SymbolicValue, ...], signature: UFuncSignature) -> tuple[SymbolicValue, ...]:
    lhs, rhs = values
    result_type, = signature.outputs

    return (_cast_scalar_unsafe(self._op(lhs, rhs), result_type),)

  @abstractmethod
  def _op(self, lhs: SymbolicValue, rhs: SymbolicValue) -> SymbolicValue:
    """
    Performs the binary operation defining this ufunc.
    """
    raise NotImplementedError


@register_ufunc('negative')
class Negative(UnaryUFunc):
  """
  Negates the operand.
  """

  def __init__(self):
    super().__init__('negative')

  @override
  def _op(self, value: SymbolicValue) -> SymbolicValue:
    return value * -1


@register_ufunc('positive')
class Positive(UnaryUFunc):
  """
  Arithmetic noop; the unary `+x` operator.
  """

  def __init__(self):
    super().__init__('positive')

  @override
  def _op(self, value: SymbolicValue) -> SymbolicValue:
    return value


@register_ufunc('add')
class Add(BinaryUFunc):
  """
  Adds two operands to a single output.
  """

  def __init__(self):
    super().__init__('add', identity=factories.lift_value(0))

  @override
  def _op(self, lhs: SymbolicValue, rhs: SymbolicValue) -> SymbolicValue:
    return lhs + rhs


@register_ufunc('subtract')
class Subtract(BinaryUFunc):
  """
  Subtracts two operands to a single output.
  """

  def __init__(self):
    super().__init__('subtract')

  @override
  def _op(self, lhs: SymbolicValue, rhs: SymbolicValue) -> SymbolicValue:
    return lhs - rhs


@register_ufunc('multiply')
class Multiply(BinaryUFunc):
  """
  Multiplies two operands to a single output.
  """

  def __init__(self):
    super().__init__('multiply', identity=factories.lift_value(1))

  @override
  def _op(self, lhs: SymbolicValue, rhs: SymbolicValue) -> SymbolicValue:
    return lhs * rhs


@register_ufunc('equal')
class Equal(BinaryUFunc):
  """
  Determines whether two operands are equal.
  """

  def __init__(self):
    super().__init__('equal')

  @override
  def _op(self, lhs: SymbolicValue, rhs: SymbolicValue) -> SymbolicValue:
    return lhs == rhs


@register_ufunc('not_equal')
class NotEqual(BinaryUFunc):
  """
  Determines whether two operands are not equal.
  """

  def __init__(self):
    super().__init__('not_equal')

  @override
  def _op(self, lhs: SymbolicValue, rhs: SymbolicValue) -> SymbolicValue:
    return lhs != rhs


@register_ufunc('less')
class Less(BinaryUFunc):
  """
  Determines whether the first operand is less than the second.
  """

  def __init__(self):
    super().__init__('less')

  @override
  def _op(self, lhs: SymbolicValue, rhs: SymbolicValue) -> SymbolicValue:
    return lhs < rhs


@register_ufunc('less_equal')
class LessEqual(BinaryUFunc):
  """
  Determines whether the first operand is less than or equal to the second.
  """

  def __init__(self):
    super().__init__('less_equal')

  @override
  def _op(self, lhs: SymbolicValue, rhs: SymbolicValue) -> SymbolicValue:
    return lhs <= rhs


@register_ufunc('greater')
class Greater(BinaryUFunc):
  """
  Determines whether the first operand is greater than the second.
  """

  def __init__(self):
    super().__init__('greater')

  @override
  def _op(self, lhs: SymbolicValue, rhs: SymbolicValue) -> SymbolicValue:
    return lhs > rhs


@register_ufunc('greater_equal')
class GreaterEqual(BinaryUFunc):
  """
  Determines whether the first operand is greater than or equal to the second.
  """

  def __init__(self):
    super().__init__('greater_equal')

  @override
  def _op(self, lhs: SymbolicValue, rhs: SymbolicValue) -> SymbolicValue:
    return lhs >= rhs
