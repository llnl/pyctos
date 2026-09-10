# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

def _pyctos_internal_evaluate_condition(value, _pyctos_internal_eval_string: str):
  from symbex.overrides.overrides import intercept_len as len, intercept_float as float, intercept_int as int, intercept_isinstance as isinstance
  return eval(_pyctos_internal_eval_string)
