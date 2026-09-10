# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


@pyctos_test('assignment')
def foo(x: int, y: int) -> int:
  z = x - y
  if z < 1:
    x += 2
    y += 2
    if x + y < 0:
      return x
    else:
      return 0
  else:
    return y
