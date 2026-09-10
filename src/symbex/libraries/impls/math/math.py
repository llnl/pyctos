# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import math
from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue
from symbex.globals.globals import record_path
import symbex.symbolic.util as util
from symbex.smtlib import *

inf = math.inf
nan = math.nan


def isinf(x, /):
  if isinstance(x, SymbolicValue):
    smt = get_smt_lib()
    record_path(makeSymbolicValue(v=type(x.get_value()) is float,
                formula=util.is_float(x.get_formula())))
    assert type(x.get_value()) is float
    return makeSymbolicValue(v=math.isinf(x.get_value()), formula=smt.Or(
        util.is_pos_inf(util.get_float(x.get_formula())),
        util.is_neg_inf(util.get_float(x.get_formula()))))
  else:
    return math.isinf(x)


def isnan(x, /):
  if isinstance(x, SymbolicValue):
    record_path(makeSymbolicValue(v=type(x.get_value()) is float,
                formula=util.is_float(x.get_formula())))
    assert type(x.get_value()) is float
    return makeSymbolicValue(v=math.isnan(x.get_value()), formula=util.is_nan(util.get_float(x.get_formula())))
  else:
    return math.isnan(x)


def isfinite(x, /):
  if isinstance(x, SymbolicValue):
    record_path(makeSymbolicValue(v=type(x.get_value()) is float,
                formula=util.is_float(x.get_formula())))
    assert type(x.get_value()) is float
    return makeSymbolicValue(v=math.isfinite(x.get_value()), formula=util.is_finite(util.get_float(x.get_formula())))
  else:
    return math.isfinite(x)
