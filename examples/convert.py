# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test


@pyctos_test('convert')
def convert_to_int(x):
  if isinstance(x, bool) or isinstance(x, float):
    if int(x) > int(0.1):
      pass


@pyctos_test('convert')
def convert_to_float(x):
  if isinstance(x, bool) or isinstance(x, int):
    if float(x) > float(0):
      pass


@pyctos_test('convert')
def string_to_int(x):
  if isinstance(x, str) and int(x) == 123:
    pass
