# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


@pyctos_test('fuzzing', mode='fuzzing')
def fuzz_list(lst: list[int]):
  list_is_long = bool(len(lst) > 5)
  if list_is_long:
    pass


@pyctos_test('fuzzing', mode='fuzzing')
def fuzz_int(x: int):
  mylist = []
  for i in range(0, x):
    mylist.append(i)
  if len(mylist) > 5:
    pass


@pyctos_test('fuzzing', mode='fuzzing')
def fuzz_float(x: float):
  x_is_large = bool(x > 56.7)
  if x_is_large:
    pass
