# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

# type: ignore
from symbex.libraries.impls import numpy as impl
from symbex.types.array import Array
from symbex.types.symbolicvalue import SymbolicValue
from typing import Any

# Separate import for newaxis since global assignment would just be dropped
from symbex.libraries.impls.numpy import newaxis

# Reexport our dtype normalization as np.dtype() (equivalent for the reduced type set)
from symbex.libraries.impls.numpy.util import _normalize_dtype as dtype

# Reexport ufunc instances
from symbex.libraries.impls.numpy.ufuncs import *


class ndarray(impl.ndarray):
  # For now, dtype is assumed to be equal to the backing ArrayStorage dtype (how do we want to handle reinterpretation?)
  storage: 'Array[Any]'
  _shape: 'ShapeLike'
  offset: 'int | SymbolicValue'
  strides: 'ShapeLike'

  # For now, writeable is used only internally but required for synthesis
  _writeable: 'bool'

  # Constructor for ndarray
  def __init__(self, *args, **kwargs):
    impl.ndarray.__init__(self, *args, **kwargs)
    self.storage
    self._shape
    self.offset
    self.strides

    self._writeable

  def __prepare_replay_arg__(self):
    return impl.ndarray.__prepare_replay_arg__(self)

  def _ensure_validity(self) -> None:
    impl.ndarray._ensure_validity(self)

  def view(*args, **kwargs):
    return impl.ndarray.view(*args, **kwargs)

  @property
  def shape(self):
    return impl.ndarray.shape_tuple.fget(self)

  @property
  def dtype(self):
    return impl.ndarray.dtype.fget(self)

  @property
  def size(self):
    return impl.ndarray.size.fget(self)

  @property
  def ndim(self):
    return impl.ndarray.ndim.fget(self)

  # Indexing with array[i, j, k, ...]
  def __getitem__(*args, **kwargs):
    return impl.ndarray.__getitem__(*args, **kwargs)

  # Indexing with array[i, j, k, ...] = item
  def __setitem__(*args, **kwargs):
    impl.ndarray.__setitem__(*args, **kwargs)

  def transpose(*args, **kwargs):
    return impl.ndarray.transpose(*args, **kwargs)

  @property
  def T(self):
    return impl.ndarray.T.fget(self)

  def swapaxes(*args, **kwargs):
    return impl.ndarray.swapaxes(*args, **kwargs)


def ndim(*args, **kwargs):
  return impl.ndim(*args, **kwargs)


# Zeros function
def zeros(*args, **kwargs):
  return impl.zeros(ndarray, *args, **kwargs)


def swapaxes(*args, **kwargs):
  return impl.swapaxes(*args, **kwargs)


def transpose(*args, **kwargs):
  return impl.transpose(*args, **kwargs)


def permute_dims(*args, **kwargs):
  return impl.permute_dims(*args, **kwargs)


def expand_dims(*args, **kwargs):
  return impl.expand_dims(*args, **kwargs)


def broadcast_to(*args, **kwargs):
  return impl.broadcast_to(*args, **kwargs)


def broadcast_shapes(*args, **kwargs):
  return impl.broadcast_shapes(*args, **kwargs)


def copyto(*args, **kwargs):
  return impl.copyto(*args, **kwargs)
