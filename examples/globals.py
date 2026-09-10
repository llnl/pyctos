# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test

x = 0
y = 0


@pyctos_test('globals')
def foo():
  if isinstance(x, list) and len(x) == 6:
    ...

  if y.member == 7:
    ...
