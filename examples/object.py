# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


@pyctos_test('object')
def simple_object(arg):
  if arg.x == 5:
    pass


class Bar:
  @pyctos_test('object')
  def mutate(self):
    self.f = 42
    if len(self.g) < 10 and len(self.g) > 5 and self.f in self.g:
      pass
    if self.h == 12:
      g = self.g
      g[4] = self.h
      if g[3] < g[4]:
        pass


class Foo:
  @pyctos_test('object')
  def foo(self) -> int:
    if self.a > self.c.f:
      if self.b > self.c.h:
        return self.a + self.b
      else:
        return 0
    else:
      return self.b

  @pyctos_test('object')
  def bar(self) -> int:
    return self.foo()


@pyctos_test('object')
def instance(obj):
  if isinstance(obj, Foo):
    pass
  elif isinstance(obj, Bar):
    pass
  elif isinstance(obj, bool):
    pass
  elif isinstance(obj, list):
    pass
