# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test
from typing import Union


class Foo:
  ...


@pyctos_test('union')
def int_object(val) -> None:
  try:
    if val + 1 == 6:
      pass
  except:
    pass

  try:
    if val.x == 42:
      pass
  except:
    pass


@pyctos_test('union')
def int_float(val) -> None:
  if val == 5:
    pass
  elif val == 3.5:
    pass


@pyctos_test('union')
def int_float_object_bool(val) -> None:
  if val == 5:
    pass
  elif val == 3.5:
    pass

  if not val:
    pass

  try:
    if val.x == 42:
      pass
  except:
    pass
