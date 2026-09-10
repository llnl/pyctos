# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import numpy
import math

from pyctest import pyctos_test
from symbex.runtime import pyctos_assert, pyctos_prove


def equals(x: float, y: float):
  return x == y or (math.isnan(x) and math.isnan(y))


@pyctos_test('numpy.ufuncs')
def scalar_add(x, y):
  """
  Tests scalar addition
  """
  result = numpy.add(x, y, dtype=float)

  pyctos_prove(equals(result, x + y))

  if not math.isnan(result):
    if result < x:
      pyctos_prove(y < 0)
    else:
      pyctos_prove(y >= 0)


@pyctos_test('numpy.ufuncs')
def scalar_subtract(x, y):
  """
  Tests scalar subtraction
  """
  result = numpy.subtract(x, y, dtype=float)

  pyctos_prove(equals(result, x - y))

  if not math.isnan(result):
    if result < 0:
      pyctos_prove(x < y)
    else:
      pyctos_prove(x >= y)


@pyctos_test('numpy.ufuncs')
def scalar_multiply(x):
  """
  Tests scalar multiplication
  """
  result = numpy.multiply(x, 2, dtype=float)

  if not isinstance(x, float) or math.isfinite(x):
    pyctos_prove(equals(result, x * 2))

  if not math.isnan(result):
    if result < 0:
      pyctos_prove(x < 0)
    else:
      pyctos_prove(x >= 0)


@pyctos_test('numpy.ufuncs')
def scalar_negative(x):
  """
  Tests scalar negation
  """
  result = numpy.negative(x, dtype=float)

  pyctos_prove(equals(result, x * -1))

  if not math.isnan(x):
    if result < 0:
      pyctos_prove(x > 0)
    else:
      pyctos_prove(x <= 0)


@pyctos_test('numpy.ufuncs')
def scalar_positive(x):
  """
  Tests scalar unary positive
  """
  result = numpy.positive(x, dtype=float)

  if not isinstance(x, float) or math.isfinite(x):
    pyctos_prove(equals(result, float(x)))

  if not math.isnan(x):
    if result < 0:
      pyctos_prove(x < 0)
    else:
      pyctos_prove(x >= 0)


@pyctos_test('numpy.ufuncs')
def scalar_equal(x, y):
  """
  Tests scalar equality
  """
  result = numpy.equal(x, y, signature=(float, float, bool))

  pyctos_prove(equals(result, (float(x) == float(y))))


@pyctos_test('numpy.ufuncs')
def scalar_not_equal(x, y):
  """
  Tests scalar inequality
  """
  result = numpy.not_equal(x, y, signature=(float, float, bool))

  pyctos_prove(equals(result, (float(x) != float(y))))


@pyctos_test('numpy.ufuncs')
def scalar_less(x, y):
  """
  Tests scalar less-than comparison
  """
  result = numpy.less(x, y, signature=(float, float, bool))

  pyctos_prove(equals(result, (float(x) < float(y))))


@pyctos_test('numpy.ufuncs')
def scalar_less_equal(x, y):
  """
  Tests scalar less-than-or-equal comparison
  """
  result = numpy.less_equal(x, y, signature=(float, float, bool))

  pyctos_prove(equals(result, (float(x) <= float(y))))


@pyctos_test('numpy.ufuncs')
def scalar_greater(x, y):
  """
  Tests scalar greater-than comparison
  """
  result = numpy.greater(x, y, signature=(float, float, bool))

  pyctos_prove(equals(result, (float(x) > float(y))))


@pyctos_test('numpy.ufuncs')
def scalar_greater_equal(x, y):
  """
  Tests scalar greater-than-or-equal comparison
  """
  result = numpy.greater_equal(x, y, signature=(float, float, bool))

  pyctos_prove(equals(result, (float(x) >= float(y))))


@pyctos_test('numpy.ufuncs')
def ufunc_zero_dim(x, y):
  """
  Tests 0d result being returned as a scalar
  """
  lhs = numpy.zeros((), dtype=int)
  rhs = numpy.zeros((), dtype=int)

  if isinstance(x, int) and isinstance(y, int):
    lhs[()] = x
    rhs[()] = y

    result = numpy.add(lhs, rhs)

    pyctos_prove(equals(result, x + y))

    if result == 11:
      pass


@pyctos_test('numpy.ufuncs')
def ufunc_zero_dim_forced_array(x, y):
  """
  Tests out=... forcing 0d result returned as array
  """
  lhs = numpy.zeros((), dtype=int)
  rhs = numpy.zeros((), dtype=int)

  if isinstance(x, int) and isinstance(y, int):
    lhs[()] = x
    rhs[()] = y

    result = numpy.add(lhs, rhs, out=...)

    pyctos_assert(result.shape == ())
    pyctos_prove(result[()] == x + y)

    if result[()] == 11:
      pass


@pyctos_test('numpy.ufuncs')
def ufunc_array_out(x):
  """
  Tests writing + returning an array in out=
  """
  lhs = numpy.zeros((2,), dtype=int)
  rhs = numpy.zeros((2,), dtype=int)
  out = numpy.zeros((2,), dtype=int)
  lhs[0] = 3
  lhs[1] = x
  rhs[0] = 7
  rhs[1] = 11

  result = numpy.add(lhs, rhs, out=out)

  pyctos_prove(result[0] == 10)
  result[0] = 23
  pyctos_prove(out[0] == 23)

  if out[1] == 16:
    pass


@pyctos_test('numpy.ufuncs')
def ufunc_rejects_bad_out(x):
  """
  Tests validation of out= array shape against result shape
  """
  lhs = numpy.zeros((2, 1), dtype=int)
  rhs = numpy.zeros((3,), dtype=int)
  out = numpy.zeros((2, 2), dtype=int)
  lhs[0, 0] = x

  numpy.add(lhs, rhs, out=out)
  pyctos_assert(False)  # should be unreachable


@pyctos_test('numpy.ufuncs', 'numpy.broadcasting')
def ufunc_broadcast_arrays(x):
  """
  Tests binary array operation broadcasting
  """
  lhs = numpy.zeros((2, 1), dtype=int)
  rhs = numpy.zeros((3,), dtype=int)
  lhs[0, 0] = 3
  lhs[1, 0] = x
  rhs[0] = 7
  rhs[1] = 5
  rhs[2] = 13

  result = numpy.add(lhs, rhs)

  pyctos_prove(result.ndim == 2)
  pyctos_prove(result.shape[0] == 2 and result.shape[1] == 3)


@pyctos_test('numpy.ufuncs', 'numpy.broadcasting')
def ufunc_broadcast_out(x):
  """
  Tests out= contributing to the broadcast shape
  """
  lhs = numpy.zeros((3,), dtype=int)
  rhs = numpy.zeros((3,), dtype=int)
  out = numpy.zeros((2, 3), dtype=int)
  lhs[0] = x
  rhs[0] = 7
  x_int = lhs[0]

  result = numpy.add(lhs, rhs, out=out)

  pyctos_assert(result.shape == (2, 3))
  pyctos_prove(result[0, 0] == x_int + 7)
  pyctos_prove(result[1, 0] == result[0, 0])


@pyctos_test('numpy.ufuncs', 'numpy.broadcasting')
def ufunc_broadcast_out_validation(rows):
  """
  Tests out= shape validation against the broadcast result
  """
  lhs = numpy.zeros((2, 3), dtype=int)
  rhs = numpy.zeros((2, 3), dtype=int)
  out = numpy.zeros((rows, 3), dtype=int)
  lhs[0, 0] = 3
  rhs[0, 0] = 7

  result = numpy.add(lhs, rhs, out=out)

  pyctos_prove(rows == 2)  # rows != 2 would fail out shape validation
  pyctos_assert(result.shape == (2, 3))
  pyctos_prove(result[0, 0] == 10)


@pyctos_test('numpy.ufuncs', 'numpy.broadcasting')
def ufunc_broadcast_mixed(value, row, col):
  """
  Tests broadcasting mixed array/scalar operands
  """
  arr = numpy.zeros((2, 2), dtype=int)
  arr[0, 0] = 3
  arr[0, 1] = value
  arr[1, 0] = 7
  arr[1, 1] = 9

  result_left = numpy.add(arr, 4)
  result_right = numpy.add(4, arr)

  pyctos_prove(result_left.shape[0] == 2)
  pyctos_prove(result_left.shape[1] == 2)
  pyctos_prove(result_left[0, 0] == 7)
  pyctos_prove(result_left[0, 1] == result_right[0, 1])

  if row is not None and col is not None:
    if result_left[row, col] == 13:
      pass


@pyctos_test('numpy.ufuncs', 'numpy.slicing')
def ufunc_overlap_out(x, y):
  """
  Tests ufunc output memory overlapping the input (writes should be buffered)
  """
  arr = numpy.zeros((4,), dtype=int)
  arr[0] = x
  arr[1] = y
  arr[2] = 7
  arr[3] = 9
  x_int = arr[0]
  y_int = arr[1]

  numpy.add(arr[:-1], arr[1:], out=arr[1:])

  pyctos_prove(arr[0] == x_int)
  pyctos_prove(arr[1] == x_int + y_int)
  pyctos_prove(arr[2] == y_int + 7)
  pyctos_prove(arr[3] == 16)

  if arr[1] < x_int:
    pyctos_prove(y_int < 0)
  else:
    pyctos_prove(y_int >= 0)


@pyctos_test('numpy.ufuncs')
def ufunc_specified_dtypes(x):
  """
  Tests resolved output type with signature= and dtype= specified
  """
  lhs = numpy.zeros((2,), dtype=int)
  rhs = numpy.zeros((2,), dtype=int)
  lhs[0] = x
  lhs[1] = 5
  rhs[0] = 7
  rhs[1] = 11

  dtype_result = numpy.add(lhs, rhs, dtype=float)
  signature_result = numpy.add(lhs, rhs, signature=(None, None, float))

  pyctos_assert(dtype_result.dtype is numpy.dtype(float))
  pyctos_assert(signature_result.dtype is numpy.dtype(float))
  pyctos_prove(signature_result[1] == 16.0)

  if dtype_result[0] == 12.0:
    pass


@pyctos_test('numpy.ufuncs')
def ufunc_reject_output_cast(value):
  """
  Tests default output cast validation
  """
  lhs = numpy.zeros((2,), dtype=float)
  rhs = numpy.zeros((2,), dtype=float)
  out = numpy.zeros((2,), dtype=int)
  lhs[0] = value
  lhs[1] = 2.5
  rhs[0] = 2.75
  rhs[1] = 3.5

  numpy.add(lhs, rhs, out=out)
  pyctos_assert(False)  # should be unreachable


@pyctos_test('numpy.ufuncs')
def ufunc_unsafe_output_cast(value):
  """
  Tests unsafe output casting
  """
  lhs = numpy.zeros((2,), dtype=float)
  rhs = numpy.zeros((2,), dtype=float)
  out = numpy.zeros((2,), dtype=int)
  lhs[0] = value
  lhs[1] = 2.5
  rhs[0] = 2.75
  rhs[1] = 3.5

  result = numpy.add(lhs, rhs, out=out, casting='unsafe')

  pyctos_assert(result.dtype is numpy.dtype(int))
  pyctos_prove(result[1] == 6)

  if result[0] == 4:
    pass


@pyctos_test('numpy.ufuncs', run_timeout=180_000, solver_timeout=20_000)
def ufunc_synthesized_input(lhs):
  """
  Tests synthesized ndarray operand
  """
  if isinstance(lhs, numpy.ndarray):
    if lhs.ndim == 2 and lhs.shape[0] == 2 and lhs.shape[1] == 2:
      rhs = numpy.zeros((2, 2), dtype=lhs.dtype)
      result = numpy.add(lhs, rhs)

      pyctos_assert(result.shape[0] == 2)
      pyctos_assert(result.shape[1] == 2)
      pyctos_prove(equals(result[0, 0], lhs[0, 0]))


@pyctos_test('numpy.ufuncs', run_timeout=180_000, solver_timeout=20_000)
def ufunc_synthesized_out(out):
  """
  Tests synthesized arrays in and symbolic None for out=
  """
  if out is None:
    # Test a synthesized (symbolic) None argument for out
    result = numpy.add(3, 7, out=out)
    pyctos_prove(result == 10)
  elif isinstance(out, numpy.ndarray):
    if out.ndim == 1 and out.shape[0] == 2:
      lhs = numpy.zeros((2,), dtype=out.dtype)
      rhs = numpy.zeros((2,), dtype=out.dtype)
      lhs[0] = 3
      lhs[1] = 5
      rhs[0] = 7
      rhs[1] = 9

      result = numpy.add(lhs, rhs, out=out)

      pyctos_prove(result[0] == out[0])
      result[0] = 23
      pyctos_prove(out[0] == 23)


@pyctos_test('numpy.ufuncs')
def reduce_single_axis(idx, x):
  """
  Tests single-axis reduce producing indexed array output
  """
  arr = numpy.zeros((2, 3), dtype=int)
  arr[0, 0] = x
  arr[0, 1] = 24
  arr[1, 0] = 11

  result = numpy.add.reduce(arr, axis=0)

  pyctos_assert(result.shape == (3,))
  pyctos_prove(result[0] == arr[0, 0] + 11)
  pyctos_prove(result[1] == 24)

  if result[idx] == 24:
    pass


@pyctos_test('numpy.ufuncs')
def reduce_equal_bool(x):
  """
  Tests Boolean equality reduction
  """
  arr = numpy.zeros((3,), dtype=bool)
  arr[0] = x == 0
  arr[1] = True
  arr[2] = False
  first = arr[0]

  result = numpy.equal.reduce(arr)

  pyctos_prove(result != first)


@pyctos_test('numpy.ufuncs')
def reduce_subtract_symbolic_axis(idx, axis, x):
  """
  Tests non-reorderable reduce with symbolic axis selection
  """
  arr = numpy.zeros((2, 3), dtype=int)
  arr[0, 0] = x
  arr[0, 1] = 5
  arr[1, 0] = 11

  result = numpy.subtract.reduce(arr, axis=axis)

  if result.ndim == 1:
    if result.shape[0] == 2:
      pyctos_prove(result[0] == arr[0, 0] - 5)
      pyctos_prove(result[1] == 11)

      if result[idx] == 11:
        pass

    else:
      pyctos_assert(result.shape[0] == 3)
      pyctos_prove(result[0] == arr[0, 0] - 11)
      pyctos_prove(result[1] == 5)

      if result[idx] == 5:
        pass

  else:
    pyctos_assert(result.ndim == 2)
    pyctos_assert(result.shape[0] == 2)
    pyctos_assert(result.shape[1] == 3)
    pyctos_prove(result[0, 0] == arr[0, 0])
    pyctos_prove(result[0, 1] == 5)
    pyctos_prove(result[1, 0] == 11)


@pyctos_test('numpy.ufuncs')
def reduce_initial_value(x):
  """
  Tests explicit initial value seeding a non-reorderable fold
  """
  arr = numpy.zeros((1, 2), dtype=int)
  arr[0, 0] = 7
  arr[0, 1] = 11

  seeded = numpy.subtract.reduce(arr, axis=1, initial=x)
  unseeded = numpy.subtract.reduce(arr, axis=1)

  pyctos_prove(seeded[0] == int(x) - 18)
  pyctos_prove(unseeded[0] == -4)

  if seeded[0] == unseeded[0]:
    pass


@pyctos_test('numpy.ufuncs')
def reduce_symbolic_keepdims(keepdims, x):
  """
  Tests reduce with symbolic keepdims changing result rank
  """
  arr = numpy.zeros((2, 3), dtype=int)
  arr[0, 0] = x
  arr[0, 1] = 12

  result = numpy.add.reduce(arr, axis=1, keepdims=keepdims)

  if result.ndim == 2:
    pyctos_prove(result.shape[0] == 2)
    pyctos_prove(result.shape[1] == 1)
    pyctos_prove(result[0, 0] == arr[0, 0] + 12)

    if result[0, 0] == 37:
      pass
  else:
    pyctos_prove(result.ndim == 1)
    pyctos_prove(result.shape[0] == 2)
    pyctos_prove(result[0] == arr[0, 0] + 12)

    if result[0] == 37:
      pass


@pyctos_test('numpy.ufuncs')
def reduce_negative_tuple_axes(col, x):
  """
  Tests reducing over negative tuple axes with kept dimensions
  """
  arr = numpy.zeros((2, 3, 2), dtype=int)
  arr[0, 0, 0] = x
  arr[1, 0, 1] = 15
  arr[0, 1, 0] = 60
  arr[0, 2, 0] = 120

  result = numpy.add.reduce(arr, axis=(-3, -1), keepdims=True)

  pyctos_assert(result.shape == (1, 3, 1))
  pyctos_prove(result[0, 0, 0] == arr[0, 0, 0] + 15)
  pyctos_prove(result[0, 1, 0] == 60)
  pyctos_prove(result[0, 2, 0] == 120)

  if result[0, col, 0] == 60:
    pass


@pyctos_test('numpy.ufuncs')
def reduce_all_axes(x):
  """
  Tests all-axis reduce returning scalar unless array return is forced
  """
  arr = numpy.zeros((2, 2), dtype=int)
  arr[0, 0] = x
  arr[1, 1] = 15

  scalar = numpy.add.reduce(arr, axis=None)
  forced = numpy.add.reduce(arr, axis=None, out=...)

  pyctos_prove(scalar == arr[0, 0] + 15)
  pyctos_assert(forced.shape == ())
  pyctos_prove(forced[()] == scalar)

  if forced[()] == 26:
    pass


@pyctos_test('numpy.ufuncs')
def reduce_empty_axis_identity(x):
  """
  Tests omitted initial using the ufunc identity for empty reductions
  """
  arr = numpy.zeros((2, 0), dtype=int)
  out = numpy.zeros((2,), dtype=int)
  out[0] = x

  result = numpy.add.reduce(arr, axis=1, out=out)

  pyctos_assert(result.shape == (2,))
  pyctos_prove(result[0] == 0)
  pyctos_prove(out[0] == 0)

  if out[0] == int(x):
    pass


@pyctos_test('numpy.ufuncs')
def reduce_empty_axis_initial(initial):
  """
  Tests explicit initial on empty reductions without an identity
  """
  arr = numpy.zeros((2, 0), dtype=int)

  result = numpy.subtract.reduce(arr, axis=1, initial=initial)

  pyctos_assert(result.shape == (2,))
  pyctos_prove(result[0] == int(initial))

  if result[1] == 5:
    pass


@pyctos_test('numpy.ufuncs')
def reduce_rejects_empty_axis_without_initial(axis):
  """
  Tests rejecting empty reductions without an identity or initial
  """
  arr = numpy.zeros((2, 0), dtype=int)

  result = numpy.subtract.reduce(arr, axis=axis)

  pyctos_assert(result.shape == (0,))
  pyctos_assert(axis != 1)
  pyctos_assert(axis != -1)


@pyctos_test('numpy.ufuncs')
def reduce_out_alias(x):
  """
  Tests reduce writing and returning out=
  """
  arr = numpy.zeros((2, 2), dtype=int)
  out = numpy.zeros((2,), dtype=int)
  arr[0, 0] = x
  arr[0, 1] = 3

  result = numpy.add.reduce(arr, axis=1, out=out)

  pyctos_prove(result[0] == arr[0, 0] + 3)
  result[1] = x
  pyctos_prove(out[1] == int(x))

  if out[1] == 7:
    pass


@pyctos_test('numpy.ufuncs')
def reduce_keepdims_out_shape(keepdims, x):
  """
  Tests keepdims selecting whether out= shape is valid
  """
  arr = numpy.zeros((2, 2), dtype=int)
  out = numpy.zeros((2, 1), dtype=int)
  arr[0, 0] = x
  arr[0, 1] = 3

  result = numpy.add.reduce(arr, axis=1, keepdims=keepdims, out=out)

  pyctos_assert(keepdims)
  pyctos_prove(result[0, 0] == arr[0, 0] + 3)
  result[1, 0] = x
  pyctos_prove(out[1, 0] == int(x))

  if out[0, 0] == 10:
    pass


@pyctos_test('numpy.ufuncs')
def reduce_rejects_multi_axis_subtract(axis_0, axis_1):
  """
  Tests rejecting multi-axis reduction for non-reorderable ufuncs
  """
  arr = numpy.zeros((2, 2), dtype=int)

  numpy.subtract.reduce(arr, axis=(axis_0, axis_1))
  pyctos_assert(False)  # should be unreachable


@pyctos_test('numpy.ufuncs')
def reduce_rejects_duplicate_axes(axis):
  """
  Tests rejecting duplicate axes in reduce
  """
  arr = numpy.zeros((2, 2), dtype=int)

  numpy.add.reduce(arr, axis=(axis, axis))
  pyctos_assert(False)  # should be unreachable


@pyctos_test('numpy.ufuncs', run_timeout=180_000, solver_timeout=20_000)
def reduce_synthesized_input(arr):
  """
  Tests reducing a synthesized ndarray
  """
  if isinstance(arr, numpy.ndarray):
    if arr.ndim == 2 and arr.shape[0] == 2 and arr.shape[1] == 2:
      result = numpy.add.reduce(arr, axis=1)

      pyctos_assert(result.shape == (2,))
      pyctos_prove(equals(result[0], numpy.add(
        arr[0, 0], arr[0, 1], dtype=arr.dtype)))
      pyctos_prove(equals(result[1], numpy.add(
        arr[1, 0], arr[1, 1], dtype=arr.dtype)))


@pyctos_test('numpy.ufuncs', run_timeout=180_000, solver_timeout=20_000)
def reduce_synthesized_out(out):
  """
  Tests reducing into a synthesized out= array
  """
  if isinstance(out, numpy.ndarray):
    if out.ndim == 1 and out.shape[0] == 1:
      arr = numpy.zeros((1, 2), dtype=out.dtype)
      arr[0, 0] = 7

      result = numpy.add.reduce(arr, axis=1, out=out)

      pyctos_prove(result[0] == arr[0, 0])

      result[0] = arr[0, 1]
      pyctos_prove(out[0] == arr[0, 1])


@pyctos_test('numpy.ufuncs', run_timeout=180_000, solver_timeout=20_000)
def reduce_synthesized_input_concrete_out(arr):
  """
  Tests reducing a synthesized ndarray with concrete out=
  """
  if isinstance(arr, numpy.ndarray):
    if arr.ndim == 2 and arr.shape[0] == 2 and arr.shape[1] == 2:
      out = numpy.zeros((2,), dtype=arr.dtype)

      result = numpy.add.reduce(arr, axis=1, out=out)

      pyctos_prove(equals(result[0], out[0]))
      pyctos_prove(equals(out[0], numpy.add(
        arr[0, 0], arr[0, 1], dtype=arr.dtype)))
      result[1] = arr[0, 0]
      pyctos_prove(equals(out[1], arr[0, 0]))


@pyctos_test('numpy.ufuncs', run_timeout=180_000, solver_timeout=20_000)
def reduce_synthesized_both(arr, out):
  """
  Tests reducing a synthesized ndarray into synthesized out=
  """
  if (isinstance(arr, numpy.ndarray) and
      isinstance(out, numpy.ndarray) and
      arr.ndim == 2 and arr.shape[0] == 1 and arr.shape[1] == 2 and
          out.ndim == 1 and out.shape[0] == 1):
    expected = numpy.zeros((1,), dtype=out.dtype)
    expected[0] = arr[0, 0] + arr[0, 1]
    result = numpy.add.reduce(arr, axis=1, out=out)

    pyctos_prove(equals(result[0], expected[0]))

    result[0] = expected[0]
    pyctos_prove(equals(out[0], expected[0]))


@pyctos_test('numpy.ufuncs')
def reduce_out_casts_result(x):
  """
  Tests reduce accumulator dtype distinct from out= dtype
  """
  arr = numpy.zeros((2,), dtype=float)
  out = numpy.zeros((), dtype=int)
  arr[0] = x
  arr[1] = 0.75

  scalar = numpy.subtract.reduce(arr)
  stored = numpy.subtract.reduce(arr, out=out)
  int_result = numpy.subtract.reduce(arr, dtype=int)

  pyctos_prove(stored[()] == int(scalar))

  if stored[()] == int_result:
    pass
