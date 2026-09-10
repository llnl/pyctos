# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


@pyctos_test('none')
def foo(x):
  if x == None:
    pass
  elif len(x) == 4 and None in x:
    pass


class Foo:
  pass


@pyctos_test('none')
def bar(x, y):
  if x.field is None:
    x.field = y

    if x.field == 12:
      pass


@pyctos_test('none')
def baz(x):
  if x is not None:
    pass
