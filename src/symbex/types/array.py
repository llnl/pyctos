# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from collections import deque
from typing import Generic, TypeAlias, TypeVar

from symbex.globals.globals import make_assertion, record_path
from symbex.smtlib import ExprRef, get_smt_lib
from symbex.symbolic import util
from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue
smt = get_smt_lib()

# Describes the element type of an array
ElementT = TypeVar('ElementT', float, int, bool)

# Size bound for the number of symbolic writes we store on an array; unbounded if negative
_MAX_SYMBOLIC_WRITES = -1


class Array(Generic[ElementT]):
  """
  Represents a concolic array with elements of a known type (float, int, or bool).
  The concrete part is a Python list and symbolic part is one of floatarray, intarray
  or boolarray.

  The Array instance itself is concrete but assumes that `self` is an SV, as the
  instance should always be used internally wrapped in a SymbolicValue.

  Stores a bounded symbolic write cache for index reasoning.
  """
  _concrete_array: list[ElementT]
  _type: type[ElementT]
  _symbolic_writes: deque[tuple[ExprRef, SymbolicValue]]

  def __init__(self: 'Array[ElementT]', typ: type[ElementT], length: int, concrete_array: list[ElementT] | None = None) -> None:
    """
    Initializes a new array with a given type and length (assumed to be a nonnegative integer).
    If concrete_array is provided, it's used as the concrete array state.
    """
    # Create the concrete and array if not provided
    if concrete_array is None:
      concrete_array = [typ(0)] * length

    # Initialize the array
    self._concrete_array = concrete_array
    self._type = typ
    self._symbolic_writes = deque()

  def __repr__(self: 'Array[ElementT]') -> str:
    """
    Returns the string representation of a concrete array.
    """
    return f"Array({self._concrete_array})"

  def _get_validity(self: SymbolicValue) -> SymbolicValue:
    """
    Returns a concolic condition representing the internal consistency of the concolic array.
    """
    # Get some concrete values used for validity conditions
    concrete_type = self.get_value()._type
    concrete_array = self.get_value()._concrete_array

    # Determine validity conditions
    concrete_validity = isinstance(concrete_array, list) and all(
      type(x) is concrete_type for x in concrete_array)
    symbolic_validity = util.is_reference(self.get_formula())
    if concrete_type is float:
      symbolic_validity = smt.And(symbolic_validity, util.is_floatarray(
        util.dereference(self.get_formula())))
    elif concrete_type is int:
      symbolic_validity = smt.And(symbolic_validity, util.is_intarray(
        util.dereference(self.get_formula())))
    elif concrete_type is bool:
      symbolic_validity = smt.And(symbolic_validity, util.is_boolarray(
        util.dereference(self.get_formula())))
    else:
      # The concrete type should be valid by construction
      raise ValueError

    return makeSymbolicValue(v=concrete_validity, formula=symbolic_validity)

  def ensure_validity(self: SymbolicValue) -> None:
    """
    Ensures the internal consistency of the array, branching and raising if invalid so the
    engine will retry to satisfy validity conditions.

    After invoking this method, the array can assume its structure is valid.
    """
    # Validate the construction
    internal_validity = Array._get_validity(self)
    if internal_validity.get_value():
      # If the array is already valid, make an assertion to track the symbolic validity
      make_assertion(internal_validity)
    else:
      # We only record_path if concretely invalid, so the engine will solve for negation
      record_path(internal_validity)
      raise ValueError("Array instance is not internally consistent")

  def get_type(self: SymbolicValue) -> type[ElementT]:
    """
    Gets the concrete element type of the array.
    """
    return self.get_value()._type

  def get_length(self: SymbolicValue) -> SymbolicValue:
    """
    Gets the concolic length of the backing array.
    """
    # Ensure internal consistency
    Array.ensure_validity(self)

    concrete_len = len(self.get_value()._concrete_array)
    symbolic_len: ExprRef

    symbolic_array = util.dereference(self.get_formula())
    if Array.get_type(self) is float:
      symbolic_len = smt.Length(util.get_floatarray(symbolic_array))
    elif Array.get_type(self) is int:
      symbolic_len = smt.Length(util.get_intarray(symbolic_array))
    elif Array.get_type(self) is bool:
      symbolic_len = smt.Length(util.get_boolarray(symbolic_array))
    else:
      # We got an invalid type somehow in (re)construction; shouldn't be reachable
      raise ValueError

    # Box the symbolic length and return
    return makeSymbolicValue(v=concrete_len, formula=util.lift_expr_to_any(symbolic_len))

  def get(self: SymbolicValue,
          index: SymbolicValue,
          *,
          skip_validation: bool = False) -> SymbolicValue:
    """
    Reads a concolic value from the list at a given concolic index.

    The index is assumed to be an integer in [0, self.length).
    """
    # Ensure internal consistency
    if not skip_validation:
      Array.ensure_validity(self)

    # Get the concrete and symbolic values we need
    concrete_array = self.get_value()._concrete_array
    symbolic_array = util.dereference(self.get_formula())

    # Read both the concrete and symbolic value
    concrete_value: ElementT = concrete_array[index.get_value()]
    symbolic_value: ExprRef
    if Array.get_type(self) is float:
      symbolic_value = util.get_floatarray(symbolic_array)[index.get_formula()]
    elif Array.get_type(self) is int:
      symbolic_value = util.get_intarray(symbolic_array)[index.get_formula()]
    elif Array.get_type(self) is bool:
      symbolic_value = util.get_boolarray(symbolic_array)[index.get_formula()]
    else:
      # Should be unreachable assuming correct construction
      raise ValueError

    # Guard the symbolic value with an ITE chain for every symbolic write thus far
    # (last write wins if we go in forward order)
    # First unbox the index if necesssary (we normalized symbolic indices to raw ints for comparison)
    symbolic_index = util.get_int(index.get_formula()) if util.is_any(
      index.get_formula()) else index.get_formula()
    for key, value in self.get_value()._symbolic_writes:
      symbolic_value = smt.If(symbolic_index == key,
                              value,
                              symbolic_value)

    # Return the concolic element value
    return makeSymbolicValue(v=concrete_value, formula=symbolic_value)

  def set(self: SymbolicValue,
          index: SymbolicValue,
          element: SymbolicValue,
          *,
          skip_validation: bool = False) -> None:
    """
    Sets a concolic value in the list at a given concolic index.

    The index is assumed to be an integer in [0, self.length), and the element is assumed
    to be of the correct type.
    """
    # Ensure internal consistency
    if not skip_validation:
      Array.ensure_validity(self)

    # Set the concrete element
    self.get_value()._concrete_array[index.get_value()] = element.get_value()

    # Handle symbolic writes if enabled
    symbolic_writes = self.get_value()._symbolic_writes
    if _MAX_SYMBOLIC_WRITES != 0:
      # Drop a symbolic write if needed to keep the cache size in bounds
      if len(symbolic_writes) == _MAX_SYMBOLIC_WRITES:
        symbolic_writes.popleft()

      # Append the new symbolic write
      symbolic_writes.append((util.get_int(index.get_formula()) if util.is_any(
        index.get_formula()) else index.get_formula(), element.get_formula()))

  def __getitem__(self: SymbolicValue,
                  index: SymbolicValue) -> SymbolicValue:
    """
    See `Array::get`.
    """
    return Array.get(self, index)

  def __setitem__(self: SymbolicValue,
                  index: SymbolicValue,
                  element: SymbolicValue) -> None:
    """
    See `Array::set`.
    """
    Array.set(self, index, element)
