# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause


import numpy as np
from pyctest import pyctos_test
from symbex.lib import wrap_concrete, FunctionSummary
from z3 import If, Not
from symbex.symbolic.symbolic import SymbolicValue


def manual_summary(x: SymbolicValue, y: SymbolicValue):
  return FunctionSummary(ret_expr=If(Not(x.get_formula() > y.get_formula()), y.get_formula(), x.get_formula()), global_exprs=dict())


def simple_summary(x: int, y: int) -> int:
  if x > y:
    return x
  else:
    return y


@wrap_concrete(summary=manual_summary, infer_model=False)
def my_np_max(x: int, y: int):
  return int(np.max([x, y]))


@wrap_concrete(summary=simple_summary, infer_model=True)
def my_np_max2(x: int, y: int):
  return int(np.max([x, y]))


def my_max(p: int, q: int, r: int):
  pq = my_np_max(p, q)
  if pq > r:
    return r
  elif pq > 0:
    return pq
  else:
    return -1


def my_max2(p: int, q: int, r: int):
  pq = my_np_max2(p, q)
  if pq > r:
    return r
  elif pq > 0:
    return pq
  else:
    return -1


i = -1


@pyctos_test('mutable')
def fresh():
  global i
  i += 1
  return i


@pyctos_test('mutable')
def global_branch_direct():
  global i

  fresh()

  if i > 10:
    return True
  else:
    return False

# For example:

# py-symbex global_branch_indirect examples/mutable.py
#   Exploring: global_branch_indirect
#   Inputs for all paths:
#   No branches were left unturned!
#   [i=-1]global_branch_indirect()
#   [i=10]global_branch_indirect()


@pyctos_test('mutable')
def global_branch_indirect():

  v = fresh()
  if v > 10:
    return True
  else:
    return False
