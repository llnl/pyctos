# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

def dicts(x: dict[int, float]) -> float:
  if 5 in x:
    return x[5]
  else:
    return 0.0
