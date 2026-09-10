# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


@pyctos_test('branching')
def foo(a, b) -> int:
  if a > 0:
    if b > 0:
      return a + b
    else:
      return 0
  else:
    return b


class Foo:
  @staticmethod
  @pyctos_test('branching')
  def foo(a: int, b: int) -> int:
    if a > 0:
      if b > 0:
        return a + b
      else:
        return 0
    else:
      return b


@pyctos_test('convert')
def bool_conv(x: int) -> bool:
  return bool(x == 0)


@pyctos_test('branching')
def bool_compare(x: int, y: int, z: int, t: int):
  if (x < y) != (z < t):
    pass


@pyctos_test('branching')
def nothing(x):
  if x == False:
    ...


@pyctos_test('branching')
def greater_than_0(x):
  x = x * 2
  if x > 0:
    return True
  else:
    return False
