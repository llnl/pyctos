# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

all: install

install:
	./scripts/install.sh

test:
	pyctest

clean: clean-inputs
	./scripts/uninstall.sh

clean-inputs:
	rm -rf $$(find examples/ -name "*_inputs")
	rm -rf $$(find examples/ -name "__pycache__")