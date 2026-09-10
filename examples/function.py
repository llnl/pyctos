# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


@pyctos_test('function')
def foo(x: int) -> int:
  if bar(x + 3) == x:
    return x
  else:
    return x + 1


@pyctos_test('function')
def bar(x: int) -> int:
  if x < 0:
    return 1
  else:
    return 2
