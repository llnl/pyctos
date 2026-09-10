# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import numpy

from pyctest import pyctos_test
from symbex.runtime import pyctos_assert


@pyctos_test('numpy.scalars')
def zero_init(a, b, c, x, y, z):
  """
  Tests zero initialization of an array with numpy.zeros
  """
  if a == 2:
    zeros = numpy.zeros((a, b, c), dtype=float)
    if zeros.size > 200:
      pass

    if x is not None and y is not None and z is not None:
      pyctos_assert(zeros[x, y, z] == 0)


@pyctos_test('numpy.scalars')
def reject_invalid_index(x):
  """
  Tests that invalid indices are generated as inputs
  """
  arr = numpy.ndarray((2, 3, 4), dtype=int)

  arr[1, 2, x] = 3


@pyctos_test('numpy.scalars')
def reject_invalid_dim(x):
  """
  Tests that invalid dimensions are rejected in ndarray shape
  """
  if x < 0:
    pass

  if x == 3.14:
    pass

  arr = numpy.ndarray((2, 3, x), dtype=int)

  if arr.size == 12:
    pass


@pyctos_test('numpy.scalars')
def scalar_round_trip_int(x):
  """
  Tests a scalar write-read trip with integers
  """
  arr = numpy.ndarray((2, 3, 4), dtype=int)
  arr[1, 2, 3] = x

  if arr[1, 2, 3] == 7:
    pass


@pyctos_test('numpy.scalars')
def scalar_round_trip_float(x):
  """
  Tests a scalar write-read trip with floats
  """
  arr = numpy.ndarray((2, 3, 4), dtype=float)
  arr[1, 2, 3] = x

  if arr[1, 2, 3] == 3.14:
    pass


@pyctos_test('numpy.scalars')
def scalar_round_trip_bool(x):
  """
  Tests a scalar write-read trip with booleans
  """
  arr = numpy.ndarray((2, 3, 4), dtype=bool)
  arr[1, 2, 3] = x

  if arr[1, 2, 3]:
    pass


@pyctos_test('numpy.scalars')
def scalar_round_trip_symbolic_coords(coords):
  """
  Tests a scalar write-read trip with symbolic coordinates
  """
  arr = numpy.zeros((2, 3, 4), dtype=int)

  # Constrain coords to resolve to a scalar
  if isinstance(coords, tuple) and len(coords) == 3 \
          and coords[0] is not None and coords[1] is not None and coords[2] is not None:
    arr[coords] = 7

    pyctos_assert(arr[coords] == 7)

    if arr[0, 0, 0] == 7:
      pass


@pyctos_test('numpy.scalars')
def scalar_round_trip_both_symbolic(shape, coords):
  """
  Tests a scalar write-read trip with symbolic shape and coordinates
  """
  arr = numpy.ndarray(shape, dtype=int)

  if len(shape) == 3:
    pass

  if shape[0] == 2:
    pass

  if arr.size == 8:
    pass

  # Length 3 is arbitrary; need to be able to constrain coordinates not none
  if len(shape) == 3 and len(shape) == len(coords) \
          and coords[0] is not None and coords[1] is not None and coords[2] is not None:
    arr[coords] = 7
    pyctos_assert(arr[coords] == 7)


@pyctos_test('numpy.scalars')
def scalar_index_normalization(x, y):
  """
  Tests normalizing single-component index into a tuple
  """
  arr = numpy.zeros((3,), dtype=int)

  if isinstance(x, int) and isinstance(y, int):
    arr[1] = x
    arr[2] = y

    if arr[1] > arr[2]:
      pass


@pyctos_test('numpy.scalars')
def scalar_index_normalization_symbolic(x, y):
  """
  Tests normalizing symbolic single-component index into a tuple
  """
  arr = numpy.zeros((3,), dtype=int)

  arr[x] = 1
  arr[y] = 2

  if arr[0] > arr[1]:
    pass


@pyctos_test('numpy.scalars')
def scalar_overwrite(x):
  """
  Tests overwriting a scalar value in an array
  """
  arr = numpy.ndarray((2, 3, 4), dtype=int)

  if x == 9:
    pass

  arr[0, 0, 1] = x
  arr[0, 0, 1] = 9

  pyctos_assert(arr[0, 0, 1] == 9)


@pyctos_test('numpy.scalars')
def scalar_overwrite_symbolic(x, y):
  """
  Tests overwriting a scalar value at a symbolic index
  """
  arr = numpy.ndarray((5,), dtype=int)

  arr[(x,)] = 5
  arr[(y,)] = 7

  # None in indexing would be treated as newaxis
  if x is not None and y is not None:
    if x == y:
      pyctos_assert(arr[(x,)] == 7)
    else:
      pyctos_assert(arr[(x,)] == 5)
      pyctos_assert(arr[(y,)] == 7)


@pyctos_test('numpy.scalars')
def scalar_write_several(x, y):
  """
  Tests several writes to different concrete indices
  """
  arr = numpy.zeros((1, 2, 3), dtype=int)
  if isinstance(x, int) and isinstance(y, int):
    arr[0, 0, 0] = x
    arr[0, 0, 1] = y

    pyctos_assert(arr[0, 0, 0] == x and arr[0, 0, 1] == y)

    if arr[0, 0, 0] == arr[0, 0, 1]:
      pass

    pyctos_assert(arr[0, 1, 2] == 0)


@pyctos_test('numpy.scalars')
def coerce_to_int(x):
  """
  Tests coercion to integer on write
  """
  arr = numpy.ndarray((1, 2, 3), dtype=int)
  arr[0, 0, 0] = x

  if x == 3.14:
    pass

  if arr[0, 0, 0] == 3:
    pass


@pyctos_test('numpy.scalars')
def coerce_to_float(x):
  """
  Tests coercion to float on write
  """
  arr = numpy.ndarray((1, 2, 3), dtype=float)
  arr[0, 0, 0] = x

  if isinstance(x, float):
    pass

  if arr[0, 0, 0] == 3:
    pass


@pyctos_test('numpy.scalars')
def coerce_to_bool(x):
  """
  Tests coercion to boolean on write
  """
  arr = numpy.ndarray((1, 2, 3), dtype=bool)
  arr[0, 0, 0] = x

  if isinstance(x, bool):
    pass

  if arr[0, 0, 0]:
    pass


@pyctos_test('numpy.scalars', run_timeout=360_000, solver_timeout=36_000)
def synthesize_ndarray(arr, x, y, z):
  """
  Tests synthesizing an ndarray to read from a symbolic index
  """
  if isinstance(arr, numpy.ndarray):
    if arr.size == 8:
      pass

    if arr[x, y, z] == 2.5:
      pass


glob_arr = None


@pyctos_test('numpy.scalars', run_timeout=360_000, solver_timeout=36_000)
def synthesize_ndarray_global(x, y, z):
  """
  Tests synthesizing an ndarray in a global variable to read from a symbolic index
  """
  global glob_arr
  if isinstance(glob_arr, numpy.ndarray):
    if glob_arr.size == 8:
      pass

    if glob_arr[x, y, z] == 2.5:
      pass
