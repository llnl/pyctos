#!/bin/bash

# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

AUTOPEP_FOLDERS="src/ examples/"
MYPY_FOLDERS="src/"

if [ ! -e ./pyctos-venv/ ]; then
    python3.11 -m venv pyctos-venv
    source pyctos-venv/bin/activate
    pip install ".[dev,misc]"
else
    source pyctos-venv/bin/activate
fi

autopep8 --in-place $AUTOPEP_FOLDERS -r -i && \
    mypy $MYPY_FOLDERS --check-untyped-defs && \
    pip install ".[dev,misc]"