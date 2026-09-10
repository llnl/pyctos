# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


@pyctos_test('branching')
def foo(x: int, y: int) -> int:
  if x < 10 or x > 20:
    if x > 30:
      return 1
    elif x < 0:
      return 2
    else:
      return 3
  elif x < y and y == 15:
    return 4
  else:
    return 5
