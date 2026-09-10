# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import json
from symbex.types.symbolicvalue import SymbolicValue


def dump(obj, *args, **kwargs):
  if isinstance(obj, SymbolicValue):
    return json.dump(obj.get_value(), *args, **kwargs)
