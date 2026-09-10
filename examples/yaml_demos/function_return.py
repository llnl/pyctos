# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

def parse_args(args):
  split_args = args.split(" ")
  check_args(split_args[0], split_args[1])


def check_args(flag, value):
  if flag == "--buffer":
    allocate_buffer(int(value))


def allocate_buffer(bytes):
  if bytes < 65536:
    return 0xDEADBEEF
  else:
    return -1
