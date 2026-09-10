#!/bin/bash

# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

if [ -e ./pyctos-venv ]; then
    yes | rm -r ./pyctos-venv
fi