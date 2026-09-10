# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


class Foo:
  x: int
  y: int

  def __init__(self, x, y):
    self.x = x
    self.y = y


class ComplexAssignment:
  lst: list[int]
  obj: Foo

  @pyctos_test('assignment')
  def list_assign(self, x: int):
    self.lst = [x, 2, 3]
    if self.lst[0] == 42:
      pass

  @pyctos_test('assignment')
  def obj_assign(self, x: int):
    self.obj = Foo(x, 5)
    if self.obj.x == 42:
      pass


@pyctos_test('assignment')
def list_assign(lst: list[list[int]], x: int):
  if len(lst) > 0:
    lst[0] = [x, 2, 3]

    if lst[0][0] == 42:
      pass


@pyctos_test('assignment')
def obj_assign(lst: list[Foo], x: int):
  if len(lst) > 0:
    lst[0] = Foo(x, 2)

    if lst[0].x == 42:
      pass
