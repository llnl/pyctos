# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


@pyctos_test('set')
def set_len(s):
  if isinstance(s, set) and len(s) == 3:
    pass


@pyctos_test('set')
def set_contains(x):
  if isinstance(x, set):
    if 6.7 in x and "wow" in x:
      pass


@pyctos_test('set')
def set_equals(x):
  if x == {4, 7.0, 5}:
    pass
