# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from types import EllipsisType
from typing import TYPE_CHECKING, TypeAlias

from symbex.globals.globals import record_path
from symbex.libraries.impls.numpy.util import *
from symbex.symbolic import factories, util
from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue

from symbex.smtlib import get_smt_lib
smt = get_smt_lib()


__all__ = [
    'Index', 'Slice', 'NewAxis', 'IndexArg', 'BasicIndexArgs', 'newaxis',
    '_validate_basic_index', '_normalize_basic_index', '_resolve_basic_index',
]


# Elements of a "basic indexing" tuple into an ndarray
Index: TypeAlias = int | SymbolicValue
if TYPE_CHECKING:
  Slice: TypeAlias = slice[Index | None, Index | None, Index | None]
else:
  # Generic slice[...] subscripting is not allowed at runtime
  Slice: TypeAlias = slice
NewAxis: TypeAlias = None
IndexArg: TypeAlias = Index | Slice | NewAxis | EllipsisType
BasicIndexArgs: TypeAlias = tuple[Index | Slice | NewAxis, ...]

# np.newaxis
newaxis: NewAxis = None


def _validate_basic_index(shape: ShapeLike,
                          args: tuple[IndexArg, ...]) -> SymbolicValue:
  """
  Builds a concolic condition representing the validity of the basic indexing arguments.
  Basic indexing describes the semantics of ndarray slicing with some permutation of ints,
  slices, np.newaxis and ellipses (excluding tuples, lists, arrays, masks, etc.).
  """
  rank = _shape_like_rank(shape)

  # We first validate structure, then if structure is concretely valid continue with checking dimensions.

  # Number of dimensions consumed and number of ellipsis components
  concrete_consumed_dims = 0
  symbolic_consumed_dims = smt.IntVal(0)
  num_ellipses = 0

  # Initialize the validity condition parts
  concrete_result = True
  symbolic_result_conjuncts = [smt.BoolVal(True)]

  # Loop through index parts
  for arg in args:
    if isinstance(arg, SymbolicValue) and util.is_any(arg.get_formula()):
      # If the formula is Any, this could be either an int index or newaxis/None
      concrete_result &= arg.get_value() is None or type(arg.get_value()) is int
      symbolic_result_conjuncts.append(smt.Or(util.is_int(arg.get_formula()),
                                              util.is_none(arg.get_formula())))

      # None does not consume a dimension (newaxis); int does
      concrete_consumed_dims += int(type(arg.get_value()) is int)
      symbolic_consumed_dims += smt.If(util.is_int(arg.get_formula()),
                                       smt.IntVal(1), smt.IntVal(0))
      continue

    if isinstance(arg, SymbolicValue):
      # Must be an int
      concrete_result &= type(arg.get_value()) is int
      symbolic_result_conjuncts.append(smt.BoolVal(
        arg.get_formula().sort() == smt.IntSort()))

      concrete_consumed_dims += 1
      symbolic_consumed_dims += smt.IntVal(1)
      continue

    if type(arg) is int:
      # Concrete integer has fully concrete effect
      concrete_consumed_dims += 1
      symbolic_consumed_dims += smt.IntVal(1)
      continue

    if arg is None:
      # Concrete none is a new axis
      continue

    if isinstance(arg, slice):
      # Slice with possibly concolic parameters
      for val in (arg.start, arg.stop, arg.step):
        if isinstance(val, SymbolicValue):
          if util.is_any(val.get_formula()):
            # If any, can be an integer or none
            concrete_result &= (type(val.get_value()) is int) or (
              val.get_value() is None)
            symbolic_result_conjuncts.append(
              smt.Or(util.is_int(val.get_formula()), util.is_none(val.get_formula())))
          else:
            # If not any, it can't be none; only an integer is valid
            concrete_result &= type(val.get_value()) is int
            symbolic_result_conjuncts.append(smt.BoolVal(
              val.get_formula().sort() == smt.IntSort()))
        else:
          concrete_result &= (type(val) is int) or (val is None)
          symbolic_result_conjuncts.append(
            smt.BoolVal((type(val) is int) or (val is None)))

      # Slice step, if provided, must be nonzero
      if arg.step is not None:
        if isinstance(arg.step, SymbolicValue):
          if util.is_any(arg.step.get_formula()):
            concrete_result &= (arg.step.get_value() is None) or (
              type(arg.step.get_value()) is int and arg.step.get_value() != 0)
            symbolic_result_conjuncts.append(smt.Implies(
              util.is_int(arg.step.get_formula()), util.get_int(arg.step.get_formula()) != smt.IntVal(0)))
          else:
            concrete_result &= type(
              arg.step.get_value()) is int and arg.step.get_value() != 0
            symbolic_result_conjuncts.append(
              arg.step.get_formula() != smt.IntVal(0))
        else:
          concrete_result &= type(arg.step) is int and arg.step != 0
          symbolic_result_conjuncts.append(
            smt.BoolVal(type(arg.step) is int and arg.step != 0))

      # Slice consumes a dimension
      concrete_consumed_dims += 1
      symbolic_consumed_dims += smt.IntVal(1)
      continue

    if arg is Ellipsis:
      # Ellipsis doesn't change structural validity
      num_ellipses += 1
      continue

    # Anything unhandled here is invalid
    concrete_result = False
    symbolic_result_conjuncts.append(smt.BoolVal(False))
    break

  # Validate that we got at most one ellipse
  concrete_result &= num_ellipses <= 1
  symbolic_result_conjuncts.append(smt.BoolVal(num_ellipses <= 1))

  # Validate the number of dimensions consumed against rank
  concrete_result &= concrete_consumed_dims <= rank.get_value()
  symbolic_result_conjuncts.append(
    symbolic_consumed_dims <= rank.get_formula())

  # If structurally invalid, we can't continue with further validation
  if not concrete_result:
    return makeSymbolicValue(v=concrete_result, formula=smt.And(*symbolic_result_conjuncts))

  # Now we can validate each dimension against its bounds
  concrete_axis = 0
  symbolic_axis = smt.IntVal(0)
  for arg in args:
    if arg is Ellipsis:
      # Ellipsis just skips however many dimensions we did not consume
      concrete_axis += rank.get_value() - concrete_consumed_dims
      symbolic_axis += rank.get_formula() - symbolic_consumed_dims
      continue

    if arg is None:
      # Newaxis does not consume a dimension
      continue

    if isinstance(arg, SymbolicValue) and util.is_any(arg.get_formula()):
      # SV that may be int or new axis
      concrete_is_int = type(arg.get_value()) is int
      symbolic_is_int = util.is_int(arg.get_formula())

      axis = makeSymbolicValue(v=concrete_axis, formula=symbolic_axis)
      concrete_dim, symbolic_dim = _shape_like_get_concolic_index(shape, axis)

      # Apply the bounds check
      if concrete_is_int:
        concrete_result &= -concrete_dim <= arg.get_value() < concrete_dim
      symbolic_result_conjuncts.append(smt.Implies(
        symbolic_is_int,
        smt.And(-symbolic_dim <= util.get_int(arg.get_formula()),
                util.get_int(arg.get_formula()) < symbolic_dim)))

      # Consumes a dimension if we got an integer
      concrete_axis += int(concrete_is_int)
      symbolic_axis += smt.If(symbolic_is_int, smt.IntVal(1), smt.IntVal(0))
      continue

    if isinstance(arg, SymbolicValue):
      # Our validation guarantees non-any SV are integers, so this is an int
      axis = makeSymbolicValue(v=concrete_axis, formula=symbolic_axis)
      concrete_dim, symbolic_dim = _shape_like_get_concolic_index(shape, axis)

      # Do the bounds check
      concrete_result &= -concrete_dim <= arg.get_value() < concrete_dim
      symbolic_result_conjuncts += [-symbolic_dim <=
                                    arg.get_formula(), arg.get_formula() < symbolic_dim]

      # Consume the dimension
      concrete_axis += 1
      symbolic_axis += smt.IntVal(1)
      continue

    if type(arg) is int:
      # Concrete indexing
      axis = makeSymbolicValue(v=concrete_axis, formula=symbolic_axis)
      concrete_dim, symbolic_dim = _shape_like_get_concolic_index(shape, axis)

      # Concrete bounds check...
      concrete_result &= -concrete_dim <= arg < concrete_dim
      symbolic_result_conjuncts += [-symbolic_dim <=
                                    smt.IntVal(arg), smt.IntVal(arg) < symbolic_dim]

      # Consume the dimension
      concrete_axis += 1
      symbolic_axis += smt.IntVal(1)
      continue

    if isinstance(arg, slice):
      # Slices into numpy arrays clamp instead of bounds checking, so we need only consume an axis
      concrete_axis += 1
      symbolic_axis += smt.IntVal(1)
      continue

    # Shouldn't have anything unhandled here after earlier structural validation
    raise ValueError("invalid slice component after structural validation")

  # Do the thing
  symbolic_result = smt.And(*symbolic_result_conjuncts)
  return makeSymbolicValue(v=concrete_result, formula=symbolic_result)


def _normalize_basic_index(shape: ShapeLike,
                           args: tuple[IndexArg, ...]) -> tuple[BasicIndexArgs, SymbolicValue]:
  """
  Normalizes basic indexing arguments, expanding ellipses and resolving to a tuple
  of only ints, slices, and np.newaxis. Assumes the input has passed through
  `_validate_basic_index`.

  Also returns a concolic condition representing whether indexing should return a
  scalar (to distinguish between scalar and 0-dim array return at the callsite).

  This function branches on the none-ness of Any values in the indexing arguments.
  """
  rank = _shape_like_rank(shape)

  # Branch to specialize top-level Any values that may be int or none
  s_specialization_conjuncts: list[Formula] = []
  for arg in args:
    if isinstance(arg, SymbolicValue) and util.is_any(arg.get_formula()):
      c_is_none = arg.get_value() is None
      s_is_none = util.is_none(arg.get_formula())
      s_specialization_conjuncts.append(
        s_is_none if c_is_none else smt.Not(s_is_none))
  if len(s_specialization_conjuncts):
    record_path(makeSymbolicValue(
      v=True, formula=smt.And(*s_specialization_conjuncts)))

  # Number of dimensions consumed
  concrete_consumed_dims = 0
  symbolic_consumed_dims = smt.IntVal(0)

  # Whether we've seen only int indices
  concrete_all_ints = True
  symbolic_all_ints_conjuncts = [smt.BoolVal(True)]

  # Do one pass to see if we got all ints and count consumed dimensions
  for arg in args:
    if arg is Ellipsis:
      # Ellipsis doesn't consume any dimensions
      concrete_all_ints = False
      symbolic_all_ints_conjuncts.append(smt.BoolVal(False))
      continue

    if arg is None:
      # Newaxis doesn't consume any dimensions
      concrete_all_ints = False
      symbolic_all_ints_conjuncts.append(smt.BoolVal(False))
      continue

    if isinstance(arg, SymbolicValue) and util.is_any(arg.get_formula()):
      # Any formula in an SV; may be int or none
      concrete_is_int = type(arg.get_value()) is int
      symbolic_is_int = util.is_int(arg.get_formula())

      concrete_consumed_dims += int(concrete_is_int)
      symbolic_consumed_dims += smt.If(symbolic_is_int,
                                       smt.IntVal(1), smt.IntVal(0))

      concrete_all_ints &= concrete_is_int
      symbolic_all_ints_conjuncts.append(symbolic_is_int)
      continue

    if isinstance(arg, slice):
      concrete_consumed_dims += 1
      symbolic_consumed_dims += smt.IntVal(1)

      concrete_all_ints = False
      symbolic_all_ints_conjuncts.append(smt.BoolVal(False))
      continue

    # Since the input is validated, only remaining case is an SV integer which consumes a dimension
    concrete_consumed_dims += 1
    symbolic_consumed_dims += smt.IntVal(1)

  # Build the normalized arguments
  result_args: list[Index | Slice | NewAxis] = []
  axis = 0
  for arg in args:
    if arg is Ellipsis:
      # Expands to the number of unconsumed axes
      num_ellipse_axes = rank.get_value() - concrete_consumed_dims
      result_args += [slice(None)] * num_ellipse_axes
      axis += num_ellipse_axes
      continue

    if arg is None:
      # Newaxis gets forwarded
      result_args.append(None)
      continue

    if isinstance(arg, SymbolicValue) and util.is_any(arg.get_formula()) and arg.get_value() is None:
      # Any value that is concretely none; we already branched on this
      result_args.append(None)
      continue

    if isinstance(arg, slice):
      # Slice does not get resolved here; just forward it and consume an axis
      result_args.append(arg)
      axis += 1
      continue

    # If we got here, we have an integer or concolic integer index
    concrete_index, symbolic_index = _split_concolic_int(arg)
    concrete_dim, symbolic_dim = _shape_like_get(shape, axis)

    # Normalize negatives
    concrete_res = (concrete_dim + concrete_index) % concrete_dim
    symbolic_res = smt.If(symbolic_index < smt.IntVal(0),
                          symbolic_dim + symbolic_index,
                          symbolic_index)
    result_args.append(makeSymbolicValue(v=concrete_res, formula=symbolic_res))
    axis += 1

  # Pad with full slices
  while axis < rank.get_value():
    result_args.append(slice(None))
    axis += 1

  # Determine whether the index results in a scalar read/write
  concrete_is_scalar = concrete_all_ints and concrete_consumed_dims == rank.get_value()
  symbolic_is_scalar = smt.And(smt.And(
    *symbolic_all_ints_conjuncts), symbolic_consumed_dims == rank.get_formula())
  is_scalar = makeSymbolicValue(
    v=concrete_is_scalar, formula=symbolic_is_scalar)

  return tuple(result_args), is_scalar


def _split_slice_part(value: Index | None) -> tuple[int | None, Formula, Formula]:
  """
  Splits a slice part into its concrete value, symbolic int value and symbolic None condition.
  The symbolic int value is meaningful only when the slice part is not None.
  """
  # If this is concolic Any, can be either int or none
  if isinstance(value, SymbolicValue):
    formula = value.get_formula()
    if util.is_any(formula):
      return value.get_value(), util.get_int(formula), util.is_none(formula)

    # Validation guarantees non-Any symbolic values are ints
    return value.get_value(), formula, smt.BoolVal(False)

  # Concrete None needs some dummy int formula, but callers guard it with is_none
  return value, smt.IntVal(0 if value is None else value), smt.BoolVal(value is None)


def _clamp_symbolic_slice_bound(index: Formula,
                                dim: Formula,
                                negative_step: Formula) -> Formula:
  """
  Clamps the given symbolic slice bounds equivalently to Python's concrete slice semantics.
  """
  # First shift by the dimension extent
  shifted = index + dim

  # If still out of bounds, the index clamps to 0 if the slice goes forwards and -1 otherwise
  return smt.If(index < smt.IntVal(0),
                smt.If(shifted < smt.IntVal(0),
                       smt.If(negative_step, smt.IntVal(-1), smt.IntVal(0)),
                       shifted),
                smt.If(index >= dim,
                       smt.If(negative_step, dim - smt.IntVal(1), dim),
                       index))


def _resolve_slice(arg: Slice,
                   concrete_dim: int,
                   symbolic_dim: Formula,
                   concrete_stride: int,
                   symbolic_stride: Formula) -> tuple[SymbolicValue, SymbolicValue, SymbolicValue]:
  """
  Resolves a validated slice against a source axis. Returns
  `(result_dim, offset_delta, result_stride)`: the components of shape, offset, and strides
  contributed by this slice, respectively.

  The offset delta is the amount to add to the view offset for this axis only.
  """
  # Split the slice arguments
  c_start, s_start, s_none_start = _split_slice_part(arg.start)
  c_stop, s_stop, s_none_stop = _split_slice_part(arg.stop)
  c_step, s_step, s_none_step = _split_slice_part(arg.step)

  # Defer to builtin slice to compute the concrete part
  c_result_start, c_result_stop, c_result_step = slice(
    c_start, c_stop, c_step).indices(concrete_dim)
  c_result_dim = len(range(c_result_start, c_result_stop, c_result_step))

  # Step defaults to 1 if none
  s_result_step = smt.If(s_none_step, smt.IntVal(1), s_step)
  s_negative_step = (s_result_step < smt.IntVal(0))

  # Defaults for start and stop depend on whether the step is negative
  s_default_start = smt.If(
    s_negative_step, symbolic_dim - smt.IntVal(1), smt.IntVal(0))
  s_default_stop = smt.If(s_negative_step, smt.IntVal(-1),
                          symbolic_dim)

  # Wrap the start in ITE for default, then clamp in bounds
  s_result_start = smt.If(s_none_start, s_default_start, s_start)
  s_result_start = _clamp_symbolic_slice_bound(
    s_result_start, symbolic_dim, s_negative_step)

  # Stop needs to be clamped *before* the none-ITE, so that -1 does not become dim-1
  s_result_stop = _clamp_symbolic_slice_bound(
    s_stop, symbolic_dim, s_negative_step)
  s_result_stop = smt.If(s_none_stop, s_default_stop, s_result_stop)

  # Compute the symbolic shape component
  s_dim_pos = smt.If(s_result_stop <= s_result_start,
                     smt.IntVal(0),
                     (s_result_stop - s_result_start + s_result_step - smt.IntVal(1)) / s_result_step)
  s_dim_neg = smt.If(s_result_stop >= s_result_start,
                     smt.IntVal(0),
                     (s_result_start - s_result_stop - s_result_step - smt.IntVal(1)) / -s_result_step)
  s_result_dim = smt.If(s_negative_step, s_dim_neg, s_dim_pos)

  # Compute emptiness conditions
  c_is_empty = (c_result_dim == 0)
  s_is_empty = (s_result_dim == smt.IntVal(0))

  # Empty slices contribute zero to offset and forward the existing stride
  return (makeSymbolicValue(v=c_result_dim, formula=s_result_dim),
          makeSymbolicValue(v=0 if c_is_empty else c_result_start * concrete_stride,
                            formula=smt.If(s_is_empty, smt.IntVal(0), s_result_start * symbolic_stride)),
          makeSymbolicValue(v=concrete_stride if c_is_empty else c_result_step * concrete_stride,
                            formula=smt.If(s_is_empty, symbolic_stride, s_result_step * symbolic_stride)))


def _resolve_basic_index(shape: ShapeLike,
                         offset: int | SymbolicValue,
                         strides: ShapeLike,
                         args: BasicIndexArgs) -> tuple[ShapeLikeTuple, SymbolicValue, ShapeLikeTuple]:
  """
  Resolves basic indexing arguments into shape/offset/strides. Assumes the
  arguments have been validated and normalized already.
  """
  # Offset starts equal to the input
  concrete_offset, symbolic_offset = _split_concolic_int(offset)

  result_shape: list[SymbolicValue] = []
  result_strides: list[SymbolicValue] = []

  axis = 0
  for arg in args:
    if arg is None:
      # Newaxis: add a size-1 dim without consuming a source axis (0 stride)
      result_shape.append(factories.lift_value(1))
      result_strides.append(factories.lift_value(0))
      continue

    # Other index components need to look at source strides
    concrete_stride, symbolic_stride = _shape_like_get(strides, axis)

    if isinstance(arg, slice):
      # Slice into this source dimension
      concrete_dim, symbolic_dim = _shape_like_get(shape, axis)
      result_dim, offset_delta, result_stride = _resolve_slice(
        arg, concrete_dim, symbolic_dim, concrete_stride, symbolic_stride)

      # Slice remaps shape/stride into the same dimension and may affect base offset
      concrete_offset += offset_delta.get_value()
      symbolic_offset += offset_delta.get_formula()
      result_shape.append(result_dim)
      result_strides.append(result_stride)
      axis += 1
      continue

    # Integer indices consume a source axis and update the offset
    concrete_index, symbolic_index = _split_concolic_int(arg)
    concrete_offset += concrete_index * concrete_stride
    symbolic_offset += symbolic_index * symbolic_stride
    axis += 1

  return (tuple(result_shape),
          makeSymbolicValue(v=concrete_offset, formula=symbolic_offset),
          tuple(result_strides))
