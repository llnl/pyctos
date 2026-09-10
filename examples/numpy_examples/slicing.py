# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import numpy
import math

from pyctest import pyctos_test
from symbex.runtime import pyctos_assert


@pyctos_test('numpy.views', 'numpy.slicing')
def slice_basic_read(x, y):
  """
  Tests reading from a basic slice
  """
  arr = numpy.zeros((4, 5), dtype=int)
  arr[1, 4] = 5
  arr[2, 3] = 7

  view = arr[1:3, 2:5]

  pyctos_assert(view[0, 2] == 5)
  pyctos_assert(view[1, 1] == 7)

  if x is not None and y is not None:
    if view[x, y] == 7:
      pass


@pyctos_test('numpy.views', 'numpy.slicing')
def slice_negative_step(x):
  """
  Tests slicing with a negative step
  """
  arr = numpy.zeros((5,), dtype=int)
  arr[0] = 3
  arr[2] = 7
  arr[4] = 9

  view = arr[::-2]

  pyctos_assert(view[0] == 9)
  pyctos_assert(view[1] == 7)
  pyctos_assert(view[2] == 3)

  if x == 1:
    pyctos_assert(view[x] == 7)


@pyctos_test('numpy.views', 'numpy.slicing')
def slice_symbolic_bounds(start, stop):
  """
  Tests slicing with symbolic bounds
  """
  arr = numpy.zeros((5,), dtype=int)
  arr[1] = 5
  arr[2] = 7
  arr[3] = 9

  if start == 1 and stop == 4:
    view = arr[start:stop]

    pyctos_assert(view[0] == 5)
    pyctos_assert(view[1] == 7)
    pyctos_assert(view[2] == 9)


@pyctos_test('numpy.views', 'numpy.slicing')
def slice_empty(x):
  """
  Tests an empty slice
  """
  arr = numpy.zeros((4,), dtype=int)

  view = arr[2:2]

  pyctos_assert(view.size == 0)
  pyctos_assert(view.shape[0] == 0)

  if x is not None:
    if view.size == x:
      pass


@pyctos_test('numpy.views', 'numpy.slicing')
def slice_newaxis_ellipsis(x, y, z):
  """
  Tests slicing with newaxis and ellipsis
  """
  arr = numpy.zeros((2, 3), dtype=int)
  arr[0, 1] = 5
  arr[1, 2] = 7

  view = arr[None, ..., 1:3]

  pyctos_assert(view[0, 0, 0] == 5)
  pyctos_assert(view[0, 1, 1] == 7)

  if x is not None and y is not None and z is not None:
    if view[x, y, z] == 7:
      pass


@pyctos_test('numpy.views', 'numpy.slicing')
def slice_mixed_ellipsis(x, y):
  """
  Tests slicing with ellipsis, indices and slices
  """
  arr = numpy.zeros((2, 3, 4), dtype=int)
  arr[1, 1, 2] = 5
  arr[1, 2, 3] = 7

  view = arr[1, ..., 2:]

  pyctos_assert(view[1, 0] == 5)
  pyctos_assert(view[2, 1] == 7)

  if x is not None and y is not None:
    if view[x, y] == 7:
      pass


@pyctos_test('numpy.views', 'numpy.slicing')
def slice_multiple_newaxis(x, y, z, w):
  """
  Tests slicing with multiple newaxis components
  """
  arr = numpy.zeros((2, 3), dtype=int)
  arr[0, 1] = 5
  arr[1, 2] = 7

  view = arr[numpy.newaxis, :, None, 1:]

  pyctos_assert(view[0, 0, 0, 0] == 5)
  pyctos_assert(view[0, 1, 0, 1] == 7)

  if x is not None and y is not None and z is not None and w is not None:
    if view[x, y, z, w] == 7:
      pass


@pyctos_test('numpy.views', 'numpy.slicing')
def slice_zero_dim(x):
  """
  Tests slicing a 0-d array
  """
  arr = numpy.zeros((), dtype=int)
  arr[()] = 7

  view = arr[...]

  pyctos_assert(arr[()] == 7)
  pyctos_assert(view[()] == 7)

  if x is not None:
    if view[()] == x:
      pass


@pyctos_test('numpy.slicing')
def setitem_zero_dim(x):
  """
  Tests assigning through a 0-d slice
  """
  arr = numpy.zeros((), dtype=int)

  arr[...] = 7

  pyctos_assert(arr[()] == 7)

  if arr[()] == x:
    pass


@pyctos_test('numpy.slicing')
def setitem_scalar_view(x, y):
  """
  Tests scalar assignment into a sliced view
  """
  arr = numpy.zeros((2, 3), dtype=int)

  arr[:, 1:] = 5

  pyctos_assert(arr[0, 0] == 0)
  pyctos_assert(arr[0, 1] == 5)
  pyctos_assert(arr[1, 2] == 5)

  if arr[x, y] == 5:
    pass


@pyctos_test('numpy.slicing')
def setitem_symbolic_scalar_view(x, y, value):
  """
  Tests symbolic scalar assignment into a sliced view
  """
  arr = numpy.zeros((2, 3), dtype=int)

  arr[:, 1:] = value

  pyctos_assert(arr[0, 0] == 0)

  if arr[x, y] == 7:
    pass


@pyctos_test('numpy.slicing')
def setitem_array_view(x, y):
  """
  Tests array assignment into a sliced view
  """
  src = numpy.zeros((2, 2), dtype=int)
  dst = numpy.zeros((2, 3), dtype=int)
  src[0, 0] = 3
  src[0, 1] = 5
  src[1, 0] = 7
  src[1, 1] = 9

  dst[:, 1:] = src

  pyctos_assert(dst[0, 0] == 0)
  pyctos_assert(dst[0, 1] == 3)
  pyctos_assert(dst[1, 1] == 7)
  pyctos_assert(dst[1, 2] == 9)

  if dst[x, y] == 7:
    pass


@pyctos_test('numpy.slicing', 'numpy.broadcasting')
def setitem_broadcast_array(x, y):
  """
  Tests broadcasted array assignment to a slice
  """
  src = numpy.zeros((1, 3), dtype=int)
  dst = numpy.zeros((2, 3), dtype=int)
  src[0, 1] = 5
  src[0, 2] = 7

  dst[...] = src

  pyctos_assert(dst[0, 1] == 5)
  pyctos_assert(dst[1, 1] == 5)
  pyctos_assert(dst[1, 2] == 7)

  if dst[x, y] == 7:
    pass


@pyctos_test('numpy.slicing')
def setitem_overlapping_views(x):
  """
  Tests assignment between overlapping views
  """
  arr = numpy.zeros((4,), dtype=int)
  arr[0] = 3
  arr[1] = 5
  arr[2] = 7
  arr[3] = 9

  arr[1:] = arr[:-1]

  pyctos_assert(arr[0] == 3)
  pyctos_assert(arr[1] == 3)
  pyctos_assert(arr[2] == 5)
  pyctos_assert(arr[3] == 7)

  if arr[x] == 5:
    pass


@pyctos_test('numpy.slicing', run_timeout=180_000, solver_timeout=20000)
def setitem_synthesized_src(src, x, y):
  """
  Tests assignment from a synthesized source array
  """
  dst = numpy.zeros((2, 3), dtype=float)

  if isinstance(src, numpy.ndarray):
    if src.ndim == 2:
      if src.shape[0] == 1:
        if src.shape[1] == 3:
          dst[...] = src

          if dst[x, y] == 7:
            pass
