# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import numpy

from pyctest import pyctos_test


@pyctos_test('numpy.views')
def view_read_scalar(x, y):
  """
  Tests reading a scalar value from a view of an array
  """
  arr = numpy.ndarray((2, 3, 4), dtype=float)

  arr[1, 2, 3] = x

  view = arr.view()

  arr[0, 0, 0] = y

  if view[1, 2, 3] == 3.0:
    pass

  if view[0, 0, 0] == 4.0:
    pass


@pyctos_test('numpy.views')
def view_write_scalar(x, y):
  """
  Tests writing a scalar value into a view of an array
  """
  arr = numpy.ndarray((2, 3, 4), dtype=float)

  arr[1, 2, 3] = x

  view = arr.view()

  view[0, 0, 0] = y

  if view[1, 2, 3] == 3.0:
    pass

  if arr[0, 0, 0] == 4.0:
    pass


@pyctos_test('numpy.views')
def transpose_shape_check(a, b, c):
  """
  Tests zero-argument transpose
  """
  arr = numpy.ndarray((a, b, c), dtype=int)
  arr_T = arr.transpose()

  if arr.shape[0] == 1 and arr.shape[1] == 2 and arr.shape[2] == 3:
    assert arr_T.shape[0] == 3 and arr_T.shape[1] == 2 and arr_T.shape[2] == 1


@pyctos_test('numpy.views')
def transpose_read_scalar(x, y):
  """
  Tests reading a scalar from a transposed view
  """
  arr = numpy.zeros((2, 3), dtype=int)
  arr[1, 2] = 7

  arr_T = arr.T
  if x == 2 and y == 1:
    assert arr_T[x, y] == 7


@pyctos_test('numpy.views')
def transpose_write_scalar(x, y):
  """
  Tests writing a scalar into a transposed view
  """
  arr = numpy.zeros((2, 3), dtype=int)

  arr_T = arr.T
  arr_T[2, 1] = 9

  if x == 1 and y == 2:
    assert arr[x, y] == 9


@pyctos_test('numpy.views')
def transpose_n_times(n):
  """
  Tests idempotence (if n is even) of repeatedly transposing an array
  """
  arr = numpy.zeros((2, 3), dtype=int)
  arr[0, 1] = 3

  for i in range(n):
    arr = arr.transpose()

  if n > 2:
    pass

  # We don't get a witness for (n>2 and n even) because current loop modeling obscures
  # the link between parity of transpose count and equality here :(
  if arr[1, 0] == 3:
    pass


@pyctos_test('numpy.views')
def transpose_permute(a, b, c):
  """
  Tests transposing with a permutation of symbolic indices
  """
  arr = numpy.zeros((4, 4, 4), dtype=int)
  arr[1, 2, 3] = 5

  arr_T = arr.transpose((a, b, c))

  if arr_T[2, 3, 1] == 5:
    pass


@pyctos_test('numpy.views')
def transpose_symmetric(a00, a01, a02, a10, a11, a12, a20, a21, a22):
  """
  Tests generating values that form a symmetric matrix
  """
  arr = numpy.ndarray((3, 3), dtype=int)

  # constrain all nine values to be integers so the solver doesn't generate a bunch of ndarrays...
  if isinstance(a00, int) and isinstance(a01, int) and isinstance(a02, int) \
          and isinstance(a10, int) and isinstance(a11, int) and isinstance(a12, int) \
          and isinstance(a20, int) and isinstance(a21, int) and isinstance(a22, int):
    arr[0, 0], arr[0, 1], arr[0, 2] = a00, a01, a02
    arr[1, 0], arr[1, 1], arr[1, 2] = a10, a11, a12
    arr[2, 0], arr[2, 1], arr[2, 2] = a20, a21, a22

    arr_T = arr.transpose()

    num_equal = 0
    for i in range(3):
      for j in range(3):
        if arr[i, j] == arr_T[i, j]:
          num_equal += 1

    if num_equal == 9:
      pass


@pyctos_test('numpy.views')
def expand_dim_0(x, y):
  """
  Tests inserting a dimension before existing ones
  """
  arr = numpy.zeros((2, 3), dtype=int)
  arr[1, 2] = 7

  exp = numpy.expand_dims(arr, 0)
  if exp[x, y, 2] == 7:
    pass


@pyctos_test('numpy.views')
def expand_dim_n(x, y):
  """
  Tests inserting a dimension after existing ones
  """
  arr = numpy.zeros((2, 3), dtype=int)
  arr[1, 2] = 7

  exp = numpy.expand_dims(arr, 2)
  if exp[1, x, y] == 7:
    pass


@pyctos_test('numpy.views')
def expand_dims_interleave(x, y, z):
  """
  Tests interleaving new dimensions with existing ones
  """
  arr = numpy.zeros((2, 3, 4), dtype=int)
  arr[1, 2, 3] = 7

  exp = numpy.expand_dims(arr, (1, 3, 5))
  if exp[x, 0, y, 0, z, 0] == 7:
    pass


@pyctos_test('numpy.views')
def expand_dims_empty_tuple(x, y):
  """
  Tests no-op expand_dims with an empty tuple
  """
  arr = numpy.zeros((2, 3), dtype=int)
  arr[1, 2] = 7

  exp = numpy.expand_dims(arr, ())

  if exp[1, 2] == x:
    pass

  exp[0, 0] = 5
  if arr[0, 0] == y:
    pass


@pyctos_test('numpy.views')
def expand_dims_symbolic(a, b, c):
  """
  Tests inserting dimensions at symbolic positions
  """
  arr = numpy.zeros((2, 3, 4), dtype=int)
  arr[1, 2, 0] = 7

  # Check that normalized indexing works
  if a < 0 or b < 0 or c < 0:
    pass

  exp = numpy.expand_dims(arr, (a, b, c))
  if exp[0, 1, 0, 0, 2, 0] == 7:
    pass


@pyctos_test('numpy.views')
def expand_dims_then_transpose(a, b, c, perm):
  """
  Tests transposing a view with inserted dimensions
  """
  if isinstance(perm, tuple) and len(perm) == 6:
    arr = numpy.zeros((2, 3, 4), dtype=int)
    arr[1, 2, 0] = 7

    exp = numpy.expand_dims(arr, (a, b, c))
    permuted = exp.transpose(perm)

    if permuted[0, 2, 0, 0, 1, 0] == 7:
      pass


@pyctos_test('numpy.views')
def transpose_then_expand_dims(a, b, c, perm):
  """
  Tests inserting dimensions into a transposed view
  """
  if isinstance(perm, tuple) and len(perm) == 3:
    arr = numpy.zeros((2, 3, 4), dtype=int)
    arr[1, 2, 0] = 7

    permuted = arr.transpose(perm)
    exp = numpy.expand_dims(permuted, (a, b, c))

    if exp[0, 2, 0, 0, 1, 0] == 7:
      pass


@pyctos_test('numpy.views')
def swapaxes_read_scalar(x, y):
  """
  Tests reading a scalar from a view with swapped axes
  """
  arr = numpy.zeros((2, 3, 4), dtype=int)
  arr[1, 2, 3] = x
  arr[0, 0, 0] = y

  swapped = arr.swapaxes(0, 2)

  if x > 0:
    pass

  if swapped[3, 2, 1] == y:
    pass

  if swapped[0, 0, 0] == x:
    pass


@pyctos_test('numpy.views')
def swapaxes_write_scalar(x, y):
  """
  Tests writing a scalar into a view with swapped axes
  """
  arr = numpy.zeros((2, 3, 4), dtype=int)

  swapped = arr.swapaxes(0, 2)
  swapped[3, 2, 1] = x
  swapped[0, 0, 0] = y

  if x > 0:
    pass

  if arr[1, 2, 3] == y:
    pass

  if arr[0, 0, 0] == x:
    pass


@pyctos_test('numpy.views')
def swapaxes_negative_axes(x, y):
  """
  Tests swapaxes with negative axis indices
  """
  arr = numpy.zeros((2, 3, 4), dtype=int)
  arr[1, 2, 3] = x
  arr[0, 0, 0] = y

  swapped = arr.swapaxes(-3, -1)

  if swapped[3, 2, 1] == y:
    pass

  if swapped[0, 0, 0] == x:
    pass


@pyctos_test('numpy.views')
def swapaxes_noop(x, y):
  """
  Tests noop swapaxes with equal indices
  """
  arr = numpy.zeros((2, 3, 4), dtype=int)
  arr[1, 2, 3] = x
  arr[0, 0, 0] = y

  swapped = arr.swapaxes(1, 1)

  if swapped[1, 2, 3] == y:
    pass

  if swapped[0, 0, 0] == x:
    pass


@pyctos_test('numpy.views')
def swapaxes_symbolic(i, j, x):
  """
  Tests swapping axes at symbolic indices
  """
  arr = numpy.zeros((2, 4, 4), dtype=int)
  arr[1, 2, 3] = 5
  arr[0, 0, 0] = x

  swapped = arr.swapaxes(i, j)

  if swapped[1, 3, 2] == 5:
    pass

  if swapped[0, 0, 0] == 7:
    pass
