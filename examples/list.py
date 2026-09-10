# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


@pyctos_test('list')
def foo(mylist, idx) -> None:
  if idx > 2 and idx < 10 and mylist[idx] == 6:
    ...


@pyctos_test('list')
def bar(mylist, idx) -> None:
  if len(mylist) < 10:
    if mylist[idx] == 2.718:
      ...
    elif mylist[1] - mylist[0] > 5 and mylist[1] <= 10.6:
      ...
    elif mylist[2] < 0:
      ...


@pyctos_test('list')
def baz(mylist: list[int], start: int) -> None:
  for i in range(start, len(mylist)):
    if i > 5:
      ...


@pyctos_test('list')
def nested(twodimensional) -> None:
  if len(twodimensional) < 10 and len(twodimensional[4]) < 10:
    if twodimensional[4][5] == 6:
      ...


@pyctos_test('list')
def assignment(lst: list[int]) -> None:
  if lst[0] == 0 and isinstance(lst, list):
    lst[0] = 42
    if len(lst) == 2 and lst[0] == lst[1] + 1:
      ...


@pyctos_test('list')
def in_list(lst: list[int]) -> None:
  if len(lst) > 0 and 0 in lst:
    ...


@pyctos_test('list')
def iter_list(lst: list[int]) -> None:
  if isinstance(lst, list):
    for i in lst:
      if i == 42:
        ...
      elif i > 12:
        ...


@pyctos_test('list')
def len_list(list) -> None:
  if len(list) == 5:
    ...


@pyctos_test('list')
def list_eq(lst1) -> None:
  if isinstance(lst1, list):
    if lst1 == [3, [4, 5]]:
      ...


@pyctos_test('list')
def list_eq_2(lst1, lst2) -> None:
  if not isinstance(lst1, dict) and not isinstance(lst2, dict):
    if len(lst1) == 2 and len(lst2) > 0:
      if lst1[0] == 4.2 and lst1[1] == lst2:
        ...


@pyctos_test('list')
def append(lst, obj) -> None:
  lst.append(obj)

  if len(lst) == 4 and lst[len(lst) - 1] == "hello":
    ...


@pyctos_test('list')
def pop(lst) -> None:
  if lst.pop() == 4.3 and len(lst) == 1:
    ...


@pyctos_test('list')
def pop_2(lst, obj) -> None:
  lst.append(obj)
  if lst.pop() == "hello" and len(lst) == 2:
    ...
