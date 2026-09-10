# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


@pyctos_test('loop')
def foo(x: int) -> None:
  for i in range(x, 10):
    if i < 3:
      ...
    elif i > 5:
      ...


@pyctos_test('loop')
def bar(x: int, y: int) -> None:
  for i in range(x, y):
    if i < 3:
      ...
    elif i > 5:
      ...


@pyctos_test('loop')
def baz(x: int, y: int) -> None:
  i = x
  while i < y:
    if i < 3:
      ...
    elif i > 5:
      ...
    i += 1
