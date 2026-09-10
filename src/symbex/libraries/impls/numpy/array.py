# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import itertools
from typing import Any, ClassVar, Literal
from symbex.globals.globals import make_assertion, record_path
from symbex.libraries.impls.numpy.slicing import *
from symbex.symbolic import factories
from symbex.types.array import Array
from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue
import symbex.symbolic.util as util

from .util import *

from symbex.smtlib import get_smt_lib
smt = get_smt_lib()


__all__ = [
  'ndarray', 'ndim', 'zeros',
]


# Counter for unique SMT array variables
ARRAY_STORAGE_COUNT: int = 0


def _normalize_scalar_coordinates(shape: ShapeLike, coords: int | ShapeLikeTuple) -> ShapeLikeTuple:
  """
  Normalizes scalar coordinates so a single integer on a 1D array is a valid index argument
  (without normalization, it would need to be wrapped in a tuple).
  """
  rank = len(shape.get_value()) if isinstance(
    shape, SymbolicValue) else len(shape)
  if rank != 1:
    # Rank is greater than 1 so a scalar passed for coords would be invalid.
    # We can let normal tuple validation ensure coords is correct
    return coords  # type: ignore

  # Preexisting tuples and concolic tuples should stay as-is
  if isinstance(coords, tuple):
    return coords
  # Worth noting this branch is fully concrete; in the future we may want an ITE on whether the coordinates are a tuple?
  if isinstance(coords, SymbolicValue) and isinstance(coords.get_value(), tuple):
    return coords

  # Scalar index; convert to a valid tuple
  return (coords,)


def _validate_scalar_coordinates(shape: ShapeLike, coords: ShapeLikeTuple) -> SymbolicValue:
  """
  Computes a concolic condition representing whether the coordinates are valid under the given shape.
  If the coordinates are not a valid shape-like tuple, returns early and returns the condition for
  basic data type validity. Once that condition is satisfied, the returned condition will then include
  coordinate bounds checks.

  The shape is assumed to have been validated earlier in construction.
  """
  # Get the rank from the shape tuple
  rank = _shape_like_rank(shape)

  # Check that the coordinates are a tuple of integers with the appropriate rank
  # TODO: for now, we assume nonnegative indices
  base_validity = _validate_shape_like(
    coords, expected_rank=rank, require_nonnegative=True, allow_list=False)

  # If already invalid, return early
  if not base_validity.get_value():
    return base_validity

  # Initialize conditions for validity
  concrete_validity = True
  symbolic_validity_conjuncts: list[Formula] = [base_validity.get_formula()]

  # Loop through dimensions
  for i in range(rank.get_value()):
    # Get the dimension and index
    concrete_dim, symbolic_dim = _shape_like_get(shape, i)
    concrete_coordinate, symbolic_coordinate = _shape_like_get(coords, i)

    # Add the conditions for validity
    concrete_validity &= (concrete_coordinate < concrete_dim)
    symbolic_validity_conjuncts.append(symbolic_coordinate < symbolic_dim)

  # Construct the conjunction and return
  symbolic_validity = smt.And(*symbolic_validity_conjuncts)
  return makeSymbolicValue(v=concrete_validity, formula=symbolic_validity)


def _get_flattened_size(shape: ShapeLike) -> SymbolicValue:
  """
  Computes the concolic length of a backing array derived from a (possibly concolic) shape, equivalent to ndarray.size.
  The shape is assumed to be valid (see _validate_shape_like).
  """
  # Sanity check the type (should be true if _validate_shape_like was first checked by the caller)
  if isinstance(shape, SymbolicValue):
    assert isinstance(shape.get_value(), (list, tuple)
                      ) and len(shape.get_value()) >= 0
  else:
    assert isinstance(shape, (list, tuple)) and len(shape) >= 0

  # Initialize the array size (will be undefined if any dimension is concretely invalid)
  concrete_size = 1
  symbolic_size = smt.IntVal(1)
  if isinstance(shape, SymbolicValue):
    # Shape is a symbolic tuple; its elements must be integers
    num_dims = len(shape.get_value())
    sym_tuple = util.get_list(util.dereference(shape.get_formula()))
    for i in range(num_dims):
      # We know the index is in bounds, so just check that the value is a nonnegative integer
      conc_dim = shape.get_value()[i]
      sym_dim = sym_tuple[i]

      # Multiply into the array size
      assert type(conc_dim) is int and conc_dim >= 0
      concrete_size *= conc_dim
      symbolic_size *= util.get_int(sym_dim)
  else:
    # Shape is just a Python tuple, but it might contain symbolic values
    for dim in shape:
      if isinstance(dim, SymbolicValue):
        # This dimension is concolic; get concrete and symbolic parts from it
        conc_dim = dim.get_value()
        sym_dim = dim.get_formula()

        # Multiply into the array size if it's still valid
        assert type(conc_dim) is int and conc_dim >= 0
        concrete_size *= conc_dim
        symbolic_size *= util.get_int(
          sym_dim) if util.is_any(sym_dim) else sym_dim
      else:
        # Multiply into the array size
        assert type(dim) is int and dim >= 0
        concrete_size *= dim
        symbolic_size *= dim

  return makeSymbolicValue(v=concrete_size, formula=util.lift_expr_to_any(symbolic_size))


def _get_stride_extents(shape: ShapeLike, offset: int | SymbolicValue, strides: ShapeLike) -> tuple[SymbolicValue, SymbolicValue, SymbolicValue]:
  """
  Returns (is_empty, min_index, max_index) where is_empty is a concolic condition for whether the range is empty
  (and thus the indices are meaningless), and otherwise min/max_index are the extrema that this shape/strides
  pair may access.

  Assumes shape, strides and offset have already made it past _validate_shape_like.
  """
  # Get concrete & symbolic offsets
  concrete_offset, symbolic_offset = _split_concolic_int(offset)

  # Initialize min/max reachable indices to the base offset
  concrete_min_index, symbolic_min_index = concrete_offset, symbolic_offset
  concrete_max_index, symbolic_max_index = concrete_offset, symbolic_offset

  # We validated shape/strides type and rank already, so can just fetch rank from one of them arbitrarily
  rank = len(shape.get_value()) if isinstance(
    shape, SymbolicValue) else len(shape)

  # Initialize  concrete and symbolic conditions for whether any dimension is zero (special case)
  # If a dimension is zero, the addressible range of indices by these shape/strides is empty
  concrete_is_empty = False
  # List of terms in a disjunction implying the range is empty
  symbolic_is_empty_disjuncts = []

  # Loop through dimensions and compute reachable extents
  for i in range(rank):
    # Resolve the dimension and stride for this index
    concrete_dim, symbolic_dim = _shape_like_get(shape, i)
    concrete_stride, symbolic_stride = _shape_like_get(strides, i)

    # Update our condition for an empty index range
    concrete_is_empty |= (concrete_dim == 0)
    symbolic_is_empty_disjuncts.append(symbolic_dim == 0)

    # Compute this dimension's concrete contribution to the extents
    concrete_delta: int = 0
    if concrete_dim != 0:
      concrete_delta = (concrete_dim - 1) * concrete_stride

      # Delta may be negative if the stride is negative
      if concrete_delta >= 0:
        concrete_max_index += concrete_delta
      else:
        concrete_min_index += concrete_delta

    # Compute the symbolic min and max contribution
    symbolic_delta = (symbolic_dim - 1) * symbolic_stride
    symbolic_min_delta = smt.If(symbolic_dim == 0, smt.IntVal(0),
                                smt.If(symbolic_stride >= 0, smt.IntVal(0), symbolic_delta))
    symbolic_max_delta = smt.If(symbolic_dim == 0, smt.IntVal(0),
                                smt.If(symbolic_stride >= 0, symbolic_delta, smt.IntVal(0)))

    # Accumulate into the min/max indices
    symbolic_min_index += symbolic_min_delta
    symbolic_max_index += symbolic_max_delta

  # Form the symbolic is_empty disjunction
  symbolic_is_empty = smt.Or(smt.BoolVal(False), *symbolic_is_empty_disjuncts)

  # Return the empty range condition and min/max indices (again, only meaningful if nonempty)
  return (
    makeSymbolicValue(v=concrete_is_empty, formula=symbolic_is_empty),
    makeSymbolicValue(v=concrete_min_index, formula=symbolic_min_index),
    makeSymbolicValue(v=concrete_max_index, formula=symbolic_max_index)
  )


def _validate_view_layout(array: SymbolicValue, shape: ShapeLike, offset: int | SymbolicValue, strides: ShapeLike, symbolic_rank_link: bool = False) -> SymbolicValue:
  """
  Returns a concolic condition representing whether the view layout is safe for the given backing array.
  Also validates the types and bounds of shape and strides.
  """
  # Validate shape
  shape_valid = _validate_shape_like(shape)
  if not shape_valid.get_value():
      # If the shape is invalid, return early so the engine will revisit with a valid tuple
    return shape_valid

  # Get the rank from the shape tuple now that we know it's fine
  rank = _shape_like_rank(shape)

  # Validate strides against the shape
  strides_valid = _validate_shape_like(
    strides, expected_rank=rank if symbolic_rank_link else rank.get_value(), require_nonnegative=False)
  if not strides_valid.get_value():
    # Same as above, but make sure the callsite also gets both validity conditions
    return makeSymbolicValue(v=False, formula=smt.And(shape_valid.get_formula(), strides_valid.get_formula()))

  # Validate offset
  if isinstance(offset, SymbolicValue):
    symbolic_offset = util.get_int(offset.get_formula()) if util.is_any(
      offset.get_formula()) else offset.get_formula()

    concrete_offset_valid = type(
      offset.get_value()) is int and offset.get_value() >= 0
    symbolic_offset_valid = smt.And(util.is_int(offset.get_formula()) if util.is_any(
      offset.get_formula()) else smt.BoolVal(offset.get_formula().sort() == smt.IntSort()), symbolic_offset >= 0)

    offset_valid = makeSymbolicValue(
      v=concrete_offset_valid, formula=symbolic_offset_valid)
  else:
    offset_valid = factories.lift_value(type(offset) is int and offset >= 0)

  if not offset_valid.get_value():
    # Same deal here
    return makeSymbolicValue(v=False, formula=smt.And(shape_valid.get_formula(), strides_valid.get_formula(), offset_valid.get_formula()))

  # Validate index range against this backing array
  is_empty, min_index, max_index = _get_stride_extents(
    shape, offset, strides)

  # If the range is empty (there is some zero dimension), it is vacuously fine
  length = Array.get_length(array)
  concrete_validity = is_empty.get_value() or (
    0 <= min_index.get_value() and max_index.get_value() < length.get_value())
  symbolic_validity = smt.And(shape_valid.get_formula(),
                              strides_valid.get_formula(),
                              offset_valid.get_formula(),
                              smt.Implies(smt.Not(is_empty.get_formula()),
                                          smt.And(0 <= min_index.get_formula(),
                                                  max_index.get_formula() < util.get_int(length.get_formula()))))

  return makeSymbolicValue(v=concrete_validity, formula=symbolic_validity)


class ndarray:
  """
  Represents either a concolic ndarray or only the concrete part of an ndarray.

  There are two cases for the internal state.

  If the ndarray is constructed directly:
    - Methods receive the `ndarray` instance directly as the `self` argument.
    - `storage` is an Array wrapped in SymbolicValue. The `ndarray` constructor defines
      a unique SMT variable for the symbolic part.
    - `_shape` is a concrete or concolic shape tuple (that is, either a concrete tuple
      of concrete or concolic values; or a concolic tuple) that was provided to the
      constructor.
    - `offset` is a concrete or concolic offset integer provided to the constructor.
    - `strides` is a concrete or concolic shape-like tuple, much as `_shape`.

  If the ndarray is synthesized by the SMT solver:
    - Methods receive a `SymbolicValue` wrapping the instance as the `self` argument.
      The members of the instance are fully concrete. Member access is handled by the
      usual `SymbolicValue` machinery, which wraps the concrete members in a
      `SymbolicValue` where the formula represents symbolic object member access.
    - `storage` is a concrete instance of `Array[dtype]`
    - `_shape` is a concrete tuple of concrete integers
    - `offset` is a concrete integer
    - `strides` is a concrete tuple of concrete integers

  Note that in the second case, all members are still used as concolic values. The
  distinction is whether the `ndarray` stores their symbolic parts or whether they
  are represented by object member access through `SymbolicValueImpl`'s attribute
  handling.

  The input shape may be a list, and is stored in `_shape`. The `shape_tuple` property
  accessor returns a normalized tuple of (possibly concolic) integer values.

  Note also that rank is used concretely, even if the `ndim` property is concolic.
  This is to allow the solver to reason about the symbolic link between the rank
  of shape and strides and of coordinate accesses for synthesized ndarrays.
  Operations that actually depend on rank use its concrete value.

  We model whether the ndarray is readonly (the `writeable` flag) fully concretely;
  if any operation with symbolic dependencies would update the writeable flag, then
  it first branches and then sets the fully concrete flag value.
  """
  storage: Array[Any] | SymbolicValue
  _shape: ShapeLike
  offset: int | SymbolicValue
  strides: ShapeLike
  _writeable: bool

  # The type of the public ndarray shim, set by the init_subclass hook
  # We use this so construction gives an instance of the public shim subclass
  _PUBLIC_SHIM: ClassVar[type['ndarray'] | None] = None

  def __init_subclass__(cls):
    """
    Hook invoked when a subclass is defined. Here, we catch the public shim subclass
    being defined so that we can use it for construction instead of this hidden type.
    """
    super().__init_subclass__()
    if cls.__module__ == 'symbex.libraries.numpy':
      ndarray._PUBLIC_SHIM = cls

  def __new__(cls, *args, **kwargs):
    """
    Returns an instance of the public shim subclass.
    """
    # If attempting to instantiate with this impl class, use the shim instead
    if cls is ndarray:
      if ndarray._PUBLIC_SHIM is None:
        raise RuntimeError(
          'attempted to instantiate ndarray before shim defined')
      return object.__new__(ndarray._PUBLIC_SHIM)

    return object.__new__(cls)

  def __init__(self,
               shape: ShapeLike,
               dtype: DType | InterceptType | None = None,
               buffer: None = None,
               offset: int | SymbolicValue = 0,
               strides: ShapeLike | None = None,
               order: Literal['C', 'F'] | None = None,
               writeable: bool = True):
    """
    Constructs an ndarray that owns a new backing array.
    """
    # These params are unsupported as of now, make sure they are their default values
    assert buffer is None
    assert order is None or order == 'C'

    # Normalize the dtype
    dtype = _normalize_dtype(dtype)

    # Validate shape
    shape_valid = _validate_shape_like(shape)
    record_path(shape_valid)
    assert shape_valid.get_value()

    # Compute size of a backing array from the shape
    size = _get_flattened_size(shape)

    # Compute default strides if missing
    do_symbolic_rank_link = True
    if strides is None:
      strides = _default_strides(shape)
      do_symbolic_rank_link = False

    # Get a unique symbolic variable and make assertions on its type and length
    global ARRAY_STORAGE_COUNT
    ARRAY_STORAGE_COUNT += 1
    symbolic_array = util.lift_expr_to_any(
        smt.Const(f"__ndarray_storage{ARRAY_STORAGE_COUNT}", util.reference_sort))

    if dtype is float:
      make_assertion(makeSymbolicValue(
        v=True, formula=util.is_floatarray(util.dereference(symbolic_array))))
      make_assertion(makeSymbolicValue(v=True, formula=smt.Length(util.get_floatarray(
        util.dereference(symbolic_array))) == util.get_int(size.get_formula())))
    elif dtype is int:
      make_assertion(makeSymbolicValue(
        v=True, formula=util.is_intarray(util.dereference(symbolic_array))))
      make_assertion(makeSymbolicValue(v=True, formula=smt.Length(util.get_intarray(
        util.dereference(symbolic_array))) == util.get_int(size.get_formula())))
    elif dtype is bool:
      make_assertion(makeSymbolicValue(
        v=True, formula=util.is_boolarray(util.dereference(symbolic_array))))
      make_assertion(makeSymbolicValue(v=True, formula=smt.Length(util.get_boolarray(
        util.dereference(symbolic_array))) == util.get_int(size.get_formula())))
    else:
      raise ValueError(f"Unsupported dtype: {dtype}")

    # Initialize the concolic storage object from a new concrete Array and our symbolic array
    storage = makeSymbolicValue(
      v=Array(dtype, size.get_value()), formula=symbolic_array)

    # Validate our view layout
    layout_valid = _validate_view_layout(
      storage, shape, offset, strides, symbolic_rank_link=do_symbolic_rank_link)
    record_path(layout_valid)
    assert layout_valid.get_value()

    # Assign properties
    self.storage = storage
    self._shape = shape
    self.offset = offset
    self.strides = strides
    self._writeable = writeable

  def __prepare_replay_arg__(self: 'ndarray') -> Any:
    """
    Called on object arguments before they are pickled, in case they should be replayed from
    something other than the default object pickling result. Raises an exception if the
    input is invalid; this will be caught and the input argument set will be skipped.

    In this case, we create an actual numpy ndarray instance, and raise if the view layout
    is invalid for constructing an ndarray.

    This is the one method in which our base invariants can be wrong; if the ndarray was
    synthesized and wrapped in a SymbolicValue, then this method receives an instance with
    fully concrete fields and no symbolic part.
    """
    concrete_rank = self.ndim.get_value()

    # Validate storage
    concolic_storage: SymbolicValue
    if isinstance(self.storage, SymbolicValue):
      concolic_storage = self.storage
    else:
      # Storage can be fully concrete here (see doc comment), so we need a dummy SV for its validation method
      concolic_storage = makeSymbolicValue(
        v=self.storage, formula=util.lift_expr_to_any(smt.Const('__dummy_storage', util.reference_sort)))
    storage_valid = Array._get_validity(concolic_storage)  # type: ignore
    if not storage_valid.get_value():
      raise ValueError(
        "ndarray preprocessing failed: attached storage is invalid")

    # Validate shape
    shape_valid = _validate_shape_like(self._shape)  # type: ignore
    if not shape_valid.get_value():
      raise ValueError("ndarray preprocessing failed: shape tuple is invalid")

    # Validate strides
    strides_valid = _validate_shape_like(  # type: ignore
      self.strides, expected_rank=concrete_rank, require_nonnegative=False)
    if not strides_valid.get_value():
      raise ValueError(
        "ndarray preprocessing failed: strides invalid or do not match rank from shape")

    # Validate offset
    concrete_offset, _ = _split_concolic_int(self.offset)
    if type(concrete_offset) is not int or concrete_offset < 0:
      raise ValueError(
        "ndarray preprocessing failed: offset is not a nonnegative integer")

    # Validate the view layout
    valid_layout = _validate_view_layout(
      concolic_storage, self._shape, self.offset, self.strides, symbolic_rank_link=False)  # type: ignore
    if not valid_layout.get_value():
      raise ValueError(
        "ndarray preprocessing failed: view layout is invalid or unsafe for attached storage")

    # Validate writeable flag
    if type(getattr(self, '_writeable', None)) is not bool:
      raise ValueError(
        "ndarray preprocessing failed: internal _writeable flag missing or invalid")

    # If we got to here, the array is valid; construct a real ndarray
    dtype = Array.get_type(concolic_storage)
    storage = concolic_storage.get_value()._concrete_array  # type: ignore
    shape = [-1] * concrete_rank
    strides = [-1] * concrete_rank
    for i in range(concrete_rank):
      shape[i] = _shape_like_get(self._shape, i)[0]
      strides[i] = _shape_like_get(self.strides, i)[0]
    offset = _split_concolic_int(self.offset)[0]

    # Construct an actual ndarray
    import numpy as np
    flat = np.asarray(storage, dtype=np.dtype(dtype))

    # Convert to tuples and scale by element width
    shape = tuple(shape)  # type: ignore
    offset *= flat.itemsize  # type: ignore
    strides = tuple(x * flat.itemsize for x in strides)  # type: ignore

    # Construct the strided array
    strided = np.ndarray(
      shape=shape,
      dtype=flat.dtype,
      buffer=flat,
      offset=offset,
      strides=strides,
    )

    # Set readonly if needed
    if not self._writeable:
      strided.setflags(write=False)

    return strided

  def _get_validity(self: SymbolicValue) -> SymbolicValue:
    """
    Returns a concolic condition representing the internal consistency of the concolic ndarray.

    This should be used only when the ndarray is a SymbolicValue (i.e. when it has been synthesized
    by the SMT solver) to make the solver aware of validity conditions. As such, the following
    invariants are checked:
      - `storage` is a concrete instance of `Array[dtype]`
      - `shape` is a concrete tuple of concrete integers
      - `offset` is a concrete integer
      - `strides` is a concrete tuple of concrete integers

    ...in addition to the analogous symbolic conditions.
    """
    concrete_self = self.get_value()
    symbolic_heap_cell = util.dereference(self.get_formula())
    symbolic_members = util.get_object_members(symbolic_heap_cell)
    symbolic_self = util.get_object(symbolic_heap_cell)

    # Initialize validity conditions
    concrete_validity = True
    symbolic_validity_conjuncts: list[Formula] = [
      util.is_reference(self.get_formula()),
      util.is_object(symbolic_heap_cell),
      util.class_type_recognizer('ndarray')(
        util.get_object_type(symbolic_heap_cell)),
    ]

    # Validate the storage
    concrete_storage = getattr(concrete_self, 'storage', None)
    symbolic_storage = symbolic_self[smt.StringVal('storage')]
    concrete_validity &= isinstance(concrete_storage, Array)
    symbolic_validity_conjuncts += [
      symbolic_members[smt.StringVal('storage')],
      util.is_reference(symbolic_storage),
      smt.Or(
        util.is_floatarray(util.dereference(symbolic_storage)),
        util.is_intarray(util.dereference(symbolic_storage)),
        util.is_boolarray(util.dereference(symbolic_storage)),
      ),
    ]

    # Validate shape
    concrete_shape = getattr(concrete_self, '_shape', None)
    concolic_shape = makeSymbolicValue(
      v=concrete_shape, formula=symbolic_self[smt.StringVal('_shape')])
    shape_valid = _validate_shape_like(concolic_shape)
    concrete_validity &= shape_valid.get_value()
    symbolic_validity_conjuncts += [
      symbolic_members[smt.StringVal('_shape')],
      shape_valid.get_formula()
    ]

    # If shape or storage is concretely bad, skip further checks which depend on their values
    if not concrete_validity:
      return makeSymbolicValue(v=False, formula=smt.And(*symbolic_validity_conjuncts))

    # Get the rank from now-validated shape
    rank = _shape_like_rank(concolic_shape)

    # Validate strides against the concrete rank obtained from shape
    concrete_strides = getattr(concrete_self, 'strides', None)
    concolic_strides = makeSymbolicValue(
      v=concrete_strides, formula=symbolic_self[smt.StringVal('strides')])
    # type: ignore
    strides_valid = _validate_shape_like(
      concolic_strides, expected_rank=rank,  # type: ignore
      require_nonnegative=False)
    concrete_validity &= strides_valid.get_value()
    symbolic_validity_conjuncts += [
      symbolic_members[smt.StringVal('strides')],
      strides_valid.get_formula()
    ]

    # Validate offset
    concrete_offset = getattr(concrete_self, 'offset', None)
    symbolic_offset = symbolic_self[smt.StringVal('offset')]
    concrete_validity &= type(concrete_offset) is int and concrete_offset >= 0
    symbolic_validity_conjuncts += [
      symbolic_members[smt.StringVal('offset')],
      util.is_int(symbolic_offset),
      util.get_int(symbolic_offset) >= smt.IntVal(0)
    ]

    # Stop before layout validation if something is invalid at this point
    if not concrete_validity:
      return makeSymbolicValue(v=False, formula=smt.And(*symbolic_validity_conjuncts))

    # Validate the view layout against storage
    concolic_storage = makeSymbolicValue(
      v=concrete_storage, formula=symbolic_storage)
    concolic_offset = makeSymbolicValue(
      v=concrete_offset, formula=symbolic_offset)
    layout_valid = _validate_view_layout(
      concolic_storage, concolic_shape, concolic_offset, concolic_strides, symbolic_rank_link=True)
    concrete_validity &= layout_valid.get_value()
    symbolic_validity_conjuncts.append(layout_valid.get_formula())

    # Validate the writeable field
    concrete_writeable = getattr(concrete_self, '_writeable', None)
    symbolic_writeable = symbolic_self[smt.StringVal('_writeable')]
    concrete_validity &= type(concrete_writeable) is bool
    symbolic_validity_conjuncts += [
      symbolic_members[smt.StringVal('_writeable')],
      util.is_bool(symbolic_writeable)
    ]

    # Collapse the conjunction to a single condition
    return makeSymbolicValue(v=concrete_validity, formula=smt.And(*symbolic_validity_conjuncts))

  def _ensure_validity(self: 'ndarray | SymbolicValue') -> None:
    """
    For a concolic/synthesized ndarray (where self is a SymbolicValue), branches on and asserts a
    condition representing the internal consistency of the ndarray. After invoking this method,
    other ndarray methods can assume the validity of its fields and structure.

    If the ndarray stores its own symbolic state (i.e. it was constructed in Pythonland), this
    method does nothing.
    """
    if not isinstance(self, SymbolicValue):
      # Do nothing for constructed ndarrays
      return

    # The ndarray was synthesized; branch on its validity
    internal_validity = ndarray._get_validity(self)
    if internal_validity.get_value():
      # If the ndarray is already valid, make an assertion to track the symbolic validity
      make_assertion(internal_validity)
    else:
      # We only record_path if concretely invalid, so the engine will solve for negation
      record_path(internal_validity)
      raise ValueError("ndarray instance is not internally consistent")

  def _ensure_writeable(self: 'ndarray | SymbolicValue') -> None:
    """
    Ensures the array is writeable, branching and throwing if not.
    Only branches if the array was synthesized (otherwise writeable is concrete).
    """
    if isinstance(self, SymbolicValue):
      # If the array is synthesized, branch on the writeable flag
      # self._writeable becomes concolic from SV member access
      if self.get_value()._writeable:
        make_assertion(self._writeable)
      else:
        record_path(self._writeable)
        raise ValueError("array is readonly")
    elif not self._writeable:
      # Not synthesized; _writeable flag is concretely false
      raise ValueError("array is readonly")

  @staticmethod
  def _is_ndarray(obj: Any) -> SymbolicValue:
    """
    Returns a concolic condition representing whether the given object is an ndarray instance.
    """
    if isinstance(obj, SymbolicValue):
      c_result = isinstance(obj.get_value(), ndarray)

      # If Any formula, do the actual symbolic type check
      s_obj = obj.get_formula()
      if util.is_any(s_obj):
        s_result = smt.And(util.is_reference(s_obj),
                           util.is_object(util.dereference(s_obj)),
                           util.class_type_recognizer('ndarray')(
            util.get_object_type(util.dereference(s_obj))))
      else:
        s_result = smt.BoolVal(c_result)
    else:
      c_result = isinstance(obj, ndarray)
      s_result = smt.BoolVal(c_result)

    return makeSymbolicValue(v=c_result, formula=s_result)

  @property
  def shape_tuple(self: 'ndarray | SymbolicValue') -> ShapeLikeTuple:
    """
    Gets the shape of the array, normalized to a concrete tuple of (possibly concolic) values.

    Internal methods should almost always favor `._shape`, which is the actual shape provided
    in construction or from synthesis and retains symbolic rank information. This property
    is aliased as `.shape` on the shim ndarray class.
    """
    self._ensure_validity()

    backing_shape = self._shape
    rank = _shape_like_rank(backing_shape)

    shape = []
    for i in range(rank.get_value()):
      concrete, symbolic = _shape_like_get(backing_shape, i)
      shape.append(makeSymbolicValue(v=concrete, formula=symbolic))

    return tuple(shape)

  @property
  def dtype(self: 'ndarray | SymbolicValue') -> DType:
    """
    Gets the concrete dtype of the array.
    """
    # Validate internal structure if synthesized
    self._ensure_validity()

    # If self is a SymbolicValue, self.storage goes through SV machinery and is an SV
    # If self is concrete, we store Array as an SV anyway
    return Array.get_type(self.storage)  # type: ignore

  @property
  def size(self: 'ndarray | SymbolicValue') -> SymbolicValue:
    """
    Gets the flattened size of the array (the number of elements it touches).
    """
    # Validate internal structure if synthesized
    self._ensure_validity()

    return _get_flattened_size(self._shape)

  @property
  def ndim(self: 'ndarray | SymbolicValue') -> SymbolicValue:
    """
    Gets the rank of the array.
    """
    # Validate internal structure if synthesized
    self._ensure_validity()

    return _shape_like_rank(self._shape)

  @property
  def writeable(self: 'ndarray | SymbolicValue') -> bool:
    """
    Currently only internal; equivalent to flags.writeable. Concrete.
    """
    # Validate internal structure if synthesized
    self._ensure_validity()

    if isinstance(self, SymbolicValue):
      return self.get_value()._writeable

    return self._writeable

  @classmethod
  def _from_storage(cls,
                    storage: SymbolicValue,
                    shape: ShapeLike,
                    offset: int | SymbolicValue = 0,
                    strides: ShapeLike | None = None,
                    order: Literal['C', 'F'] | None = None,
                    writeable: bool = True,
                    skip_validation: bool = False) -> 'ndarray':
    """
    Constructs an ndarray as a view of an existing backing array.
    The new array's dtype is derived from the backing array's type.

    If called from an internal method that guarantees validity by construction,
    `skip_validation` is set to True to avoid branching on an invariant.
    """
    # These params are unsupported as of now, make sure they are their default values
    assert order is None or order == 'C'

    # Get the default strides if not provided
    do_symbolic_rank_link = True
    if strides is None:
      # Validate the shape first
      if not skip_validation:
        shape_valid = _validate_shape_like(shape)
        record_path(shape_valid)
        assert shape_valid.get_value()

      # Compute the default strides
      strides = _default_strides(shape)
      do_symbolic_rank_link = False

    if not skip_validation:
      # Validate this view layout against the storage
      layout_valid = _validate_view_layout(
        storage, shape, offset, strides, symbolic_rank_link=do_symbolic_rank_link)
      record_path(layout_valid)
      assert layout_valid.get_value()

    # Set up the ndarray properties
    array = cls.__new__(cls)
    array.storage = storage
    array._shape = shape
    array.offset = offset
    array.strides = strides
    array._writeable = writeable

    return array

  def _recreate(self: 'ndarray | SymbolicValue',
                shape: ShapeLike,
                offset: int | SymbolicValue = 0,
                strides: ShapeLike | None = None,
                order: Literal['C', 'F'] | None = None,
                *,
                writeable: bool | None = None,
                skip_validation: bool = False) -> 'ndarray':
    """
    Creates an ndarray with the same type as the input and the given view layout.

    Used instead of `_from_storage` to preserve the type of the input (i.e. to always
    return the ndarray shim class rather than an instance of impl.ndarray).

    If writeable is not provided, forwards the value of the instance the method is
    being called on (fully concrete).
    """
    cls = self.get_value().__class__ if isinstance(
      self, SymbolicValue) else self.__class__

    # Forward value of the writeable flag, if none was set explicitly
    if writeable is None:
      writeable = self.writeable

    return cls._from_storage(self.storage, shape, offset,  # type: ignore
                             strides, order, writeable, skip_validation)

  def view(self: 'ndarray | SymbolicValue', dtype: DType | InterceptType | None = None, typ: type | None = None) -> 'ndarray':
    # Validate internal structure if synthesized
    self._ensure_validity()

    # Currently don't support dtype reinterpretation or ndarray subclasses
    assert dtype is None
    assert typ is None

    # Construct a view with the same layout as this array
    return self._recreate(self._shape, self.offset, self.strides, None, writeable=self.writeable, skip_validation=True)

  def __getitem__(self: 'ndarray | SymbolicValue', raw_index_args: IndexArg | tuple[IndexArg, ...]) -> 'SymbolicValue | ndarray':
    """
    Currently supports only numpy's "basic indexing": ints, slices, ellipses, and concolic
    equivalents. Returns either a scalar value or a view into this ndarray.
    """
    self._ensure_validity()

    # Wrap args in a tuple if we got a single int/slice/whatever
    raw_index_args = _normalize_tuple_args(raw_index_args)

    # Validate the index arguments
    index_args_valid = _validate_basic_index(self._shape, raw_index_args)
    if index_args_valid.get_value():
      make_assertion(index_args_valid)
    else:
      record_path(index_args_valid)
      raise ValueError("invalid args for basic indexing")

    # Normalize args (also branches on Anys that may be int/none) and resolve them
    index_args, is_scalar_read = _normalize_basic_index(
      self._shape, raw_index_args)
    result_shape, result_offset, result_strides = _resolve_basic_index(
      self._shape, self.offset, self.strides, index_args)

    # If this is a scalar read, return the value from the backing array
    record_path(is_scalar_read)
    if is_scalar_read.get_value():
      # Scalar means a single read at the base offset
      return Array.get(self.storage, result_offset)  # type: ignore

    # Otherwise we return a view
    return self._recreate(result_shape, result_offset, result_strides, order=None, skip_validation=True)

  def __setitem__(self: 'ndarray | SymbolicValue', raw_index_args: IndexArg | tuple[IndexArg, ...], item: Scalar | SymbolicValue) -> None:
    """
    Currently supports scalar and array-copy writes with numpy's basic indexing scheme.
    """
    self._ensure_validity()
    self._ensure_writeable()

    # Wrap args in a tuple if we got a single int/slice/whatever
    raw_index_args = _normalize_tuple_args(raw_index_args)

    # Validate the index arguments
    index_args_valid = _validate_basic_index(self._shape, raw_index_args)
    if index_args_valid.get_value():
      make_assertion(index_args_valid)
    else:
      record_path(index_args_valid)
      raise ValueError("invalid args for basic indexing")

    # Normalize args (also branches on Anys that may be int/none) and resolve them
    index_args, _ = _normalize_basic_index(
      self._shape, raw_index_args)
    result_shape, result_offset, result_strides = _resolve_basic_index(
      self._shape, self.offset, self.strides, index_args)

    # Construct the indexed view
    write_view = self._recreate(
      result_shape, result_offset, result_strides, order=None, skip_validation=True)

    # Determine whether the item to write is a scalar or an ndarray
    c_is_array: bool
    s_is_array: Formula

    # Can only be an ndarray if the symbolic value is an Any
    if isinstance(item, SymbolicValue):
      c_item, s_item = item.get_value(), item.get_formula()
      c_is_array = isinstance(c_item, ndarray)

      if util.is_any(s_item):
        # If the item is an Any, it could be an ndarray or a scalar
        s_is_array = smt.And(
          util.is_reference(s_item),
          util.is_object(util.dereference(s_item)),
          util.class_type_recognizer('ndarray')(
            util.get_object_type(util.dereference(s_item))))
      else:
        # Otherwise, it must be a scalar (we'll check validity later)
        s_is_array = smt.BoolVal(False)
    else:
      # Concrete
      c_is_array = isinstance(item, ndarray)
      s_is_array = smt.BoolVal(c_is_array)

    # Branch on whether we're writing an array (only possible if the symbolic item is Any)
    is_array = makeSymbolicValue(v=c_is_array, formula=s_is_array)
    if isinstance(item, SymbolicValue) and util.is_any(item.get_formula()):
      record_path(is_array)
    if is_array.get_value():
      # For an array, we can just defer to copyto
      from . import operations
      operations.copyto(write_view, item, casting='unsafe')  # type: ignore
      return

    # Otherwise, the item is a scalar

    # Validate the scalar type
    c_valid_scalar: bool
    s_valid_scalar: Formula
    if isinstance(item, SymbolicValue):
      c_item, s_item = item.get_value(), item.get_formula()
      c_valid_scalar = type(c_item) in (int, float, bool)

      if util.is_any(s_item):
        # Any needs its type constrained
        s_valid_scalar = smt.Or(
          util.is_int(s_item),
          util.is_float(s_item),
          util.is_bool(s_item))
      else:
        s_valid_scalar = smt.BoolVal(s_item.sort() in (
          smt.IntSort(), util.float_sort, smt.BoolSort()))
    else:
      c_valid_scalar = type(item) in (int, float, bool)
      s_valid_scalar = smt.BoolVal(c_valid_scalar)

    # Branch on validity if not concretely valid
    valid_scalar = makeSymbolicValue(v=c_valid_scalar, formula=s_valid_scalar)
    if not valid_scalar.get_value():
      record_path(valid_scalar)
      raise TypeError("invalid type for scalar ndarray write")

    # Otherwise just assert validity
    make_assertion(valid_scalar)

    # Need to freeze rank and dims to iterate indices concretely
    c_dims = _freeze_shape_dims(write_view._shape)

    # Iterate concrete indices
    dtype = self.dtype
    for coords in itertools.product(*map(range, c_dims)):
      # Resolve concrete coordinates to a flat index
      index = _resolve_scalar_coordinates(
        write_view._shape, write_view.offset, write_view.strides, coords)

      # Write into the backing array
      Array.set(write_view.storage, index,  # type: ignore
                _cast_scalar_unsafe(item, dtype), skip_validation=True)

  def _read_scalar_unsafe(self: 'ndarray | SymbolicValue',
                          coords: tuple[int, ...],
                          *,
                          dtype: DType | None = None) -> SymbolicValue:
    """
    Reads a scalar value from a fully concrete coordinate, skipping
    any validity checks.

    If `dtype` is provided, performs an unsafe cast to that type.
    """
    index = _resolve_scalar_coordinates(
      self._shape, self.offset, self.strides, coords)
    value = Array.get(self.storage, index,  # type: ignore
                      skip_validation=True)

    # Cast if the caller specified a data type
    if dtype is not None:
      value = _cast_scalar_unsafe(value, dtype)

    return value

  def _write_scalar_unsafe(self: 'ndarray | SymbolicValue',
                           coords: tuple[int, ...],
                           value: Scalar | SymbolicValue) -> None:
    """
    Writes a scalar value to a fully concrete coordinate, skipping
    any validity checks and type branching (this performs an unsafe
    cast, so the value is assumed to be of the correct type).
    """
    index = _resolve_scalar_coordinates(
      self._shape, self.offset, self.strides, coords)

    # Get dtype from the storage to avoid a call to _ensure_validity
    dtype = Array.get_type(self.storage)  # type: ignore
    Array.set(self.storage,  # type: ignore
              index, _cast_scalar_unsafe(value, dtype), skip_validation=True)

  def transpose(self, axes: ShapeLike | None = None) -> 'ndarray':
    """
    Returns a view with its shape and stride axes permutated.

    If no permutation is provided, the axes are reversed.
    """
    # TODO: numpy's ndarray::transpose accepts either a permutation tuple or *params; we need to accept *args and do extra validation
    #       we need some ITE for a single-element axes containing something that could be int or tuple
    from . import views
    return views.transpose(self, axes)

  @property
  def T(self) -> 'ndarray':
    """
    Shorthand property for transpose.
    """
    return self.transpose()

  def swapaxes(self, axis1: int | SymbolicValue, axis2: int | SymbolicValue) -> 'ndarray':
    """
    Returns a view with the given axes interchanged.
    """
    from . import views
    return views.swapaxes(self, axis1, axis2)


def ndim(array: ndarray | SymbolicValue) -> SymbolicValue:
  """
  Alias for array.ndim.
  """
  return array.ndim


def zeros(cls: type[ndarray],
          shape: ShapeLike,
          dtype: DType | InterceptType | None = None,
          order: Literal['C', 'F'] | None = 'C',
          *,
          device=None,
          like=None) -> ndarray:
  # These params are unsupported as of now, make sure they are their default values
  assert device is None
  assert like is None
  assert order == 'C'

  # Normalize and validate dtype
  dtype = _normalize_dtype(dtype)

  # If dtype was not specified
  if dtype is float:
    # Create an ndarray with the default type (float)
    array = cls(shape, dtype=float, order=order)

    # Set all elements to zero
    for i in range(array.size.get_value()):
      Array.set(array.storage, factories.lift_value(  # type: ignore
        i), factories.lift_value(0.0))

  # If dtype is an int
  elif dtype is int:
    # Create an integer array
    array = cls(shape, dtype=int, order=order)

    # Set all elements to zero
    for i in range(array.size.get_value()):
      Array.set(array.storage, factories.lift_value(  # type: ignore
        i), factories.lift_value(0))

  # If dtype is a boolean
  elif dtype is bool:
    # Create a boolean array
    array = cls(shape, dtype=bool, order=order)

    # Set all elements to zero
    for i in range(array.size.get_value()):
      Array.set(array.storage, factories.lift_value(  # type: ignore
        i), factories.lift_value(False))

  else:
    # No other types are supported for this function
    raise NotImplementedError

  return array
