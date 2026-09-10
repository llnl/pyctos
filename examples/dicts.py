# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


@pyctos_test('dict')
def is_dict(x):
  if x["hello"] == 5:
    pass


@pyctos_test('dict')
def dict_key(x, s):
  if s == 4.7 and x[s] == 7 and x[s + 1] == 8:
    pass


@pyctos_test('dict')
def dict_length(x):
  if isinstance(x, dict) and len(x) == 3 and 3.4 in x:
    pass


@pyctos_test('dict')
def dict_mutate(x, n):
  x["hello"] = 4.6
  if x["hello"] == n and x["there"] == True:
    pass


@pyctos_test('dict')
def dict_contains(x):
  if "wow" in x:
    if isinstance(x, dict):
      pass
    elif isinstance(x, set):
      pass
    elif isinstance(x, str):
      pass


@pyctos_test('dict')
def dict_contains_2(x):
  if 6.7 in x and "wow" in x:
    if isinstance(x, dict):
      pass
    elif isinstance(x, set):
      pass


@pyctos_test('dict')
def dict_contains_3(x):
  if isinstance(x, dict):
    if 6.7 in x and "wow" in x:
      pass


@pyctos_test('dict')
def add_get_len(obj):
  obj[4.5] = 5
  if len(obj) == 5:
    pass


@pyctos_test('dict')
def dict_equals(obj):
  if obj == {3.14: "hello", True: [4, 5]}:
    pass


@pyctos_test('dict')
def dict_keys(obj):
  if 4.5 in obj.keys() and "hello" in obj.keys():
    pass


@pyctos_test('dict', mode='CVC5', xfail='need to implement list/tuple lifting')
def dict_items(obj):
  # TODO: Implement lift_value for lists and tuples! We should be able to handle this!
  if len(obj) == 2 and obj.items()[1][0] == 3.14 and obj.items()[0][1] == "hello":
    pass


@pyctos_test('dict')
def dict_get(obj, default):
  if obj.get("hello", default) == 3:
    pass
