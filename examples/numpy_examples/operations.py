# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import numpy

from pyctest import pyctos_test
from symbex.runtime import pyctos_assert


@pyctos_test('numpy.ops')
def copyto_basic(x):
  """
  Tests copying between equal-shaped arrays
  """
  src = numpy.zeros((3,), dtype=int)
  dst = numpy.zeros((3,), dtype=int)
  src[0] = 3
  src[1] = 5
  src[2] = 7

  numpy.copyto(dst, src)

  pyctos_assert(dst[0] == 3)
  pyctos_assert(dst[1] == 5)
  pyctos_assert(dst[2] == 7)

  if dst[x] == 5:
    pass


@pyctos_test('numpy.ops', 'numpy.broadcasting')
def copyto_broadcast(x, y):
  """
  Tests copying with source broadcasting
  """
  src = numpy.zeros((1, 3), dtype=int)
  dst = numpy.zeros((2, 3), dtype=int)
  src[0, 1] = 5
  src[0, 2] = 7

  numpy.copyto(dst, src)

  pyctos_assert(dst[0, 1] == 5)
  pyctos_assert(dst[1, 1] == 5)
  pyctos_assert(dst[1, 2] == 7)

  if dst[x, y] == 7:
    pass


@pyctos_test('numpy.ops', 'numpy.slicing')
def copyto_overlapping_views(x):
  """
  Tests copying between overlapping views
  """
  arr = numpy.zeros((4,), dtype=int)
  arr[0] = 3
  arr[1] = 5
  arr[2] = 7
  arr[3] = 9

  numpy.copyto(arr[1:], arr[:-1], casting='unsafe')

  pyctos_assert(arr[0] == 3)
  pyctos_assert(arr[1] == 3)
  pyctos_assert(arr[2] == 5)
  pyctos_assert(arr[3] == 7)

  if arr[x] == 5:
    pass


@pyctos_test('numpy.ops', 'numpy.broadcasting')
def copyto_readonly_source(x):
  """
  Tests copying from a readonly broadcasted source
  """
  base = numpy.zeros((2, 1), dtype=int)
  dst = numpy.zeros((2, 3), dtype=int)
  base[0, 0] = 5
  base[1, 0] = 7

  src = numpy.broadcast_to(base, (2, 3))
  numpy.copyto(dst, src)

  if dst[x, 0] == 5:
    pass

  if dst[x, 2] == 7:
    pass


@pyctos_test('numpy.ops')
def copyto_same_kind_casting(x):
  """
  Tests same_kind casting in copyto
  """
  if x == 0:
    src = numpy.zeros((1,), dtype=int)
    dst = numpy.zeros((1,), dtype=float)
    src[0] = 7

    numpy.copyto(dst, src)
    pyctos_assert(dst[0] == 7.0)

  if x == 1:
    src = numpy.zeros((1,), dtype=float)
    dst = numpy.zeros((1,), dtype=int)
    numpy.copyto(dst, src)
