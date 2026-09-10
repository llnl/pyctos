# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

class Expr:
  def __init__(self):
    pass

  def pp(self):
    raise NotImplementedError


class Implies(Expr):
  lhs: Expr
  rhs: Expr

  def __init__(self, lhs: Expr, rhs: Expr):
    self.lhs = lhs
    self.rhs = rhs

  def pp(self) -> str:
    return "(" + self.lhs.pp() + " -> " + self.rhs.pp() + ")"


class Tautology(Expr):
  def __init__(self):
    pass

  def pp(self) -> str:
    return "T"


class Contradiction(Expr):
  def __init__(self):
    pass

  def pp(self) -> str:
    return "F"


def expect_expression(input: str, idx: int):
  success, output, idx = expect_implies(input, idx)
  if success:
    return success, output, idx

  success, output, idx = expect_proposition(input, idx)
  if success:
    return success, output, idx

  return False, None, idx


def expect_implies(input: str, idx: int):
  old_idx = idx
  if idx >= len(input) or input[idx] != "(":
    return False, None, old_idx

  idx += 1
  success, lhs, idx = expect_expression(input, idx)
  if not success:
    return False, None, old_idx

  if idx + 1 >= len(input) or (input[idx] != "-" or input[idx + 1] != ">"):
    return False, None, old_idx

  idx += 2
  success, rhs, idx = expect_expression(input, idx)
  if not success:
    return False, None, old_idx

  if idx >= len(input) or input[idx] != ")":
    return False, None, old_idx

  idx += 1
  return True, Implies(lhs, rhs), idx


def expect_proposition(input: str, idx: int):
  if idx < len(input) and input[idx] == "T":
    idx += 1
    output = Tautology()
    return True, output, idx

  if idx < len(input) and input[idx] == "F":
    idx += 1
    output = Contradiction()
    return True, output, idx

  return False, None, idx


def parse(input: str):
  if isinstance(input, str):
    _, output, _ = expect_expression(input, 0)
    if output is not None:
      print(output.pp())
    return output
  else:
    return None


# Should parse
parse("((T->F)->T)")
# Should parse
parse("(F->((F->F)->T))")
# Shouldn't parse
parse("(F->(F->F->T))")

# This input was found with Pyctos
# idx was not checked against len(input) before doing input[idx]
# This caused the following input to cause an exception in the parser
parse("(((F")

# This input was found with Pyctos
# We weren't verifying that the parameter to the parse function was a string
# Pyctos found several arrays and even dictionaries that parsed like strings
parse(["(", "F", "-", ">", "F", ")"])
