# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import itertools

from symbex.globals.globals import make_assertion
from symbex.libraries.impls.numpy.views import broadcast_to
from symbex.types.array import Array
from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue

from .util import *
from .array import ndarray

from symbex.smtlib import get_smt_lib
smt = get_smt_lib()


__all__ = [
    'copyto',
]


def copyto(dst: ndarray | SymbolicValue,
           src: ndarray | SymbolicValue,
           casting: Casting = 'same_kind',
           where: bool = True) -> None:
  """
  Copies from the src to the dst array, broadcasting where necessary.
  Currently only supports `where=True`.
  """
  # TODO: Should branch on is_ndarray, and allow scalar source
  dst._ensure_validity()
  src._ensure_validity()

  # Make sure we can write to the destination array
  dst._ensure_writeable()

  # We don't support masked writing
  assert where is True

  # Check if this cast is allowed
  if not _is_valid_cast(src.dtype, dst.dtype, casting):
    raise TypeError(f'invalid dtypes for "{casting}" cast in copyto')

  # Fix the symbolic rank and dims to their concrete values
  rank = dst.ndim
  c_dims = _freeze_shape_dims(dst._shape)

  # Try to broadcast src to dst
  src_broadcast = broadcast_to(src, dst._shape)

  # Validate the arrays once instead of in the loop
  Array.ensure_validity(src.storage)  # type: ignore
  Array.ensure_validity(dst.storage)  # type: ignore

  # Now collect all the reads in one batch so we don't overwrite while reading
  values: list[SymbolicValue] = []
  for coords in itertools.product(*map(range, c_dims)):
    src_index = _resolve_scalar_coordinates(
      src_broadcast._shape, src_broadcast.offset, src_broadcast.strides, coords)
    values.append(Array.get(src_broadcast.storage, src_index,  # type: ignore
                  skip_validation=True))

  # Write all the values at once
  dtype = dst.dtype
  for coords, value in zip(itertools.product(*map(range, c_dims)), values):
    dst_index = _resolve_scalar_coordinates(
      dst._shape, dst.offset, dst.strides, coords)
    Array.set(dst.storage, dst_index,  # type: ignore
              _cast_scalar_unsafe(value, dtype), skip_validation=True)
