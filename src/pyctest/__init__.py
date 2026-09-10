# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest.util import Mode, PyctosTestConfig, pyctos_test


__all__ = [
  'Mode', 'PyctosTestConfig', 'main', 'pyctos_test',
]


def main() -> None:
  # Only import the runner here so it's not needlessly loaded into test modules
  from pyctest.runner import main as run
  run()
