# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test
from typing import Any


@pyctos_test('any')
def foo(val: Any) -> None:
  if val == [5, [6, 7]]:
    pass
  elif val == 3.5:
    pass
  elif val == (4, [5, 6], 7, ([8, 9],)):
    pass


class Foo:
  x: int
  y: int


@pyctos_test('any')
def bar(val) -> None:
  try:
    if not isinstance(val, dict) and not isinstance(val, set):
      if len(val) > 5 and len(val) < 10:
        if val[3] == 12:
          pass
        elif val[3] == 2.5:
          pass
  except:
    pass

  try:
    if val.x > val.y:
      pass
  except:
    pass
