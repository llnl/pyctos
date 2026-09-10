# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


@pyctos_test('tuple')
def foo(arg):
  if isinstance(arg, list) and len(arg) == 2:
    (a, b) = arg
    if a == 5 and b == 6:
      pass
  elif isinstance(arg, tuple) and len(arg) == 2:
    (a, b) = arg
    if a == 5 and b == 6:
      pass


@pyctos_test('tuple')
def bar(arg):
  if isinstance(arg, list) or isinstance(arg, tuple):
    if len(arg) == 2:
      arg[0] = "hello"
      if arg[1] == "there":
        pass


@pyctos_test('tuple')
def baz(arg):
  if isinstance(arg, list) or isinstance(arg, tuple):
    arg.append(0)
    if len(arg) == 3:
      pass


@pyctos_test('tuple')
def baz2(arg):
  if isinstance(arg, list) or isinstance(arg, tuple):
    a = arg.pop()
    if a == "hello":
      pass


def self_ownership(arg):
  if isinstance(arg, tuple) and arg[0] == arg:
    pass


@pyctos_test('tuple')
def tuple_eq(arg1, arg2):
  if arg1 == (4, 6) and arg1 == arg2:
    pass


@pyctos_test('tuple')
def tuple_eq2(arg1, arg2):
  if (4, 6) == arg1 and arg1 == arg2:
    pass


@pyctos_test('tuple')
def tuple_contains(arg):
  if "hello" in arg and 6.3 in arg:
    if isinstance(arg, list) or isinstance(arg, tuple):
      pass
