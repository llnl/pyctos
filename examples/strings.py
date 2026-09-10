# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


@pyctos_test('string')
def foo(x):
  if x == "hello, world!":
    pass
  elif not isinstance(x, dict) and len(x) == 2 and x[0] == 4.2 and x[1] == "second element":
    pass
  elif isinstance(x, str) and len(x) == 5:
    pass


@pyctos_test('string')
def bar(x):
  if isinstance(x, str) and len(x) > 5 and "hey" in x:
    pass
  if 5 in x:
    pass


@pyctos_test('string')
def repeat(x, y):
  if y > 1 and x * y == "hellohellohello":
    pass


@pyctos_test('string')
def slice(x):
  if isinstance(x, str) and x[:-1] == "ell":
    pass


@pyctos_test('string')
def slice_symbolic_start(x, i):
  if isinstance(x, str) and x[i:3] == "ab":
    pass


@pyctos_test('string')
def slice_symbolic_stop(x, i):
  if isinstance(x, str) and x[3:i] == "bc":
    pass


@pyctos_test('string')
def slice_symbolic(x, i, j):
  if isinstance(x, str) and x[i:j] == "cd":
    pass


@pyctos_test('string')
def split(x, y):
  parts = x.split(";")

  if len(parts) == 3:
    if y == 12:
      pass
    elif int(parts[0]) == 12 and int(parts[1]) == 34 and int(parts[2]) == 56:
      pass
