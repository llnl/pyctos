# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from symbex.libraries.impls.math import math as impl

nan = impl.nan
inf = impl.inf


def isinf(x, /):
  return impl.isinf(x)


def isnan(x, /):
  return impl.isnan(x)


def isfinite(x, /):
  return impl.isfinite(x)
