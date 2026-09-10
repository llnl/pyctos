# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import sys
import logging
import argparse
import checker.lib as lib

from typing import NamedTuple, cast


class ColorFormatter(logging.Formatter):
  # ANSI escape codes
  _COLORS = {
      logging.DEBUG: "\033[36m",   # cyan
      logging.INFO: "\033[32m",   # green
      logging.WARNING: "\033[33m",   # yellow
      logging.ERROR: "\033[31m",   # red
      logging.CRITICAL: "\033[35m",   # magenta
  }
  _RESET = "\033[0m"

  def format(self, record):
    # Inject color if output is a TTY *and* we have a color code
    if sys.stdout.isatty():
      color = self._COLORS.get(record.levelno, "")
      record.levelname = f"{color}{record.levelname}{self._RESET}"
    return super().format(record)


class PyCheckArgs(NamedTuple):
  func_name: str
  func_path: str
  verbose: bool


def main():
  FMT = "%(asctime)s | %(levelname)-8s | %(message)s"
  DATEFMT = "%Y-%m-%d %H:%M:%S"

  handler = logging.StreamHandler(sys.stdout)
  handler.setFormatter(ColorFormatter(FMT, datefmt=DATEFMT))

  logging.basicConfig(level=logging.INFO, handlers=[handler])
  logger = logging.getLogger(__name__)

  parser = argparse.ArgumentParser(
    prog='pyctat',
    description='Concolic execution for Python')

  parser.add_argument('func_name', type=str,
                      help="Name of (possibly nested) function to test, relative to the source file.")
  parser.add_argument('func_path', type=str,
                      help="Path to source file of function to test.")
  parser.add_argument('-v', '--verbose', action='store_true',
                      help='Display debugging info.')

  args = cast(PyCheckArgs, parser.parse_args())

  if args.verbose:
    logger.setLevel(logging.DEBUG)

  func = lib.load_path_function("FUT", args.func_path, args.func_name)

  logger.info(f"Testing {args.func_name}")

  lib.test_path_function(func, args.func_path, args.func_name)
