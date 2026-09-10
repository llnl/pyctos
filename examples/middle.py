# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


@pyctos_test('branching')
def foo(x: int) -> int:
  if 4 < x:
    if x <= 5:
      return 1
    else:
      return 2
  else:
    return 3
