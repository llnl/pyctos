# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import math

from pyctest import pyctos_test
from symbex.runtime import pyctos_prove


@pyctos_test('float')
def foo(x: float, y: float) -> float:
  if x == 1.5:
    return x + y
  elif y + 1.0 == 3.25:
    return y + 2.718
  elif y != 0.0 and x / y > 0.5:
    return x + 1
  else:
    return x - y


@pyctos_test('float')
def cast_float_to_int(x) -> None:
  """
  Tests that casting a float to an int rounds towards zero
  """
  if isinstance(x, float) and -1 < x < 1:
    if x < 0:
      pass

    if x > 0:
      pass

    # Both cases should round towards zero
    pyctos_prove(int(x) == 0)


@pyctos_test('float')
def nan(x):
  if math.isnan(x):
    pass


@pyctos_test('float')
def infty(x):
  if math.isinf(x):
    pass


@pyctos_test('float')
def finite(x):
  if math.isfinite(x):
    pass


@pyctos_test('float')
def nan_arithmetic(x, y):
  if not math.isnan(x) and not math.isnan(y):
    if math.isnan(x * y):
      pass


@pyctos_test('float')
def literal_compare(x):
  if x == 3.14:
    pass
  elif x == math.inf:
    pass
  elif x == -math.inf:
    pass


@pyctos_test('float')
def neq_nan(x):
  if isinstance(x, float):
    pyctos_prove(x != math.nan)


@pyctos_test('float')
def inf_comp(x):
  if x <= -math.inf:
    pass


@pyctos_test('float')
def inf_comp_2(x):
  if x < math.inf:
    pass
