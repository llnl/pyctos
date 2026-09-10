# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from abc import ABC, abstractmethod
import itertools
from types import EllipsisType
from typing import Any, Literal, NamedTuple, TypeAlias, final

from symbex.globals.globals import make_assertion, record_path
from symbex.symbolic import factories, util
from symbex.types.array import Array
from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue

from .names import *
from ..util import *
from ..array import ndarray
from ..views import broadcast_shapes

from symbex.smtlib import get_smt_lib
smt = get_smt_lib()


__all__ = [
  'UFuncSignature', 'UFunc',
]


# Describes a single ufunc operand passed into the call `*args`
UFuncOperandArg: TypeAlias = Scalar | ndarray | SymbolicValue

# Describes the ufunc `out=` parameter
UFuncOutSlot: TypeAlias = ndarray | SymbolicValue | None
UFuncOutArg: TypeAlias = tuple[UFuncOutSlot, ...] | UFuncOutSlot | EllipsisType

# Describes a requested signature passed to ufunc `signature=` before normalization
UFuncSignatureArg: TypeAlias = tuple[DType |
                                     InterceptType | None, ...] | str

# Describes the return value of a ufunc call (tuple iff multiple outputs)
UFuncResult: TypeAlias = ndarray | SymbolicValue | tuple[ndarray |
                                                         SymbolicValue, ...]

# Describes the axis argument for reduction
AxisArg: TypeAlias = int | tuple[int |
                                 SymbolicValue, ...] | SymbolicValue | None


class UFuncSignature(NamedTuple):
  """
  Describes a registered loop signature for a ufunc.
  """

  inputs: tuple[DType, ...]
  outputs: tuple[DType, ...]


def _generalize_dtype(dtype: Any) -> DType:
  """
  Returns the generalized form of the given numpy dtype (e.g. float for float32).
  """
  import numpy
  dtype = numpy.dtype(dtype)

  if numpy.issubdtype(dtype, numpy.integer):
    return int

  if numpy.issubdtype(dtype, numpy.floating):
    return float

  if numpy.issubdtype(dtype, numpy.bool_):
    return bool

  raise NotImplementedError(
    f'numpy dtype {dtype} is outside the set of modeled types')


class Operand:
  """
  Describes a preprocessed ufunc operand (ndarray or scalar) with additional
  metadata and helpers for ufunc internals.
  """
  value: ndarray | SymbolicValue
  is_array: bool
  dtype: DType
  shape: ShapeLike

  def __init__(self,
               arg: UFuncOperandArg) -> None:
    """
    Constructs an `Operand` and attaches concolic metadata. Assumes the input
    is validated (i.e. is a scalar, an ndarray, or an SV that represents a
    scalar or an ndarray).

    If the input is an SV with Any formula, branches on its actual type.
    """
    # We always lift scalar operands to SV
    if not isinstance(arg, ndarray):
      arg = factories.lift_value(arg)

    # Specialize Any-sort arguments to freeze their type
    if isinstance(arg, SymbolicValue) and util.is_any(arg.get_formula()):
      c_arg, s_arg = arg.get_value(), arg.get_formula()

      if type(c_arg) is int:
        record_path(makeSymbolicValue(v=True, formula=util.is_int(s_arg)))
        arg = util.narrow_from_any_t(arg, int)
      elif type(c_arg) is float:
        record_path(makeSymbolicValue(v=True, formula=util.is_float(s_arg)))
        arg = util.narrow_from_any_t(arg, float)
      elif type(c_arg) is bool:
        record_path(makeSymbolicValue(v=True, formula=util.is_bool(s_arg)))
        arg = util.narrow_from_any_t(arg, bool)
      else:
        # We can just branch on is_reference since the input has been validated to be an ndarray if non-scalar
        record_path(makeSymbolicValue(
          v=True, formula=util.is_reference(s_arg)))

    # Handle ndarray operand
    if isinstance(arg, ndarray) or isinstance(arg.get_value(), ndarray):
      arg._ensure_validity()

      self.value = arg
      self.is_array = True
      self.dtype = arg.dtype
      self.shape = arg._shape
      return

    # Handle scalar operand
    self.value = arg
    self.is_array = False
    self.dtype = type(arg.get_value())
    self.shape = ()

  def read_unsafe(self,
                  coords: tuple[int, ...],
                  dtype: DType | None = None) -> SymbolicValue:
    """
    Reads the value at a concrete coordinate, skipping validity checks
    (except verifying that coordinates are empty for scalars).

    If `dtype` is provided, performs an unsafe cast to that type.
    """
    if not self.is_array:
      assert coords == ()
      if dtype is not None:
        return _cast_scalar_unsafe(self.value,  # type: ignore[arg-type]
                                   dtype=dtype)

      return self.value  # type: ignore[return-value]

    return self.value._read_scalar_unsafe(coords, dtype=dtype)

  def write_unsafe(self,
                   coords: tuple[int, ...],
                   value: Scalar | SymbolicValue) -> None:
    """
    Writes a scalar value at a concrete coordinate, skipping validation.
    Fails if the operand is a scalar.
    """
    if not self.is_array:
      raise TypeError('cannot write to scalar ufunc operand')

    self.value._write_scalar_unsafe(coords, value)


class UFunc(ABC):
  """
  Base class for ufuncs with any number of inputs and outputs.

  NOTE: technically, reorderability is a property of the resolved loop
  signature and not of the ufunc, but we don't currently model any
  dtype-specific loops so our simplification is correct for now. An
  example of this behavior is `numpy.add` with strings (since addition
  becomes non-commutative concatenation).
  """
  nin: int
  nout: int
  nargs: int
  identity: SymbolicValue | None

  def __init__(self,
               name: UFuncName,
               nin: int,
               nout: int,
               identity: SymbolicValue | None | Unset = UNSET,
               reorderable: bool = False) -> None:
    self._name = name
    self.__name__ = name

    # TODO: model remaining public ufunc properties
    self.nin = nin
    self.nout = nout
    self.nargs = nin + nout

    # Explicit `identity=None` is different from omitted, in that it sets `reorderable`
    if isinstance(identity, Unset):
      self.identity = None
      self._reorderable = reorderable
    else:
      self.identity = identity
      self._reorderable = True

  @abstractmethod
  def _apply(self,
             values: tuple[SymbolicValue, ...],
             signature: UFuncSignature) -> tuple[SymbolicValue, ...]:
    """
    Applies a single resolved loop operation to scalar input values, which
    are already cast to corresponding input types from the signature.

    The length of `values` is equal to `self.nin`; this method returns a
    tuple of scalars with length equal to `self.nout`.

    Outputs should be of the correct types according to `signature`.
    """
    raise NotImplementedError

  @final
  def __call__(self,
               *args: UFuncOperandArg,
               out: UFuncOutArg = None,
               where: bool = True,
               casting: Casting = 'same_kind',
               order: Literal['C', 'F', 'A', 'K'] = 'K',
               dtype: DType | InterceptType | None | Unset = UNSET,
               subok: bool = True,
               signature: UFuncSignatureArg | Unset = UNSET) -> UFuncResult:
    """
    Applies the ufunc operation to the given inputs.

    Returns a single scalar/ndarray for single output, or a tuple if
    there are multiple outputs.

    NumPy analog: umath/ufunc_object.c::ufunc_generic_fastcall
    """
    # Check kwargs and normalize the requested dtype, if any
    self._check_call_args(*args, out=out, where=where, casting=casting,
                          order=order, dtype=dtype, subok=subok, signature=signature)

    # Validate and normalize operands and outputs
    # TODO: numpy allows out to be passed positionally in *args
    operands = self._resolve_operands(*args)
    normalized_out, force_array_return = self._normalize_out_arg(out)

    # Compute the requested type tuple from `signature`/`dtype` kwargs
    type_tuple = self._get_type_tuple(signature, dtype)

    # Resolve the loop signature
    loop_signature = self._resolve_call_signature(
      operands, normalized_out, type_tuple, casting)

    # Validate out arrays and collect shapes that participate in the broadcast
    out_shapes: list[ShapeLike] = []
    for slot in normalized_out:
      if slot is None:
        continue

      slot._ensure_validity()
      out_shapes.append(slot._shape)

    # Broadcast inputs and supplied out arrays to the compute the result shape
    result_shape = broadcast_shapes(*(op.shape for op in operands),
                                    *out_shapes)

    # Outputs participate in the result shape, but cannot be broadcast themselves
    # So we validate that they exactly match the result shape
    c_out_shapes_valid = True
    s_out_shapes_valid_conjuncts: list[Formula] = [smt.BoolVal(True)]
    for slot in normalized_out:
      if slot is None:
        continue

      # Check the out slot's validity and ensure it's writeable
      slot._ensure_validity()
      slot._ensure_writeable()

      # Check the slot's shape against the result shape
      # Validate rank
      slot_rank = _shape_like_rank(slot._shape)
      c_out_shapes_valid &= (slot_rank.get_value() == len(result_shape))
      s_out_shapes_valid_conjuncts.append(
        slot_rank.get_formula() == smt.IntVal(len(result_shape)))

      # Validate shape elements
      # We can safely loop to min of result rank and slot rank, since if the lengths mismatch we'll catch it
      for i in range(min(len(result_shape), slot_rank.get_value())):
        c_slot_dim, s_slot_dim = _shape_like_get(slot._shape, i)
        result_dim = result_shape[i]

        c_out_shapes_valid &= (c_slot_dim == result_dim.get_value())
        s_out_shapes_valid_conjuncts.append(
          s_slot_dim == result_dim.get_formula())

    # Check validity of the out shapes atomically
    out_shapes_valid = makeSymbolicValue(
      v=c_out_shapes_valid, formula=smt.And(*s_out_shapes_valid_conjuncts))
    record_path(out_shapes_valid)
    if not out_shapes_valid.get_value():
      raise ValueError(
        f'output shape or shapes do not match broadcasted result shape')

    # Resolve the arrays to write to (constructing where necessary)
    out_arrays = self._resolve_out_arrays(
      normalized_out, result_shape, loop_signature.outputs)

    # Execute the actual loop
    self._execute_loop(operands, out_arrays, result_shape, loop_signature)

    # Format the results and return
    results: list[ndarray | SymbolicValue] = []
    for out_slot, out_array in zip(normalized_out, out_arrays):
      # Turn 0-d arrays into scalars for return, if conditions are met
      if out_slot is None and len(result_shape) == 0 and not force_array_return:
        # Manually read from the array here to skip all the branching and validation of indexing the ndarray
        index = _resolve_scalar_coordinates(
          out_array._shape, out_array.offset, out_array.strides, ())
        results.append(Array.get(out_array.storage,  # type: ignore
                       index, skip_validation=True))
      else:
        results.append(out_array)

    return results[0] if self.nout == 1 else tuple(results)

  @final
  def _check_call_args(self,
                       *args: UFuncOperandArg,
                       out: UFuncOutArg,
                       where: bool,
                       casting: Casting,
                       order: Literal['C', 'F', 'A', 'K'],
                       dtype: DType | InterceptType | None | Unset,
                       subok: bool,
                       signature: UFuncSignatureArg | Unset) -> None:
    """
    Checks kwargs to `__call__`, rejecting non-default values for those we
    don't model. Also rejects receiving values for both the `dtype` and
    `signature` args as these are mutually exclusive.
    """
    # Check number of operand args against arity
    if len(args) != self.nin:
      raise TypeError(
        f'ufunc "{self._name}" expects {self.nin} arguments, received {len(args)}')

    # TODO: numpy allows out to be passed positionally in *args, rejecting the kwarg
    if where is not True:
      raise NotImplementedError('ufunc `where` masks are unsupported')
    if order != 'K':
      raise NotImplementedError('ufunc `order` specification is not supported')
    if subok is not True:
      raise NotImplementedError('ufunc `subok` override is not supported')

    if not isinstance(dtype, Unset) and not isinstance(signature, Unset):
      raise TypeError(
        "ufunc `dtype` and `signature` args are mutually exclusive")

  def _resolve_call_signature(self,
                              operands: tuple[Operand, ...],
                              out: tuple[UFuncOutSlot, ...],
                              type_tuple: tuple[DType | None, ...] | None,
                              casting: Casting) -> UFuncSignature:
    """
    Resolves the loop signature this ufunc will use for a normal call
    (reduction semantics are different).

    Defers to the actual ufunc's `resolve_dtypes` under the live numpy
    installation.

    NumPy analog: umath/ufunc_object.c::py_resolve_dtypes_generic
    (which is the actual `resolve_dtypes` we defer to)
    """
    # We defer to the live numpy installation to resolve the types the loop will use
    import numpy as live_numpy
    live_ufunc: live_numpy.ufunc = getattr(live_numpy, self._name)

    # Collect dtypes to pass into the actual ufunc's `resolve_dtypes`
    resolve_dtypes_arg: list[Any] = []
    for op in operands:
      if op.is_array or op.dtype is bool:
        # Array dtypes (and bool) get converted to specified types
        resolve_dtypes_arg.append(live_numpy.dtype(op.dtype))
      else:
        # Scalars keep their weak Python types
        resolve_dtypes_arg.append(op.dtype)

    # Collect the output types
    for slot in out:
      if slot is None:
        resolve_dtypes_arg.append(None)
      else:
        resolve_dtypes_arg.append(live_numpy.dtype(slot.dtype))

    kwargs: dict[str, Any] = {'casting': casting}
    if type_tuple is not None:
      # Specify dtypes in the signature where provided
      kwargs['signature'] = tuple(None if dtype is None else live_numpy.dtype(dtype)
                                  for dtype in type_tuple)

    # Get the dtypes the live ufunc would use
    live_dtypes = live_ufunc.resolve_dtypes(
      tuple(resolve_dtypes_arg), **kwargs)

    # Generalize fixed-width dtypes back to our reduced set
    return UFuncSignature(
      tuple(map(_generalize_dtype, live_dtypes[:self.nin])),
      tuple(map(_generalize_dtype, live_dtypes[self.nin:])))

  @final
  def _execute_loop(self,
                    operands: tuple[Operand, ...],
                    out_arrays: tuple[ndarray | SymbolicValue, ...],
                    result_shape: tuple[SymbolicValue, ...],
                    signature: UFuncSignature) -> None:
    """
    Executes the selected loop signature over the inputs, writing to the
    provided out arrays.
    """
    assert len(operands) == self.nin
    assert len(out_arrays) == self.nout

    # Freeze rank and dims since we loop over indices concretely
    c_result_dims = _freeze_shape_dims(result_shape)

    # Now loop over array operands and freeze their rank/shape
    for op in operands:
      if not op.is_array:
        continue

      # Ensure validity of synthesized arrays
      op.value._ensure_validity()  # type: ignore

      # Freeze the rank and all dimensions
      _freeze_shape_dims(op.shape)

    # Validate any synthesized out arrays
    for out_array in out_arrays:
      out_array._ensure_validity()  # type: ignore
      out_array._ensure_writeable()  # type: ignore

    # Collect the values to be written without actually assigning them, in case out shares memory with in
    op_ranks = [_shape_like_rank(op.shape).get_value() for op in operands]
    writes: list[tuple[tuple[int, ...], tuple[SymbolicValue, ...]]] = []
    for coords in itertools.product(*map(range, c_result_dims)):
      # Get the value from each input at this result coordinate
      values: list[SymbolicValue] = []
      for i, op in enumerate(operands):
        if op.is_array:
          # We have to shift indexing by the number of missing dimensions (broadcast semantics)
          rank_shift = len(result_shape) - op_ranks[i]

          # We map the result coordinate back into the coordinates for indexing this operand
          # Missing leading axes are skipped and broadcasted (size 1) axes always get coordinate 0
          source_coords: list[int] = []
          for axis in range(op_ranks[i]):
            c_dim, _ = _shape_like_get(op.shape, axis)
            source_coords.append(
              0 if c_dim == 1 else coords[axis + rank_shift])

          # Compute the concrete index into this operand to read at
          source_index = _resolve_scalar_coordinates(
            op.shape, op.value.offset, op.value.strides, tuple(source_coords))
          source_value = Array.get(op.value.storage,  # type: ignore
                                   source_index, skip_validation=True)

          # Cast the value to the corresponding input type of the loop signature
          values.append(_cast_scalar_unsafe(
            source_value, signature.inputs[i]))
        else:
          # Scalars give us a value directly; just cast it to the signature type
          values.append(_cast_scalar_unsafe(
            op.value, signature.inputs[i]))  # type: ignore

      # Apply the scalar function to the collected values
      outputs = self._apply(tuple(values), signature)

      # Validate and store the write value
      assert len(outputs) == self.nout
      writes.append((coords, outputs))

    # Now commit the writes to each output
    for coords, outputs in writes:
      for out_array, value in zip(out_arrays, outputs):
        # Cast the write value to the dtype of the output array
        out_array._write_scalar_unsafe(coords, value)

  @final
  def _resolve_operands(self, *args: UFuncOperandArg) -> tuple[Operand, ...]:
    """
    Validates that all inputs are either scalars or ndarrays.

    Following validation, constructs `Operand` instances for each argument
    (which branches on the type of `Any` symbols in the input) and returns
    these operands.
    """
    c_args_valid = True
    s_args_valid_conjuncts: list[Formula] = []
    for arg in args:
      c_arg_valid: bool
      s_arg_valid: Formula

      if isinstance(arg, SymbolicValue):
        c_arg = arg.get_value()
        s_arg = arg.get_formula()
        c_arg_valid = type(
          c_arg) in DTYPES_ALLOWED or isinstance(c_arg, ndarray)

        if util.is_any(s_arg):
          # If the argument is an Any, we need to ensure it wraps a scalar or ndarray
          s_arg_valid = smt.Or(util.is_int(s_arg),
                               util.is_float(s_arg),
                               util.is_bool(s_arg),
                               smt.And(util.is_reference(s_arg),
                                       util.is_object(
                                  util.dereference(s_arg)), util.class_type_recognizer('ndarray')(
                                  util.get_object_type(util.dereference(s_arg)))))
        else:
          # The argument is a non-Any SV; we know its kind concretely
          s_arg_valid = smt.BoolVal(c_arg_valid)

      else:
        # The argument is concrete
        c_arg_valid = type(arg) in DTYPES_ALLOWED or isinstance(arg, ndarray)
        s_arg_valid = smt.BoolVal(c_arg_valid)

      # Update the validity condition for the whole argument set
      c_args_valid &= c_arg_valid
      s_args_valid_conjuncts.append(s_arg_valid)

    # Build the validity condition
    args_valid = makeSymbolicValue(
      v=c_args_valid, formula=smt.And(*s_args_valid_conjuncts))
    record_path(args_valid)
    if not args_valid.get_value():
      raise TypeError('ufunc received one or more invalid arguments')

    # Construct the Operands and return
    return tuple(map(Operand, args))

  @final
  def _normalize_out_arg(self,
                         out: UFuncOutArg) -> tuple[tuple[UFuncOutSlot, ...], bool]:
    """
    Normalizes the `out=` argument, which may be an ndarray, None, a tuple
    of ndarray/None, or a literal ellipsis. If a tuple is passed, validates
    its length.

    An ellipsis is equivalent to passing None/empty tuple, but forces array
    output rather than raw scalars.

    Returns a tuple of ndarray/None of length nout, as well as a flag
    denoting whether 0-d results should avoid scalar conversion (set when
    the user passes `out=...`).

    NumPy analog: umath/ufunc_object.c::_set_full_args_out
    (also output parsing in ::ufunc_generic_fastcall)
    """
    # TODO: Support a symbolic tuple of none? Not sure we'd gain anything
    #       since a symbolic input could only ever be (None,)*nout
    # Ellipsis means unspecified types, forced array return
    if out is ...:
      return (None,) * self.nout, True

    # None means unspecified types but allowing scalar return
    if out is None:
      return (None,) * self.nout, False

    # If out is symbolic Any, it may be symbolic None
    if isinstance(out, SymbolicValue) and util.is_any(out.get_formula()):
      c_out_is_none = out.get_value() is None
      s_out_is_none = util.is_none(out.get_formula())

      # Branch on whether out=None
      record_path(makeSymbolicValue(v=c_out_is_none, formula=s_out_is_none))
      if c_out_is_none:
        return (None,) * self.nout, False

    # Normalize the out tuple
    out_tuple: tuple[UFuncOutSlot, ...]
    if type(out) is tuple:
      # If we got a tuple, validate its length
      if len(out) != self.nout:
        raise ValueError(
          f'invalid `out` argument: expected {self.nout} slots, got {len(out)}')
      out_tuple = out
    elif self.nout == 1:
      # If we got a single value and this is a single-output ufunc, normalize to a tuple
      out_tuple = (out,)  # type: ignore
    else:
      # Otherwise invalid
      raise TypeError(
        f'invalid `out` argument: expected an array or tuple of arrays')

    # Validate the elements of the out tuple
    c_out_valid = True
    s_out_valid_conjuncts: list[Formula] = [smt.BoolVal(True)]
    for slot in out_tuple:
      if slot is None:
        continue

      is_array = ndarray._is_ndarray(slot)
      c_out_valid &= is_array.get_value()
      s_out_valid_conjuncts.append(is_array.get_formula())

    out_valid = makeSymbolicValue(
      v=c_out_valid, formula=smt.And(*s_out_valid_conjuncts))
    record_path(out_valid)
    if not out_valid.get_value():
      raise TypeError(
        f'invalid `out` argument: elements must be ndarray or None')

    # We do not force array return on this path
    return out_tuple, False

  @final
  def _resolve_out_arrays(self,
                          out: tuple[UFuncOutSlot, ...],
                          result_shape: ShapeLike,
                          result_dtypes: tuple[DType, ...]) -> tuple[ndarray | SymbolicValue, ...]:
    """
    Resolves the normalized `out=` argument to a tuple of the actual ndarrays
    to write to. Any missing/None arrays are constructed here with the result
    shape and their corresponding result dtype.
    """
    assert len(out) == self.nout
    assert len(result_dtypes) == self.nout

    result: list[ndarray | SymbolicValue] = []
    for slot, dtype in zip(out, result_dtypes):
      if slot is None:
        # Missing slots get a newly constructed array with the result shape
        result.append(ndarray(shape=result_shape, dtype=dtype))
      else:
        result.append(slot)

    return tuple(result)

  @final
  def _get_type_tuple(self,
                      signature: UFuncSignatureArg | Unset,
                      dtype: DType | InterceptType | None | Unset) -> tuple[DType | None, ...] | None:
    """
    Resolves the `signature` and `dtype` kwargs, validating type and length
    (if a tuple is passed for `signature`) and normalizing both to a tuple
    of dtype/None, or None to indicate that no types are specified.

    Note the `signature` and `dtype` arguments are mutually exclusive. If
    provided, `signature` directly becomes the type tuple. If instead the
    `dtype` arg is provided, it becomes `(None,)*nin + (dtype,)*nout.

    We do not support numpy's special signature strings.

    NumPy analog: umath/ufunc_object.c::_get_fixed_signature
    """
    if dtype is None:
      # If dtype is specificed but is None, no type tuple
      return None

    if not isinstance(dtype, Unset):
      # If `dtype` is provided, it specifies all output types
      dtype = _normalize_dtype(dtype)
      return (None,) * self.nin + (dtype,) * self.nout

    # If neither is provided, no type tuple specified for resolution
    if isinstance(signature, Unset):
      return None

    # We don't support string signatures
    if isinstance(signature, str):
      raise NotImplementedError(
        "numpy signature strings not supported for ufunc `signature` argument")

    # Signature must be a tuple
    if not isinstance(signature, tuple):
      raise TypeError("ufunc `signature` argument must be a tuple")

    signature = tuple(_normalize_dtype(t) if (
      t is not None) else None for t in signature)

    # Validate the signature length
    if len(signature) != self.nargs:
      raise ValueError(f'ufunc "{self._name}" received `signature` with invalid length: '
                       f'expected {self.nargs}, got {len(signature)}')

    return signature

  @final
  def _ensure_reducelike_compatible(self) -> None:
    """
    Reduce-like methods are defined on all ufuncs, but throw a ValueError
    if the ufunc is not binary input, single output. This method handles
    that precondition.
    """
    # Note: conditions differ for some methods (at, outer) we don't yet model
    if self.nin != 2 or self.nout != 1:
      raise ValueError(f'{self._name} does not support reduce-like methods')

  def _resolve_reducelike_signature(self,
                                    operand: Operand,
                                    out: UFuncOutSlot,
                                    dtype: DType | InterceptType | None,
                                    enforce_uniform_args: bool) -> UFuncSignature:
    """
    Resolves the accumulator/input/output signature this ufunc will use
    for reduce-like methods (reduce, accumulate, etc.).

    Defers to the actual ufunc's `resolve_dtypes` under the live numpy
    installation.

    NumPy analog: umath/ufunc_object.c::py_resolve_dtypes_generic
    (reduction branch, defers to ::reducelike_promote_and_resolve)
    """
    # We defer to the live numpy installation to resolve the types the reduction will use
    import numpy as live_numpy
    live_ufunc: live_numpy.ufunc = getattr(live_numpy, self._name)

    # With reduce-like methods, dtype= becomes signature[0] (the accumulator dtype)
    req_signature = None
    if dtype is not None:
      req_signature = (live_numpy.dtype(_normalize_dtype(dtype)), None, None)

    # Reduction resolver takes (accumulator/out, input, result)
    # First slot candidate comes from out= and final slot is always unspecified
    dtypes = (None if out is None else live_numpy.dtype(out.dtype),
              live_numpy.dtype(operand.dtype),
              None)

    # Defer to live numpy for reduction type resolver
    if req_signature is not None:
      resolved = live_ufunc.resolve_dtypes(dtypes,
                                           signature=req_signature, casting='unsafe', reduction=True)
    else:
      # Omitted signature argument is NOT equivalent to signature=None
      resolved = live_ufunc.resolve_dtypes(dtypes,
                                           casting='unsafe', reduction=True)

    # Build the signature to return
    signature = UFuncSignature(tuple(map(_generalize_dtype, resolved[:2])),
                               tuple(map(_generalize_dtype, resolved[2:])))

    # Some reduce-like methods require uniform types across the resolved signature
    if enforce_uniform_args:
      acc_dtype, op_dtype = signature.inputs
      out_dtype, = signature.outputs

      if acc_dtype != op_dtype or op_dtype != out_dtype:
        raise TypeError(
          f'failed to resolve uniform reduction signature for {self._name}')

    return signature

  @final
  def _normalize_reducelike_out_arg(self,
                                    out: UFuncOutArg) -> tuple[UFuncOutSlot, bool]:
    """
    Normalizes the `out=` argument; like `_normalize_out_arg` specifically
    for reduce-like methods.

    Returns an ndarray or None, as well as a flag denoting whether 0-d
    results should be returned as arrays (when the user passes `out=...`).
    """
    # No specified out slot but force array return
    if out is ...:
      return None, True

    # May get concrete none or an Any-valued SV that is none
    if out is None:
      return None, False
    if isinstance(out, SymbolicValue) and util.is_any(out.get_formula()):
      # If we got Any-valued SV, whether out=None could vary symbolically
      c_is_none = out.get_value() is None
      s_is_none = util.is_none(out.get_formula())
      record_path(makeSymbolicValue(v=c_is_none, formula=s_is_none))
      if c_is_none:
        return None, False

    # Can be a concrete tuple of a single element; if so, unwrap it
    if type(out) is tuple:
      if len(out) != 1:
        raise ValueError(
          f'reduce-like ufunc methods received wrong number of entries for `out=`')

      out = out[0]
      if out is None:
        raise TypeError(f'elements of `out` tuple must be ndarrays')

    # Already handled None, so tuple element or direct arg must be ndarray here
    is_array = ndarray._is_ndarray(out)
    record_path(is_array)
    if not is_array.get_value():
      raise TypeError('ufunc `out` slots must be ndarray')

    return out, False  # type: ignore

  @final
  def _normalize_reducelike_axes(self,
                                 axis: AxisArg,
                                 rank: SymbolicValue) -> tuple[SymbolicValue, ...]:
    """
    Normalizes the `axis` arg for reduce-like methods.

    Takes in the array rank for bounds-checking and normalization; this
    rank should first be frozen to its concrete value by the caller.

    NumPy analog: umath/ufunc_object.c::_parse_axis
    """
    c_rank, s_rank = rank.get_value(), rank.get_formula()

    c_axis_is_none = (axis is None) or (isinstance(
      axis, SymbolicValue) and axis.get_value() is None)
    s_axis_is_none: Formula
    if isinstance(axis, SymbolicValue):
      # Only any-typed formula can be symbolically None
      s_axis_is_none = util.is_none(axis.get_formula()) if util.is_any(
        axis.get_formula()) else smt.BoolVal(False)
    else:
      s_axis_is_none = smt.BoolVal(c_axis_is_none)

    # Branch on whether axis=None
    # This can only vary symbolically if we got an Any-typed formula
    if isinstance(axis, SymbolicValue) and util.is_any(axis.get_formula()):
      record_path(makeSymbolicValue(v=c_axis_is_none, formula=s_axis_is_none))
    if c_axis_is_none:
      # None means reduce all axes
      return tuple(map(factories.lift_value, range(c_rank)))

    # Now we parse either a single integer or a tuple of ints
    c_is_single_axis: bool
    s_is_single_axis: Formula
    if isinstance(axis, SymbolicValue):
      c_axis, s_axis = axis.get_value(), axis.get_formula()
      c_is_single_axis = type(c_axis) is int
      s_is_single_axis = util.is_int(s_axis) if util.is_any(
        s_axis) else smt.BoolVal(s_axis.sort() == smt.IntSort())
    else:
      c_is_single_axis = type(axis) is int
      s_is_single_axis = smt.BoolVal(c_is_single_axis)

    # Branch on whether we were passed a single axis
    # This can only vary symbolically if we got an Any-typed formula
    if isinstance(axis, SymbolicValue) and util.is_any(axis.get_formula()):
      record_path(makeSymbolicValue(
        v=c_is_single_axis, formula=s_is_single_axis))

    # Collect axes before normalizing
    c_axes: list[int] = []
    s_axes: list[Formula] = []
    if c_is_single_axis:
      c_axis, s_axis = _split_concolic_int(axis)  # type: ignore
      c_axes.append(c_axis)
      s_axes.append(s_axis)
    else:
      # We got an axis tuple; basically a shape with lists disallowed so use shape validation
      axes_valid = _validate_shape_like(
        axis, require_nonnegative=False, allow_list=False)  # type: ignore
      if axes_valid.get_value():
        make_assertion(axes_valid)
      else:
        # Axes invalid; branch and fail
        record_path(axes_valid)
        raise TypeError(
          'axis must be None, an integer, or a tuple of integers')

      # Freeze the rank of the axis tuple
      num_axes_sv = _shape_like_rank(axis)  # type: ignore
      make_assertion(makeSymbolicValue(
        v=True, formula=num_axes_sv.get_formula() == smt.IntVal(num_axes_sv.get_value())))

      num_axes: int = num_axes_sv.get_value()
      for i in range(num_axes):
        c_axis, s_axis = _shape_like_get(axis, i)  # type: ignore
        c_axes.append(c_axis)
        s_axes.append(s_axis)

    if c_is_single_axis and c_rank == 0:
      # For scalar (0d) array input, numpy allows axis 0 or -1 only
      c_valid = c_axes[0] in (0, -1)
      s_valid = smt.And(s_rank == smt.IntVal(0),
                        smt.Or(s_axes[0] == smt.IntVal(0),
                               s_axes[0] == smt.IntVal(-1)))

      # Branch and fail if the provided axis is invalid
      record_path(makeSymbolicValue(v=c_valid, formula=s_valid))
      if not c_valid:
        raise ValueError('axis out of bounds for 0-d array')
      return ()

    # Normalize the axes
    axes: list[SymbolicValue] = []
    c_valid = True
    s_valid_conjuncts: list[Formula] = [smt.BoolVal(True)]
    for c_axis, s_axis in zip(c_axes, s_axes):
      # Validate bounds of this axis (with negative index normalization)
      c_valid &= (-c_rank <= c_axis < c_rank)
      s_valid_conjuncts += [-s_rank <= s_axis, s_axis < s_rank]

      # We don't check for duplicates in this shared helper; just normalize
      c_normalized = c_rank + c_axis if c_axis < 0 else c_axis
      s_normalized = smt.If(s_axis < smt.IntVal(0), s_rank + s_axis, s_axis)
      axes.append(makeSymbolicValue(v=c_normalized,
                  formula=smt.simplify(s_normalized)))

    # Branch on validity
    record_path(makeSymbolicValue(
      v=c_valid, formula=smt.And(*s_valid_conjuncts)))
    if not c_valid:
      raise ValueError('axis or axes out of bounds for array')

    return tuple(axes)

  @final
  def _resolve_reducelike_out_array(self,
                                    out: UFuncOutSlot,
                                    result_shape: ShapeLike,
                                    result_dtype: DType) -> ndarray | SymbolicValue:
    """
    Resolves the output array to write to for reduce-like methods.
    """
    # If no out provided, construct an array
    if out is None:
      # If the out= arg was an SV of none, it got normalized to concrete None
      return ndarray(result_shape, dtype=result_dtype)

    # Make sure we have a valid, writeable ndarray
    out._ensure_validity()
    out._ensure_writeable()

    result_rank = _shape_like_rank(result_shape)
    out_rank = out.ndim

    # Check out array shape against the result shape
    c_valid = out_rank.get_value() == result_rank.get_value()
    s_valid_conjuncts: list[Formula] = [
      out_rank.get_formula() == result_rank.get_formula()]

    # Mismatched ranks handled by the initial conjunct; we can just loop up to min here
    for i in range(min(out_rank.get_value(), result_rank.get_value())):
      c_out_dim, s_out_dim = _shape_like_get(out._shape, i)
      c_res_dim, s_res_dim = _shape_like_get(result_shape, i)

      # Dimensions must be exactly equal; result is not broadcast to the out array
      c_valid &= (c_out_dim == c_res_dim)
      s_valid_conjuncts.append(s_out_dim == s_res_dim)

    record_path(makeSymbolicValue(
      v=c_valid, formula=smt.And(*s_valid_conjuncts)))
    if not c_valid:
      raise ValueError('out array has incorrect shape for result')

    return out

  @final
  def _normalize_reduce_keepdims(self, arg: bool | int | SymbolicValue) -> bool:
    """
    Resolves possibly concolic `keepdims` flag for reduce.
    Numpy parses an int here so we allow int, bool or SV of int or bool.
    """
    if not isinstance(arg, SymbolicValue):
      if type(arg) not in (int, bool):
        raise TypeError('boolean/integer argument expected for keepdims')

      return bool(arg)

    c_arg = arg.get_value()
    s_arg = arg.get_formula()

    if util.is_any(s_arg):
      # If we have Any-typed formula, need to branch on type validity
      valid = makeSymbolicValue(v=type(c_arg) in (int, bool),
                                formula=smt.Or(util.is_int(s_arg), util.is_bool(s_arg)))
      record_path(valid)
      if not valid.get_value():
        raise TypeError('boolean/integer argument expected for keepdims')

      # We know it's an int if not bool
      s_value = smt.If(util.is_bool(s_arg),
                       util.get_bool(s_arg),
                       util.get_int(s_arg) != smt.IntVal(0))
    elif s_arg.sort() == smt.IntSort():
      # Use int truthiness
      s_value = (s_arg != smt.IntVal(0))
    elif s_arg.sort() == smt.BoolSort():
      # Use direct truth value
      s_value = s_arg
    else:
      # Unsupported type
      raise TypeError('boolean/integer argument expected for keepdims')

    # Branch on the actual keepdims value if it has a symbolic component
    value = makeSymbolicValue(v=bool(c_arg), formula=s_value)
    record_path(value)

    return value.get_value()

  @final
  def get_reduce_axis_flags(self,
                            axes: tuple[SymbolicValue, ...],
                            rank: SymbolicValue) -> tuple[bool, ...]:
    """
    Resolves the normalized axis tuple into a boolean flag per dimension
    indicating whether that dimension is to be reduced. Freezes the values
    of these flags atomically, concretizing the axes reduced.

    First validates that axes are unique.

    NumPy analog: prefix of umath/ufunc_object.c::PyUFunc_Reduce
    """
    c_rank = rank.get_value()

    # Check that the axes to reduce are unique
    c_unique = len({axis.get_value() for axis in axes}) == len(axes)
    s_unique = smt.Distinct(*(axis.get_formula()
                            for axis in axes)) if len(axes) > 1 else smt.BoolVal(True)
    unique = makeSymbolicValue(v=c_unique, formula=s_unique)
    record_path(unique)
    if not unique.get_value():
      raise ValueError('duplicate value in normalized `axis` tuple')

    # Build the flag tuple
    c_flags: list[bool] = []
    s_flags: list[Formula] = []
    for dim in range(c_rank):
      c_flags.append(any(axis.get_value() == dim for axis in axes))
      s_flags.append(smt.Or(smt.BoolVal(False), *
                     (axis.get_formula() == smt.IntVal(dim) for axis in axes)))

    # Freeze the values atomically
    s_flags_state = smt.And(smt.BoolVal(True),
                            *(s if c else smt.Not(s)
                              for c, s in zip(c_flags, s_flags)))
    record_path(makeSymbolicValue(v=True, formula=s_flags_state))

    return tuple(c_flags)

  @final
  def _resolve_reduce_initial(self,
                              initial: Scalar | SymbolicValue | None | Unset,
                              signature: UFuncSignature) -> SymbolicValue | None:
    """
    Resolves the `initial` argument to `reduce`, or None when the
    reduction should seed from the first input element.

    NumPy analog: bits of umath/reduction.c::PyUFunc_ReduceWrapper
    """
    acc_dtype = signature.inputs[0]

    if isinstance(initial, Unset):
      # No explicit initializer; use identity or None
      if self.identity is None:
        return None

      # If this ufunc has an identity, cast it to the accumulator type
      return _cast_scalar_unsafe(self.identity, acc_dtype)

    if initial is None:
      # If initial=None provided explicitly, reduction seeds from the first input element
      return None

    if isinstance(initial, SymbolicValue):
      c_initial = initial.get_value()
      s_initial = initial.get_formula()

      if util.is_any(s_initial):
        # Any-valued initial can be none
        c_is_none = c_initial is None
        s_is_none = util.is_none(s_initial)
        record_path(makeSymbolicValue(v=c_is_none, formula=s_is_none))
        if c_is_none:
          return None

        # Otherwise, initial can be any scalar
        c_valid = type(c_initial) in DTYPES_ALLOWED
        s_valid = smt.Or(util.is_int(s_initial),
                         util.is_float(s_initial),
                         util.is_bool(s_initial))
        record_path(makeSymbolicValue(v=c_valid, formula=s_valid))
        if not c_valid:
          raise TypeError('initial value must be a scalar')

      if type(c_initial) not in DTYPES_ALLOWED:
        # If not Any, we know the type concretely so there's no branching to do
        raise TypeError('initial value must be a scalar')

    elif type(initial) not in DTYPES_ALLOWED:
      # If fully concrete, just check the argument type directly
      raise TypeError('initial value must be a scalar')

    return _cast_scalar_unsafe(initial, acc_dtype)

  @final
  def _get_reduce_source_coords(self,
                                result_coords: tuple[int, ...],
                                reduced_coords: tuple[int, ...],
                                axis_flags: tuple[bool, ...],
                                keepdims: bool) -> tuple[int, ...]:
    """
    Maps a reduce output coordinate, along with its coordinates in the
    reduced axes, to a source coordinate in the input.
    """
    res: list[int] = []

    result_axis = 0
    reduced_axis = 0
    for is_reduced in axis_flags:
      if is_reduced:
        # Reduced axis gets coordinate from the reduction loop
        res.append(reduced_coords[reduced_axis])
        reduced_axis += 1

        # Consume an axis iff keepdims==True
        if keepdims:
          result_axis += 1
      else:
        # Non-reduced axis lines up with a result coordinate
        res.append(result_coords[result_axis])
        result_axis += 1

    return tuple(res)

  @final
  def _execute_reduce_loop(self,
                           operand: Operand,
                           out_array: ndarray | SymbolicValue,
                           axis_flags: tuple[bool, ...],
                           keepdims: bool,
                           initial_value: SymbolicValue | None,
                           signature: UFuncSignature) -> None:
    """
    Executes the actual reduce loop over concretized dimensions.
    """
    if operand.is_array:
      operand.value._ensure_validity()

    out_array._ensure_validity()
    out_array._ensure_writeable()

    # Freeze the operand dimensions
    c_operand_shape = _freeze_shape_dims(operand.shape)

    # Get the concrete result dimensions to loop over
    c_result_shape = tuple(1 if is_reduced else dim
                           for dim, is_reduced in zip(c_operand_shape, axis_flags)
                           if keepdims or not is_reduced)

    # Which dimensions are being reduced?
    c_reduced_dims = tuple(dim for dim, is_reduced in zip(c_operand_shape, axis_flags)
                           if is_reduced)

    if initial_value is None and any(dim == 0 for dim in c_reduced_dims):
      # If no initial value, we seed from the first reduced element
      # But if any dimension is zero, there is no element to seed from
      raise ValueError(
        f'reduction over ufunc "{self._name}" with no identity received zero-sized array')

    # Collect the writes in a batch
    writes: list[tuple[tuple[int, ...], SymbolicValue]] = []
    for result_coords in itertools.product(*map(range, c_result_shape)):
      accumulator: SymbolicValue
      if initial_value is None:
        # Map result coordinates to a source coordinate in the input array
        source_coords = self._get_reduce_source_coords(
          result_coords, (0,) * len(c_reduced_dims), axis_flags, keepdims)

        # Accumulator is seeded with this value
        accumulator = operand.read_unsafe(
          source_coords, dtype=signature.inputs[0])
      else:
        # If we have an initial value, use it instead
        accumulator = _cast_scalar_unsafe(
          initial_value, dtype=signature.inputs[0])

      # Loop over coordinates into the reduced dimensions
      for reduced_coords in itertools.product(*map(range, c_reduced_dims)):
        # If we seeded from the first value (coords all 0), skip folding it in
        if initial_value is None and all(dim == 0 for dim in reduced_coords):
          continue

        # LHS is the accumulator; RHS is the next array/scalar value
        source_coords = self._get_reduce_source_coords(
          result_coords, reduced_coords, axis_flags, keepdims)
        next_value = operand.read_unsafe(
          source_coords, dtype=signature.inputs[1])

        # Fold this value into the accumulator
        accumulator, = self._apply((accumulator, next_value), signature)

      # Batch a write of the accumulated value to this result coordinate
      writes.append((result_coords, accumulator))

    for result_coords, value in writes:
      out_array._write_scalar_unsafe(result_coords, value)

  @final
  def reduce(self,
             array: UFuncOperandArg,
             /,
             axis: AxisArg = 0,
             dtype: DType | InterceptType | None = None,
             out: UFuncOutArg = None,
             keepdims: bool | int | SymbolicValue = False,
             initial: Scalar | SymbolicValue | None | Unset = UNSET,
             where: bool = True) -> ndarray | SymbolicValue:
    """
    Reduces the input over some axes.

    NumPy analog: umath_ufunc_object.c::PyUFunc_GenericReduction
    (through the `UFUNC_REDUCE` branch)
    """
    # Reduce-like methods are defined on all ufuncs, but only valid for 2-in-1-out
    self._ensure_reducelike_compatible()

    if where is not True:
      raise NotImplementedError(
        f'`where` argument is not modeled for {self._name}.reduce')

    normalized_out, force_array_return = self._normalize_reducelike_out_arg(
      out)
    operand, = self._resolve_operands(array)

    # Freeze the operand shape
    _freeze_shape_dims(operand.shape)
    rank = _shape_like_rank(operand.shape)

    # Resolve the actual axes that get reduced
    axes = self._normalize_reducelike_axes(axis, rank)
    axis_flags = self.get_reduce_axis_flags(axes, rank)

    # Multi-axis reduction with non reorderable operation is not well-defined
    # (numpy rejects)
    if sum(axis_flags) > 1 and not self._reorderable:
      raise ValueError(f'at most one axis may be specified for reduction over '
                       f'non-reorderable ufunc "{self._name}"')

    # Resolve a concrete keepdims value
    keep_reduced_dims = self._normalize_reduce_keepdims(keepdims)

    # Resolve the signature we'll use for reduction
    signature = self._resolve_reducelike_signature(
      operand, normalized_out, dtype, enforce_uniform_args=False)
    initial_value = self._resolve_reduce_initial(initial, signature)

    # Compute the result shape
    result_shape: list[SymbolicValue] = []
    for axis, is_reduced in enumerate(axis_flags):
      if is_reduced:
        # If keepdims==True, reduced dimensions are replaced with 1
        if keep_reduced_dims:
          result_shape.append(factories.lift_value(1))
      else:
        c_dim, s_dim = _shape_like_get(operand.shape, axis)
        result_shape.append(makeSymbolicValue(v=c_dim, formula=s_dim))

    # Get the out array to write to
    out_array = self._resolve_reducelike_out_array(
      normalized_out, tuple(result_shape), signature.outputs[0])

    # Execute the reduction
    self._execute_reduce_loop(operand, out_array, axis_flags,
                              keep_reduced_dims, initial_value, signature)

    if normalized_out is None and len(result_shape) == 0 and not force_array_return:
      # If the result is scalar, out is None, and we're not forced to return arrays, scalarize the result
      return out_array._read_scalar_unsafe(())

    return out_array
