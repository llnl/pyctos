# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


class Foo:
  def __init__(self):
    self.x = []

  def append(self, item):
    self.x.append(item)

  def __add__(self, item):
    self.x.append(item)

  def __contains__(self, item):
    return item in self.x


@pyctos_test('overload')
def foo(x):
  if isinstance(x, Foo):
    if 4 in x:
      pass
