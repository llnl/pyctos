# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from pyctest import pyctos_test
from symbex.runtime import pyctos_assert, pyctos_prove


@pyctos_test("filesystem")
def file_open():
  with open("some_file.txt", "r") as file:
    if int(file.read()) == 123:
      pass


@pyctos_test("filesystem")
def file_open_absolute():
  with open("/bin/some_file.txt", "r") as file:
    if int(file.read()) == 123:
      pass


@pyctos_test("filesystem")
def file_read_to_end():
  with open("some_file.txt", "r") as file:
    if file.read() == "hello":
      pyctos_prove(file.read() == "")


@pyctos_test("filesystem")
def file_readline_repeat():
  with open("some_file.txt", "r") as file:
    if file.readline() == "hello\n":
      if file.readline() == "world\n":
        if file.read() == "!":
          pass
