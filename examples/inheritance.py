# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


class Foo:
  @pyctos_test('inheritance')
  def method(self):
    return self.x


class Bar(Foo):
  ...


class Baz(Bar):
  ...


class Bee:
  ...


@pyctos_test('inheritance')
def is_baz(obj):
  if isinstance(obj, Foo):
    if isinstance(obj, Baz):
      if obj.method() == 6:
        ...


@pyctos_test('inheritance')
def is_not_baz(obj):
  if not isinstance(obj, Baz) and isinstance(obj, Foo):
    ...
  elif not isinstance(obj, Foo) and isinstance(obj, Bee):
    ...


class A:
  ...


class B(A):
  ...


class C(A):
  ...


class D(B, C):
  ...


@pyctos_test('inheritance')
def diamond(obj):
  if isinstance(obj, A):
    if isinstance(obj, C) and isinstance(obj, D):
      pass
