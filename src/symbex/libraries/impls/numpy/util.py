# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from collections.abc import Callable
from typing import Any, Literal, TypeAlias, TypeVar

from symbex.globals.globals import make_assertion, record_path
from symbex.overrides.overrides import intercept_float, intercept_int
from symbex.smtlib import ExprRef
from symbex.symbolic import factories, util
from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue

from symbex.smtlib import get_smt_lib
smt = get_smt_lib()


__all__ = [
    'Scalar', 'DType', 'InterceptType', 'ShapeLikeTuple', 'ShapeLike', 'Formula', 'Casting',
    'DTYPES_ALLOWED', 'Unset', 'UNSET',
    '_split_concolic_int', '_shape_like_rank', '_shape_like_get', '_shape_like_get_concolic_index',
    '_freeze_shape_dims', '_coerce_scalar', '_cast_scalar_unsafe', '_normalize_dtype',
    '_normalize_index', '_validate_shape_like', '_default_strides', '_normalize_tuple_args',
    '_resolve_scalar_coordinates', '_is_valid_cast', '_min_casting',
]


# Describes the type of an SMT formula
Formula: TypeAlias = ExprRef

# Describes the elements and dtype of an ndarray, respectively
Scalar: TypeAlias = int | float | bool
DType: TypeAlias = type[Scalar]

# Describes an intercepted type (intercept_float or intercept_int in particular)
InterceptType: TypeAlias = Callable[[
  Any], int | SymbolicValue] | Callable[[Any], float | SymbolicValue]

# Describes a shape, stride or coordinate tuple/list: a concrete or concolic tuple of integers
ShapeLikeTuple: TypeAlias = tuple[int | SymbolicValue, ...] | SymbolicValue
ShapeLike: TypeAlias = ShapeLikeTuple | list[int | SymbolicValue]

# Describes a valid numpy casting rule
Casting: TypeAlias = Literal['no', 'equiv', 'safe', 'same_kind', 'unsafe']

# The set of allowed dtypes for ndarrays
DTYPES_ALLOWED = (int, float, bool)


class Unset:
  """
  Represents the default value of an argument for which "no kwarg provided" must be distinguished
  from "explicitly None".
  """


UNSET = Unset()


def _split_concolic_int(value: int | SymbolicValue) -> tuple[int, Formula]:
  """
  Resolves a (possibly concolic) value *known to be an integer* into its concrete and symbolic parts.
  Unboxes if the symbolic value is an Any; lifts to smt.IntSort if it is concrete.
  """
  concrete_value: int
  symbolic_value: Formula
  if isinstance(value, SymbolicValue):
    concrete_value = value.get_value()
    symbolic_value = value.get_formula()
    # Unbox if necessary
    if util.is_any(symbolic_value):
      symbolic_value = util.get_int(symbolic_value)
  else:
    concrete_value = value
    symbolic_value = smt.IntVal(value)

  return concrete_value, symbolic_value


def _shape_like_rank(shape: ShapeLike) -> SymbolicValue:
  """
  Gets the concolic rank of a shape-like tuple.
  """
  concrete_rank: int
  symbolic_rank: Formula
  if isinstance(shape, SymbolicValue):
    concrete_rank = len(shape.get_value())
    symbolic_rank = util.get_list_length(util.dereference(shape.get_formula()))
  else:
    # Concrete tuple that may contain a symbolic value
    concrete_rank = len(shape)
    symbolic_rank = smt.IntVal(concrete_rank)

  return makeSymbolicValue(v=concrete_rank, formula=symbolic_rank)


def _shape_like_get(shape: ShapeLike, index: int) -> tuple[int, Formula]:
  """
  Shorthand to get the concrete and symbolic parts of an element of a ShapeLike tuple (unboxing Any).
  The shape is assumed to be validated for type and element type, and the index is assumed to be in bounds.
  """
  concrete_value: int
  symbolic_value: Formula
  if isinstance(shape, SymbolicValue):
    concrete_value = shape.get_value()[index]
    symbolic_value = util.get_int(util.get_list(
      util.dereference(shape.get_formula()))[index])
  else:
    # Concrete tuple that may contain a symbolic value
    concrete_value, symbolic_value = _split_concolic_int(shape[index])

  return concrete_value, symbolic_value


def _shape_like_get_concolic_index(shape: ShapeLike, index: int | SymbolicValue) -> tuple[int, Formula]:
  """
  Shorthand to get the concrete and symbolic parts of an element of a ShapeLike tuple (unboxing Any).
  This function takes a concolic index. This index is allowed to be concretely out of bounds, in
  which case an undefined value is returned and should only be used guarded by an ITE bounds check.

  If shape is a concrete tuple of symbolic values, the result will be an O(rank) ITE chain.
  If shape is a concolic tuple, it will just be an indexing expression.
  """
  # If the index is concrete, we can defer to the concrete indexing function with lower overhead
  if not isinstance(index, SymbolicValue):
    return _shape_like_get(shape, index)

  concrete_value: int
  symbolic_value: Formula
  if isinstance(shape, SymbolicValue):
    # If shape is a concolic tuple, we can just index into its symbolic part (or -1 if OOB)
    concrete_value = shape.get_value()[index.get_value(
    )] if 0 <= index.get_value() < len(shape.get_value()) else -1
    symbolic_value = util.get_int(util.get_list(
      util.dereference(shape.get_formula()))[index.get_formula()])
  else:
    # Otherwise we have to generate an ITE chain for the symbolic part
    concrete_value = _shape_like_get(shape, index.get_value())[
        0] if 0 <= index.get_value() < len(shape) else -1

    rank = len(shape)
    symbolic_value = _shape_like_get(
      shape, rank - 1)[1] if rank > 0 else smt.IntVal(-1)
    for i in reversed(range(rank - 1)):
      symbolic_value = smt.If(index.get_formula() == i,
                              _shape_like_get(shape, i)[1],
                              symbolic_value)

  # Simplify the symbolic part, so the ITEs collapse if concretely known
  return concrete_value, smt.simplify(symbolic_value)


def _freeze_shape_dims(shape: ShapeLike) -> tuple[int, ...]:
  """
  Freezes symbolic rank and dimensions of the given shape, returning a fully concrete shape tuple.

  Functionally, asserts that symbolic dimensions equal their current concrete values.
  """
  rank = _shape_like_rank(shape)
  make_assertion(makeSymbolicValue(
    v=True, formula=rank.get_formula() == smt.IntVal(rank.get_value())))

  dims: list[int] = []
  for i in range(rank.get_value()):
    c_dim, s_dim = _shape_like_get(shape, i)
    make_assertion(makeSymbolicValue(
      v=True, formula=s_dim == smt.IntVal(c_dim)))
    dims.append(c_dim)

  return tuple(dims)


def _coerce_scalar(item: Scalar | SymbolicValue, dtype: DType | InterceptType | None) -> SymbolicValue:
  """
  Performs type coercion on a concrete or concolic item into a given dtype, unboxing Any.
  Like util.narrow_from_any_t but coerces the concrete value and records a type check.
  """
  # Normalize and validate the dtype
  dtype = _normalize_dtype(dtype)

  # Lift item to a symbolic value if it isn't one
  item = factories.lift_value(item)

  # For int and float, we can defer to the type casting handlers
  if dtype is int:
    # Unbox the Any from __int__
    coerced = item.__int__()
    formula = coerced.get_formula()
    return makeSymbolicValue(v=coerced.get_value(), formula=util.get_int(formula) if util.is_any(formula) else formula)
  if dtype is float:
    coerced = item.__float__()
    formula = coerced.get_formula()
    return makeSymbolicValue(v=coerced.get_value(), formula=util.get_float(formula) if util.is_any(formula) else formula)

  # We need to handle booleans ourself; SymbolicValue.__bool__ just returns a Python bool
  narrowed = util.narrow_from_any_t(item, dtype)
  return makeSymbolicValue(v=dtype(narrowed.get_value()), formula=narrowed.get_formula())


def _cast_scalar_unsafe(item: Scalar | SymbolicValue,
                        dtype: DType | InterceptType | None) -> SymbolicValue:
  """
  Casts a concrete or concolic item into a given dtype (unboxing Any), skipping validation.

  Unlike `_coerce_scalar`, this method does not cause branching, for use in concrete
  loops over array elements. The item is assumed to be a valid scalar (int, float or bool)
  coercible to the target dtype.
  """
  # Normalize and validate the dtype
  dtype = _normalize_dtype(dtype)

  # Lift item to a symbolic value if it isn't one
  item = factories.lift_value(item)

  # Perform the coercion
  casted = util.narrow_from_any_t(item, dtype)

  # If no conversion needed, return directly
  if casted is item and type(casted.get_value()) is dtype:
    return item

  # Otherwise cast the concrete part and simplify the coerced formula
  return makeSymbolicValue(v=dtype(casted.get_value()),
                           formula=smt.simplify(casted.get_formula()))


def _normalize_dtype(dtype: DType | InterceptType | None) -> DType:
  """
  Normalize a dtype that may have been intercepted by AST manipulation or may not have been passed.
  """
  if dtype is None:
    dtype = float

  if dtype is intercept_float:
    dtype = float
  if dtype is intercept_int:
    dtype = int

  assert dtype in DTYPES_ALLOWED
  return dtype


def _normalize_index(index: int | SymbolicValue, n: int | SymbolicValue) -> SymbolicValue:
  """
  Normalizes an index in the range [-n, n) into [0, n) following numpy's negative indexing semantics.
  Assumes the index is validated to be within [-n, n) already.
  """
  # Get the concrete and symbolic parts
  concrete_index, symbolic_index = _split_concolic_int(index)
  concrete_n, symbolic_n = _split_concolic_int(n)

  return makeSymbolicValue(v=(concrete_n + concrete_index) % concrete_n,
                           formula=smt.If(symbolic_index < 0,
                                          symbolic_n + symbolic_index,
                                          symbolic_index))


def _validate_shape_like(shape: ShapeLike,
                         *,
                         expected_rank: int | SymbolicValue | None = None,
                         require_nonnegative: bool = True,
                         allow_list: bool = True) -> SymbolicValue:
  """
  Returns a concolic condition representing the validity of the shape-like, for assertion or path recording.

  - If `expected_rank` is provided, checks the length against that rank.
  - If `require_nonnegative` is true, validates that elements of the list/tuple are nonnegative.
  - If `allow_list` is false, checks that the shape is a tuple and not a list (i.e. is immutable).

  We collapse the validity conditions into one so that the shape check is atomic; we don't want unecessary branching
  for each index that could be invalid, which would generate redundant inputs with the same point of failure.
  """
  # TODO: numpy supports a single int for shape; this should be allowed and we need a normalize_shape_like probably
  # Initialize the validity condition (we'll collect symbolic terms into a conjunction before returning)
  concrete_validity = True
  symbolic_validity_conjuncts: list[Formula] = []

  # Resolve the concrete and symbolic expected rank parts, if provided
  concrete_exp_rank: int | None = None
  symbolic_exp_rank: Formula | None = None
  if expected_rank is not None:
    concrete_exp_rank, symbolic_exp_rank = _split_concolic_int(expected_rank)

  allowed_types = (list, tuple) if allow_list else (tuple,)

  # Check that the shape is a tuple of the correct length
  # If the shape is a concolic object
  if isinstance(shape, SymbolicValue):
    concrete_validity &= isinstance(shape.get_value(), allowed_types)
    symbolic_validity_conjuncts += [
      util.is_reference(shape.get_formula()),
      util.is_list(util.dereference(shape.get_formula())),
    ]

    # Add the immutability condition, if lists are not allowed
    if not allow_list:
      symbolic_validity_conjuncts.append(
        smt.Not(util.get_list_mutable(util.dereference(shape.get_formula()))))

    # Add rank conditions
    if expected_rank is not None:
      # If expected rank is provided, check against it
      concrete_validity &= isinstance(shape.get_value(), allowed_types) and len(
        shape.get_value()) == concrete_exp_rank
      symbolic_validity_conjuncts.append(util.get_list_length(
        util.dereference(shape.get_formula())) == symbolic_exp_rank)
    else:
      # Need to safely get the length of the shape tuple; if it's not a valid tuple, we'll break out further down at the branch
      # concrete_rank = len(shape.get_value()) if isinstance(shape.get_value(), tuple) else 0
      concrete_validity &= isinstance(
        shape.get_value(), allowed_types) and len(shape.get_value()) >= 0
      symbolic_validity_conjuncts.append(util.get_list_length(
        util.dereference(shape.get_formula())) >= 0)

      if not allow_list:
        symbolic_validity_conjuncts.append(
          smt.Not(util.get_list_mutable(util.dereference(shape.get_formula()))))

  # Otherwise
  else:
    if expected_rank is not None:
      # If expected rank is provided, validate against it
      concrete_validity &= isinstance(
        shape, allowed_types) and len(shape) == concrete_exp_rank
      if isinstance(shape, allowed_types):
        symbolic_validity_conjuncts.append(symbolic_exp_rank == len(shape))
    else:
      # Otherwise ensure the shape is a tuple
      concrete_validity = isinstance(shape, allowed_types)

  # If the concrete condition already is unsatisfied, return invalid (unsafe to iterate)
  if not concrete_validity:
    symbolic_validity = smt.And(
      *symbolic_validity_conjuncts) if len(symbolic_validity_conjuncts) > 0 else smt.BoolVal(False)
    return makeSymbolicValue(v=False, formula=symbolic_validity)

  # Check the validity of each dimension
  if isinstance(shape, SymbolicValue):
    # Shape is a symbolic tuple; its elements must be integers
    num_dims = len(shape.get_value())
    sym_tuple = util.get_list(util.dereference(shape.get_formula()))
    for i in range(num_dims):
      # We know the index is in bounds, so just check that the value is a nonnegative integer
      conc_dim = shape.get_value()[i]
      sym_dim = sym_tuple[i]

      # Apply the condition for this dimension
      if require_nonnegative:
        concrete_validity &= type(conc_dim) is int and conc_dim >= 0
        symbolic_validity_conjuncts.append(
          smt.And(util.is_int(sym_dim), util.get_int(sym_dim) >= 0))
      else:
        concrete_validity &= type(conc_dim) is int
        symbolic_validity_conjuncts.append(util.is_int(sym_dim))
  else:
    # Shape is just a Python tuple, but it might contain symbolic values
    for dim in shape:
      if isinstance(dim, SymbolicValue):
        # This dimension is concolic; get concrete and symbolic parts from it
        conc_dim = dim.get_value()
        sym_dim = dim.get_formula()

        # Apply the condition for this dimension
        if require_nonnegative:
          concrete_validity &= type(conc_dim) is int and conc_dim >= 0
          if util.is_any(sym_dim):
            symbolic_validity_conjuncts.append(
              smt.And(util.is_int(sym_dim), util.get_int(sym_dim) >= 0))
          else:
            symbolic_validity_conjuncts.append(
              smt.And(smt.BoolVal(sym_dim.sort() == smt.IntSort()), sym_dim >= 0))
        else:
          concrete_validity &= type(conc_dim) is int
          symbolic_validity_conjuncts.append(util.is_int(sym_dim) if util.is_any(
            sym_dim) else smt.BoolVal(sym_dim.sort() == smt.IntSort()))
      else:
        # This dimension must be an integer
        if require_nonnegative:
          concrete_validity &= type(dim) is int and dim >= 0
        else:
          concrete_validity &= type(dim) is int

  # Return the concolic validity condition
  symbolic_validity = smt.And(
    *symbolic_validity_conjuncts) if len(symbolic_validity_conjuncts) > 0 else smt.BoolVal(True)
  return makeSymbolicValue(v=concrete_validity, formula=symbolic_validity)


def _default_strides(shape: ShapeLike) -> tuple[SymbolicValue, ...]:
  """
  Constructs the default strides from a (possibly concolic) shape.
  Result is a concrete tuple of concolic ints.
  """
  # Get rank from the shape
  rank = len(shape.get_value()) if isinstance(
    shape, SymbolicValue) else len(shape)

  # Initialize strides
  strides: list[SymbolicValue] = [None] * rank  # type: ignore

  # Compute the strides from the back
  concrete_stride = 1
  symbolic_stride = smt.IntVal(1)
  for i in reversed(range(rank)):
    strides[i] = makeSymbolicValue(v=concrete_stride, formula=symbolic_stride)

    concrete_dim, symbolic_dim = _shape_like_get(shape, i)
    concrete_stride *= concrete_dim
    symbolic_stride *= symbolic_dim

  return tuple(strides)


ElementT = TypeVar('ElementT')


def _normalize_tuple_args(args: ElementT | tuple[ElementT | SymbolicValue, ...] | SymbolicValue) -> tuple[ElementT | SymbolicValue, ...]:
  """
  Normalizes arguments that accept either a tuple of values or a single value of that
  type, always returning a concrete tuple of possibly concolic elements.

  Branches if the input is an SV that may be tuple or non-tuple.
  """
  if isinstance(args, SymbolicValue) and util.is_any(args.get_formula()):
    # Any-sort formula could be a tuple or a single element
    formula = args.get_formula()
    c_is_tuple = type(args.get_value()) is tuple
    s_is_tuple = smt.And(util.is_reference(formula),
                         util.is_list(util.dereference(formula)),
                         smt.Not(util.get_list_mutable(util.dereference(formula))))

    # Branch on whether it's a tuple
    record_path(makeSymbolicValue(v=c_is_tuple, formula=s_is_tuple))
    if not c_is_tuple:
      # If not a tuple, we just wrap it and return
      return (args,)

    # If we have a tuple formula, tie its symbolic and concrete length
    length = len(args.get_value())
    make_assertion(makeSymbolicValue(v=True, formula=util.get_list_length(
      util.dereference(formula)) == smt.IntVal(length)))

    # Then flatten the tuple
    return tuple(makeSymbolicValue(v=args.get_value()[i],
                                   formula=util.get_list(util.dereference(formula))[i])
                 for i in range(length))

  # Otherwise, the element can never be a concolic tuple; just wrap it
  return args if type(args) is tuple else (args,)  # type: ignore


def _resolve_scalar_coordinates(shape: ShapeLike,
                                offset: int | SymbolicValue,
                                strides: ShapeLike,
                                coords: tuple[int, ...]) -> SymbolicValue:
  """
  Resolves a concrete coordinate tuple against a view layout, returning the
  flat index to write to in the backing array.
  """
  # Index starts at offset
  c_index, s_index = _split_concolic_int(offset)

  # Add contribution from each dimension
  for i in range(len(coords)):
    c_stride, s_stride = _shape_like_get(strides, i)

    c_index += c_stride * coords[i]
    s_index += s_stride * smt.IntVal(coords[i])

  return makeSymbolicValue(v=c_index, formula=s_index)


def _is_valid_cast(from_type: DType, to_type: DType, casting: Casting) -> bool:
  """
  Checks whether `from_type` can be cast to `to_type` under the given numpy
  casting rule.
  """
  if casting == 'unsafe':
    return True

  if casting in ('no', 'equiv'):
    return from_type is to_type

  # Note that since we disregard type width, 'safe' and 'same_kind' are equivalent
  if casting in ('safe', 'same_kind'):
    return (from_type is to_type or
            (from_type is int and to_type is float) or
            (from_type is bool and to_type is int) or
            (from_type is bool and to_type is float))

  raise ValueError(f'invalid casting mode "{casting}"')


def _min_casting(rule_a: Casting, rule_b: Casting) -> Casting:
  """
  Returns the "min" casting rule of the two provided.
  """
  order: list[Casting] = ['no', 'equiv', 'safe', 'same_kind', 'unsafe']

  if rule_a not in order:
    raise ValueError(f'invalid casting rule "{rule_a}"')
  if rule_b not in order:
    raise ValueError(f'invalid casting rule "{rule_b}"')

  return order[min(order.index(rule_a), order.index(rule_b))]
