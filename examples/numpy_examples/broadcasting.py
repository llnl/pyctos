# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import numpy

from pyctest import pyctos_test
from symbex.runtime import pyctos_assert


@pyctos_test('numpy.views', 'numpy.broadcasting')
def broadcast_to_leading_dim(x, y):
  """
  Tests adding a leading dimension through broadcasting
  """
  arr = numpy.zeros((3,), dtype=int)
  arr[1] = y
  arr[2] = x

  broadcasted = numpy.broadcast_to(arr, (2, 3))

  if broadcasted[0, 2] == 7:
    pass

  if broadcasted[1, 1] == 5:
    pass


@pyctos_test('numpy.views', 'numpy.broadcasting')
def broadcast_to_size_one_dim(x, y):
  """
  Tests broadcasting a size-one dimension
  """
  arr = numpy.zeros((2, 1), dtype=int)
  arr[0, 0] = y
  arr[1, 0] = x

  broadcasted = numpy.broadcast_to(arr, (2, 3))

  if broadcasted[1, 0] == 7:
    pass

  if broadcasted[1, 2] == 7:
    pass

  if broadcasted[0, 2] == 5:
    pass


@pyctos_test('numpy.views', 'numpy.broadcasting')
def broadcast_to_scalar(x, y):
  """
  Tests broadcasting a 0-d array
  """
  arr = numpy.zeros((), dtype=int)
  arr[()] = 7

  broadcasted = numpy.broadcast_to(arr, (2, 3))

  if broadcasted[x, y] == 7:
    pass


@pyctos_test('numpy.views', 'numpy.broadcasting')
def broadcast_to_readonly(x):
  """
  Tests that broadcast_to returns a readonly view
  """
  arr = numpy.zeros((1,), dtype=int)
  broadcasted = numpy.broadcast_to(arr, (2,))

  broadcasted[0] = x
  pyctos_assert(False)  # should be unreachable


@pyctos_test('numpy.views', 'numpy.broadcasting')
def broadcast_to_invalid_shape(x, y):
  """
  Tests rejecting invalid broadcast shapes
  """
  arr = numpy.zeros((2,), dtype=int)
  arr[1] = y

  if x == 2:
    broadcasted = numpy.broadcast_to(arr, (x,))

    if broadcasted[1] == 7:
      pass

  if x == 3:
    numpy.broadcast_to(arr, (x,))
    pyctos_assert(False)  # should be unreachable

  if x == -1:
    numpy.broadcast_to(arr, (x,))
    pyctos_assert(False)  # should be unreachable


@pyctos_test('numpy.views', 'numpy.broadcasting')
def broadcast_to_symbolic(shape, x, y):
  """
  Tests broadcasting to a symbolic shape
  """
  if isinstance(shape, tuple) and len(shape) >= 2:
    arr = numpy.zeros((1, 3), dtype=int)
    arr[0, 1] = x
    arr[0, 2] = y

    broadcasted = numpy.broadcast_to(arr, shape)
    if len(shape) == 2:
      if broadcasted[0, 2] == 5:
        pass

    if len(shape) == 3:
      if broadcasted[0, 3, 1] == 7:
        pass


@pyctos_test('numpy.broadcasting')
def broadcast_shapes_basic(x, y):
  """
  Tests broadcasting several concrete shapes together
  """
  shape = numpy.broadcast_shapes((), (1, 3), (2, 1))

  if shape[0] == x:
    pass

  if shape[1] == y:
    pass


@pyctos_test('numpy.broadcasting')
def broadcast_shapes_single(x, y):
  """
  Tests broadcast_shapes with a single shape
  """
  shape = numpy.broadcast_shapes([x, y])

  if shape[0] == 4:
    pass

  if shape[1] == 5:
    pass


@pyctos_test('numpy.broadcasting')
def broadcast_shapes_zero_dim(x):
  """
  Tests broadcasting shapes with at least one zero dimension
  """
  shape = numpy.broadcast_shapes((1, 0), (x, 1))

  if shape[0] == 0 and shape[1] == 0:
    pass

  if shape[0] == 2 and shape[1] == 0:
    pass


@pyctos_test('numpy.broadcasting')
def broadcast_shapes_symbolic(shape, x, y, z):
  """
  Tests broadcast_shapes with mixed concrete and symbolic shape
  """
  if isinstance(shape, tuple) and len(shape) == 1:
    result = numpy.broadcast_shapes((1, 3), shape)

    if result[0] == x and result[1] == y:
      pass

  if isinstance(shape, tuple) and len(shape) == 3:
    result = numpy.broadcast_shapes((1, 3), shape)

    if result[0] == x and result[1] == y and result[2] == z:
      pass
