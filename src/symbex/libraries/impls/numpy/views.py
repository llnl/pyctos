# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from symbex.globals.globals import make_assertion, record_path
from symbex.symbolic import factories, util
from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue

from .util import *
from .array import ndarray

from symbex.smtlib import get_smt_lib
smt = get_smt_lib()


__all__ = [
    'swapaxes', 'transpose', 'permute_dims', 'expand_dims', 'broadcast_to', 'broadcast_shapes',
]


def swapaxes(array: ndarray | SymbolicValue, axis1: int | SymbolicValue, axis2: int | SymbolicValue) -> ndarray:
  """
  Returns a view with the given axes interchanged.
  """
  array._ensure_validity()

  # Get the rank
  rank = array.ndim
  concrete_rank = rank.get_value()
  symbolic_rank = rank.get_formula()

  # Get the concrete and symbolic parts of the axes to swap
  concrete_axis1: int
  symbolic_axis1: Formula
  if isinstance(axis1, SymbolicValue):
    concrete_axis1 = axis1.get_value()
    symbolic_axis1 = axis1.get_formula()
  else:
    concrete_axis1 = axis1
    symbolic_axis1 = factories.lift_value(axis1).get_formula()

  concrete_axis2: int
  symbolic_axis2: Formula
  if isinstance(axis2, SymbolicValue):
    concrete_axis2 = axis2.get_value()
    symbolic_axis2 = axis2.get_formula()
  else:
    concrete_axis2 = axis2
    symbolic_axis2 = factories.lift_value(axis2).get_formula()

  # Normalize symbolic axes to simplify our checks
  symbolic_axis1 = util.lift_expr_to_any(symbolic_axis1)
  symbolic_axis2 = util.lift_expr_to_any(symbolic_axis2)

  # Validate the provided indices: ints in [-rank, rank)
  concrete_axes_valid = (type(concrete_axis1) is int and -concrete_rank <= concrete_axis1 < concrete_rank) and (
    type(concrete_axis2) is int and -concrete_rank <= concrete_axis2 < concrete_rank)
  symbolic_axes_valid = smt.And(
    util.is_int(symbolic_axis1),
      -symbolic_rank <= util.get_int(symbolic_axis1),
      util.get_int(symbolic_axis1) < symbolic_rank,
      util.is_int(symbolic_axis2),
      -symbolic_rank <= util.get_int(symbolic_axis2),
      util.get_int(symbolic_axis2) < symbolic_rank)

  # Branch on validity
  record_path(makeSymbolicValue(
    v=concrete_axes_valid, formula=symbolic_axes_valid))
  assert concrete_axes_valid

  # After validation, unbox back to ints
  if util.is_any(symbolic_axis1):
    symbolic_axis1 = util.get_int(symbolic_axis1)
  if util.is_any(symbolic_axis2):
    symbolic_axis2 = util.get_int(symbolic_axis2)

  # Normalize negative indices
  concrete_axis1 = concrete_axis1 + \
      concrete_rank if concrete_axis1 < 0 else concrete_axis1
  symbolic_axis1 = smt.If(
    symbolic_axis1 < 0, symbolic_axis1 + symbolic_rank, symbolic_axis1)
  concrete_axis2 = concrete_axis2 + \
      concrete_rank if concrete_axis2 < 0 else concrete_axis2
  symbolic_axis2 = smt.If(
    symbolic_axis2 < 0, symbolic_axis2 + symbolic_rank, symbolic_axis2)

  # Compute the new shape and strides
  result_shape: list[SymbolicValue] = [None] * concrete_rank  # type: ignore
  result_strides: list[SymbolicValue] = [None] * concrete_rank  # type: ignore
  for i in range(concrete_rank):
    # Get the concrete and symbolic index this dimension should come from
    concrete_j = (concrete_axis1 ^ concrete_axis2 ^ i) if i in (
      concrete_axis1, concrete_axis2) else i
    symbolic_j = smt.If(symbolic_axis1 == i,
                        symbolic_axis2,
                        smt.If(symbolic_axis2 == i,
                               symbolic_axis1,
                               smt.IntVal(i)))
    j_sv = makeSymbolicValue(v=concrete_j, formula=symbolic_j)

    # Figure out the new shape/strides
    concrete_shapei = _shape_like_get(array._shape, concrete_j)[0]
    symbolic_shapei = _shape_like_get_concolic_index(array._shape, j_sv)[1]
    result_shape[i] = makeSymbolicValue(
      v=concrete_shapei, formula=symbolic_shapei)

    concrete_stridesi = _shape_like_get(array.strides, concrete_j)[0]
    symbolic_stridesi = _shape_like_get_concolic_index(array.strides, j_sv)[1]
    result_strides[i] = makeSymbolicValue(
      v=concrete_stridesi, formula=symbolic_stridesi)

  # Return a new view with the computed shape and strides
  return array._recreate(tuple(result_shape),  # type: ignore
                         array.offset, tuple(result_strides), order=None, skip_validation=True)


def transpose(array: ndarray | SymbolicValue, axes: ShapeLike | None = None) -> ndarray:
  """
  Returns a view with its shape and stride axes permutated.

  If no permutation is provided, the axes are reversed.
  """
  array._ensure_validity()

  # TODO: for now we don't normalize negatives, but it would be crazy to specify a permutation with negative indices
  # Get the rank
  rank = array.ndim
  concrete_rank = rank.get_value()
  symbolic_rank = rank.get_formula()

  # If a permutation is provided, validate it
  if axes is not None:
    permutation_valid = _validate_shape_like(
      axes, expected_rank=rank, require_nonnegative=True)

    # Branch on basic type/nonnegative values
    record_path(permutation_valid)
    assert permutation_valid.get_value()

    # If it passed shape-like validation, its values are nonnegative; must still check that they form a permutation
    # Unfortunately this requires rank^2 terms
    concrete_validity = True
    symbolic_validity_conjuncts: list[Formula] = []
    for i in range(concrete_rank):
      # Get the concrete and symbolic parts of this value
      concrete_value, symbolic_value = _shape_like_get(axes, i)

      # Ensure the value is in range
      concrete_validity &= (concrete_value < concrete_rank)
      symbolic_validity_conjuncts.append(symbolic_value < symbolic_rank)

      # Ensure the value is unique in the permutation
      for j in range(i):
        # Get the concrete and symbolic parts of the value to check against
        concrete_other, symbolic_other = _shape_like_get(axes, j)

        # Check for pairwise uniqueness
        concrete_validity &= (concrete_value != concrete_other)
        symbolic_validity_conjuncts.append(symbolic_value != symbolic_other)

    # Collapse the conjunction and branch on validity
    symbolic_validity = smt.And(
      smt.BoolVal(True), *symbolic_validity_conjuncts)
    record_path(makeSymbolicValue(
      v=concrete_validity, formula=symbolic_validity))
    assert concrete_validity
  else:
    # If no permutation is provided, we reverse the axes
    axes = tuple(reversed(range(concrete_rank)))

  # Permute the shape and strides
  result_shape: list[SymbolicValue] = [None] * concrete_rank  # type: ignore
  result_strides: list[SymbolicValue] = [None] * concrete_rank  # type: ignore
  for i in range(concrete_rank):
    concrete_j, symbolic_j = _shape_like_get(axes, i)
    j_sv = makeSymbolicValue(v=concrete_j, formula=symbolic_j)

    # Resolve possibly concolic permutation values for the new shape/strides
    concrete_shape_i, symbolic_shape_i = _shape_like_get_concolic_index(
      array._shape, j_sv)
    result_shape[i] = makeSymbolicValue(
      v=concrete_shape_i, formula=symbolic_shape_i)

    concrete_strides_i, symbolic_strides_i = _shape_like_get_concolic_index(
      array.strides, j_sv)
    result_strides[i] = makeSymbolicValue(
      v=concrete_strides_i, formula=symbolic_strides_i)

  # Return a new view with the computed shape and strides
  return array._recreate(tuple(result_shape),  # type: ignore
                         array.offset, tuple(result_strides), order=None, skip_validation=True)


def permute_dims(array: ndarray | SymbolicValue, axes: ShapeLike | None = None) -> ndarray:
  """
  Alias for `transpose`.
  """
  return transpose(array, axes)


def expand_dims(array: ndarray | SymbolicValue, axis: int | ShapeLike) -> ndarray:
  """
  Returns a view with new size-1 dimensions inserted at given indices.
  The given axis may be a single (possibly concolic) int, or a tuple of ints (in which case its
  length is used concretely).

  Returns a view with rank n+k, where n is the original rank and k is the number of given axes.
  Each new axis gets shape[i] = 1 and strides[i] = 0.
  """
  # TODO: numpy gives new axes strides computed as per `reshape`, not zeroes
  #       worth noting the strides for size-1 axes are stated as arbitrary so it's probably fine:
  #       https://github.com/numpy/numpy/blob/main/numpy/_core/src/multiarray/shape.c#L374
  array._ensure_validity()

  # Get the rank
  rank = array.ndim

  # Encode a condition for whether a single axis is provided (concrete int or symbolicvalue of int)
  concrete_is_single_axis = (type(axis) is int) or (
    isinstance(axis, SymbolicValue) and type(axis.get_value()) == int)
  symbolic_is_single_axis: Formula
  if isinstance(axis, SymbolicValue):
    formula = axis.get_formula()
    symbolic_is_single_axis = util.is_int(formula) if util.is_any(
      formula) else smt.BoolVal(formula.sort() == smt.IntSort())
  else:
    symbolic_is_single_axis = smt.BoolVal(type(axis) is int)

  # Initialize the axes we'll populate within the two cases
  concrete_axes: list[int] = []
  symbolic_axes: list[Formula] = []

  # Branch on whether we have a single axis or several, only if it could vary symbolically
  if isinstance(axis, SymbolicValue) and util.is_any(axis.get_formula()):
    record_path(makeSymbolicValue(v=concrete_is_single_axis,
                formula=symbolic_is_single_axis))
  if concrete_is_single_axis:
    # Axis is an int or concolic int; its type was already verified by the branching above
    concrete_axis: int
    symbolic_axis: Formula
    if isinstance(axis, SymbolicValue):
      concrete_axis = axis.get_value()
      symbolic_axis = util.get_int(axis.get_formula()) if util.is_any(
        axis.get_formula()) else axis.get_formula()
    else:
      concrete_axis = axis  # type: ignore
      symbolic_axis = smt.IntVal(axis)

    concrete_axes = [concrete_axis]
    symbolic_axes = [symbolic_axis]
  else:
    # Otherwise we have a concolic tuple or concrete tuple of possibly concolic values
    # Use the shape-like validation to check that it contains only integers (we validate bounds below, so skip it here)
    is_valid = _validate_shape_like(
      axis, require_nonnegative=False)  # type: ignore

    # Branch on validity
    # If already concretely valid, we can just make an assertion since we'll branch further down anyway
    if is_valid.get_value():
      make_assertion(is_valid)
    else:
      record_path(is_valid)
      raise ValueError('axis permutation is invalid')

    num_axes = len(axis.get_value()) if isinstance(
      axis, SymbolicValue) else len(axis)  # type: ignore

    for i in range(num_axes):
      # Get the concrete and symbolic parts of the current axis
      concrete_current_axis, symbolic_current_axis = _shape_like_get(
        axis, i)  # type: ignore

      # Put it in the lists for processing
      concrete_axes.append(concrete_current_axis)
      symbolic_axes.append(symbolic_current_axis)

  # Figure out the new rank (we assume both rank and number of axes are concrete)
  k = len(concrete_axes)
  result_rank = rank.get_value() + k

  # Now check validity of the axes: unique integers in the range [-new_rank, new_rank)
  concrete_validity: bool = True
  symbolic_validity_conjuncts: list[Formula] = []
  for i in range(k):
    concrete_current_axis = concrete_axes[i]
    symbolic_current_axis = symbolic_axes[i]

    # Axis is an integer in range [-new_rank, rank)
    concrete_validity &= -result_rank <= concrete_current_axis < result_rank
    symbolic_validity_conjuncts += [-result_rank <= symbolic_current_axis,
                                    symbolic_current_axis < result_rank]

    # Overwrite the axis with its normalized value before checking for uniqueness
    concrete_axes[i] = (
      result_rank + concrete_current_axis) if concrete_current_axis < 0 else concrete_current_axis
    symbolic_axes[i] = smt.If(symbolic_current_axis < 0,
                              symbolic_current_axis + result_rank,
                              symbolic_current_axis)

    # Axis is unique
    for j in range(i):
      concrete_validity &= (concrete_axes[i] != concrete_axes[j])
      symbolic_validity_conjuncts.append(
        symbolic_axes[i] != symbolic_axes[j])

  # Form the conjunction and actually check validity
  symbolic_validity = smt.And(smt.BoolVal(True), *symbolic_validity_conjuncts)
  record_path(makeSymbolicValue(
    v=concrete_validity, formula=symbolic_validity))
  assert concrete_validity

  # Boolean mask for which indices are new dimensions
  concrete_is_new_dim: list[bool] = [
    i in concrete_axes for i in range(result_rank)]
  symbolic_is_new_dim: list[Formula] = [smt.Or(smt.BoolVal(False), *(sym_ax == i for sym_ax in symbolic_axes))
                                        for i in range(result_rank)]

  # Construct the new shape and strides
  result_shape: list[SymbolicValue] = [None] * result_rank  # type: ignore
  result_strides: list[SymbolicValue] = [None] * result_rank  # type: ignore
  for i in range(result_rank):
    # Get the concolic index to pull shape/strides from for position i, if it's not a new dimension
    concrete_source_index = i - sum(1 for c in concrete_axes if c < i)
    symbolic_source_index = smt.IntVal(
      i) - smt.Sum(*(smt.If(symbolic_is_new_dim[j], smt.IntVal(1), smt.IntVal(0)) for j in range(i)))

    # Source index as a concolic value
    source_index_sv = makeSymbolicValue(
      v=concrete_source_index, formula=symbolic_source_index)

    # Compute the new shape/stride values
    # Dimension size is 1 for new dims
    concrete_shapei = 1 if concrete_is_new_dim[i] else _shape_like_get(
      array._shape, concrete_source_index)[0]
    symbolic_shapei = smt.If(symbolic_is_new_dim[i], smt.IntVal(
      1), _shape_like_get_concolic_index(array._shape, source_index_sv)[1])
    result_shape[i] = makeSymbolicValue(
      v=concrete_shapei, formula=symbolic_shapei)

    # Stride is 0 for new dims
    concrete_stridesi = 0 if concrete_is_new_dim[i] else _shape_like_get(
      array.strides, concrete_source_index)[0]
    symbolic_stridesi = smt.If(symbolic_is_new_dim[i], smt.IntVal(
      0), _shape_like_get_concolic_index(array.strides, source_index_sv)[1])
    result_strides[i] = makeSymbolicValue(
      v=concrete_stridesi, formula=symbolic_stridesi)

  # Construct the resulting view
  return array._recreate(tuple(result_shape),   # type: ignore
                         array.offset, tuple(result_strides), order=None,
                         skip_validation=True)


def broadcast_to(array: ndarray | SymbolicValue, shape: ShapeLike, subok: bool = False) -> ndarray:
  """
  Broadcasts an ndarray to the given shape, returning a read-only view with the strides
  of the broadcasted dimensions set to zero. Fails if the array cannot be broadcast to
  the given shape.
  """
  array._ensure_validity()

  # TODO: subok is meaningless with our curreny ndarray-only support model
  assert subok is False

  # Get the rank
  rank: SymbolicValue = array.ndim

  # Validate the new shape (rank may differ)
  shape_valid = _validate_shape_like(shape, require_nonnegative=True)
  if shape_valid.get_value():
    make_assertion(shape_valid)
  else:
    record_path(shape_valid)
    raise ValueError("broadcast target shape is invalid")

  # Get the rank of the shape we are broadcasting to and ensure it is at least the input rank
  target_rank = _shape_like_rank(shape)
  rank_valid = makeSymbolicValue(v=rank.get_value() <= target_rank.get_value(),
                                 formula=rank.get_formula() <= target_rank.get_formula())
  if rank_valid.get_value():
    make_assertion(rank_valid)
  else:
    record_path(rank_valid)
    raise ValueError("cannot broadcast to lower rank")

  # Get the amount the rank is increased by in broadcasting to the new shape
  # rank_shift: int = target_rank.get_value() - rank.get_value()
  rank_shift = makeSymbolicValue(v=target_rank.get_value() - rank.get_value(),
                                 formula=target_rank.get_formula() - rank.get_formula())

  # Build the new strides and broadcast validity condition
  concrete_validity = True
  symbolic_validity_conjuncts: list[Formula] = []
  result_strides: list[SymbolicValue] = [makeSymbolicValue(
    v=0, formula=smt.IntVal(0))] * target_rank.get_value()

  for old_axis in range(rank.get_value()):
    concrete_old_dim, symbolic_old_dim = _shape_like_get(
      array._shape, old_axis)
    new_axis = makeSymbolicValue(v=rank_shift.get_value(
    ) + old_axis, formula=rank_shift.get_formula() + smt.IntVal(old_axis))
    concrete_new_dim, symbolic_new_dim = _shape_like_get_concolic_index(
      shape, new_axis)

    # Apply validity conditions
    concrete_validity &= (
      concrete_old_dim == 1 or concrete_old_dim == concrete_new_dim)
    symbolic_validity_conjuncts.append(
      smt.Or(symbolic_old_dim == smt.IntVal(1), symbolic_old_dim == symbolic_new_dim))

    # Compute the new stride
    concrete_old_stride, symbolic_old_stride = _shape_like_get(
      array.strides, old_axis)
    concrete_stride = 0 if (concrete_old_dim == 1) else concrete_old_stride
    symbolic_stride = smt.If(symbolic_old_dim == smt.IntVal(
      1), smt.IntVal(0), symbolic_old_stride)
    result_strides[new_axis.get_value()] = makeSymbolicValue(
      v=concrete_stride, formula=symbolic_stride)

  # Branch on whether this is a valid shape to broadcast to
  symbolic_validity = smt.And(smt.BoolVal(True), *symbolic_validity_conjuncts)
  record_path(makeSymbolicValue(
    v=concrete_validity, formula=symbolic_validity))
  if not concrete_validity:
    raise ValueError("cannot broadcast to this shape")

  # Construct and return a read-only view with the new shape and strides
  return array._recreate(shape, array.offset, tuple(result_strides), order=None, writeable=False, skip_validation=True)


def broadcast_shapes(*shapes: ShapeLike) -> tuple[SymbolicValue, ...]:
  """
  Broadcasts the provided shapes against eachother and returns the resulting shape
  (always as a concrete tuple of SVs). Attempts to preserve some symbolic linking
  between dimensions and symbolic input ranks, though as always it operates on the
  concrete ranks.
  """
  # No shapes broadcast to a scalar shape
  if len(shapes) == 0:
    return ()

  # Validate input shapes in one atomic condition
  shapes_valid_each = list(map(_validate_shape_like, shapes))
  shapes_valid = makeSymbolicValue(v=all(sv.get_value() for sv in shapes_valid_each),
                                   formula=smt.And(smt.BoolVal(True), *(sv.get_formula() for sv in shapes_valid_each)))
  if shapes_valid.get_value():
    make_assertion(shapes_valid)
  else:
    record_path(shapes_valid)
    raise ValueError("at least one broadcast shape is invalid")

  # Make an assertion on the symbolic input ranks to tie them to the output rank
  ranks: list[SymbolicValue] = []
  result_rank = 0
  for shape in shapes:
    rank = _shape_like_rank(shape)
    ranks.append(rank)
    result_rank = max(result_rank, rank.get_value())

  # We assert that all input ranks are <= the output rank, and at least one input rank is == it
  # The highest rank input determines the rank of the output
  symbolic_result_rank = smt.IntVal(result_rank)
  symbolic_rank_case = smt.And(
    *(rank.get_formula() <= symbolic_result_rank for rank in ranks),
    smt.Or(*(rank.get_formula() == symbolic_result_rank for rank in ranks)))
  make_assertion(makeSymbolicValue(v=True, formula=symbolic_rank_case))

  # A single shape broadcasts to itself
  if len(shapes) == 1:
    # Just flatten the input shape into a concrete tuple of SVs
    result_shape: list[SymbolicValue] = []
    for i in range(result_rank):
      concrete_dim, symbolic_dim = _shape_like_get(shapes[0], i)
      result_shape.append(makeSymbolicValue(
        v=concrete_dim, formula=symbolic_dim))
    return tuple(result_shape)

  # Compute each result dimension from right to left, along with the broadcast validity condition
  concrete_validity = True
  symbolic_validity_conjuncts: list[Formula] = []
  result_shape: list[SymbolicValue] = []  # type: ignore[no-redef]
  for result_axis in range(result_rank):
    concrete_result_dim = 1
    symbolic_result_dim: Formula = smt.IntVal(1)

    # Loop over the input shapes
    for i in range(len(shapes)):
      shape = shapes[i]

      # Index that corresponds to the current result_axis for this shape
      concrete_source_axis = result_axis - result_rank + ranks[i].get_value()
      symbolic_source_axis = smt.IntVal(
        result_axis) - symbolic_result_rank + ranks[i].get_formula()
      source_axis = makeSymbolicValue(v=concrete_source_axis,
                                      formula=symbolic_source_axis)
      concrete_source_dim, symbolic_source_dim = _shape_like_get_concolic_index(
        shape, source_axis)

      # Missing leading axes behave like dimensions of size 1
      concrete_dim = 1 if concrete_source_axis < 0 else concrete_source_dim
      symbolic_dim = smt.If(symbolic_source_axis < smt.IntVal(
        0), smt.IntVal(1), symbolic_source_dim)

      # Must be compatible with the result dimension so far
      concrete_validity &= (
        concrete_dim == 1 or concrete_result_dim == 1 or concrete_dim == concrete_result_dim)
      symbolic_validity_conjuncts.append(smt.Or(symbolic_dim == smt.IntVal(1),
                                                symbolic_result_dim == smt.IntVal(
        1),
        symbolic_dim == symbolic_result_dim))

      # The resulting dimension is the first non-1 dimension, if one exists
      if concrete_result_dim == 1:
        concrete_result_dim = concrete_dim
      symbolic_result_dim = smt.If(symbolic_result_dim == smt.IntVal(
        1), symbolic_dim, symbolic_result_dim)

    result_shape.append(makeSymbolicValue(
      v=concrete_result_dim, formula=symbolic_result_dim))

  # Branch on whether the shapes are mutually broadcastable
  symbolic_validity = smt.And(smt.BoolVal(True), *symbolic_validity_conjuncts)
  record_path(makeSymbolicValue(
    v=concrete_validity, formula=symbolic_validity))
  if not concrete_validity:
    raise ValueError("shapes are not compatible for broadcasting")

  return tuple(result_shape)
