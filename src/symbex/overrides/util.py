# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from functools import reduce
from typing import List, Any, Union, Tuple, Optional, cast

from pathlib import Path
from symbex.yaml import get_all_Api

from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue
from symbex.globals.globals import record_path, make_assertion, get_engine
from symbex.overrides.eval import _pyctos_internal_evaluate_condition
import symbex.symbolic.util as util

import logging
import os

from symbex.smtlib import get_smt_lib
smt = get_smt_lib()

logger = logging.getLogger(__name__)

taken_history: dict[tuple[int, int], tuple[bool, bool]] = {}


def mark_taken(key: tuple[int, int], taken: bool) -> None:
  """
  Marks a branch as either taken or not taken.

  `key` is a tuple of `(line, col)` based on its location in the source code as a unique identifier for this branch.
  `taken` denotes whether the branch was taken.
  """
  if not key in taken_history:
    taken_history[key] = False, False
  previously_taken, previously_not_taken = taken_history[key]
  if taken:
    taken_history[key] = True, previously_not_taken
  else:
    taken_history[key] = previously_taken, True


def get_taken() -> dict[tuple[int, int], tuple[bool, bool]]:
  """
  Gets the full dictionary of branch history.

  The return value is `(line, col) -> (taken, nottaken)`.
  """
  return taken_history


def check_function_yaml(name: str, conc_args: List[Any], args: Tuple[Any, ...], conc_ret: Any, ret: Any) -> None:
  """
  Check if a function call, its arguments, and its return value matches a YAML feature.
  """
  from symbex.engine.engine import ConcolicEngine, StopSearching
  logger.debug(
    f"Comparing {name}({', '.join([str(arg) for arg in conc_args])}) == {conc_ret}")
  for feature in ConcolicEngine.features:  # Iterate through all features
    for api in get_all_Api(feature):  # Iterate through all API nodes in a feature
      if api.name == name:  # Check if the function name is the same
        match: bool = True
        if api.ret is not None:
          if conc_ret != api.ret:
            record_path(ret == api.ret)
            match = False
        for arg in api.args:
          if arg.id < len(conc_args) and arg.id < len(args):
            eval_result = _pyctos_internal_evaluate_condition(
              args[arg.id], arg.expression)
            try:
              logger.debug(f"Eval resulted in: {eval_result}")
            except:
              pass
            if isinstance(eval_result, SymbolicValue) and not eval_result.get_value():
              record_path(eval_result)
              match = False
            elif not isinstance(eval_result, SymbolicValue) and not eval_result:
              match = False
          else:
            logger.debug(
              f"ID {arg.id} out of range: conc_args length == {len(conc_args)}, args length == {len(args)}")
            match = False
        if match:
          api.set()

    feature.propagate()
    if feature.triggered:
      raise StopSearching("Found input!")


class SymbolicVariableExpected(Exception):
  """
  Base exception for expecting a symbolic variable and not receiving one.
  """

  def __init__(self, *args: object) -> None:
    super().__init__(*args)


class RangeHelper:
  def __init__(self, args: List[Any]):
    """
    Initializes the `RangeHelper`.

    The following special arguments are required:
    - `args[0]` - the line number this range appears at
    - `args[1]` - the column number this range appears at
    - `args[2:]` - the normal range arguments
    """
    self.lineno = args[0]
    self.colno = args[1]
    self.args = args[2:]

  def has_any_symbolic(self) -> bool:
    """
    Checks if any of the parameters are instances of `SymbolicValue`.
    """
    return reduce(lambda any_symbolic, var: any_symbolic or isinstance(var, SymbolicValue), self.args, False)

  def capture_symbolic_iterator(self) -> Union[SymbolicValue, int]:
    """
    Gets the `SymbolicValue` iterator to use if possible, otherwise return `int`.
    """
    if len(self.args) == 1:
      return 0
    else:
      if isinstance(self.args[0], SymbolicValue):
        return self.args[0]
      elif isinstance(self.args[1], SymbolicValue):
        return self.args[1] - (self.args[1] - self.args[0])
      elif len(self.args) == 3 and isinstance(self.args[2], SymbolicValue):
        # Duplicate as first check, but more readable this way, since the return type here is an int, not a SymbolicValue
        return self.args[0]
      else:
        # This should never be hit, as this function isn't called unless has_any_symbolic returns true.
        # Nevertheless, we should make a note if something went wrong!
        raise SymbolicVariableExpected

  def capture_end_value(self) -> Union[SymbolicValue, int]:
    """
    Gets the end value of this iterator.
    """
    if len(self.args) == 1:
      return self.args[0]
    else:
      return self.args[1]

  def capture_stride(self) -> Union[SymbolicValue, int]:
    """
    Gets the stride of this iterator.
    """
    if len(self.args) == 3:
      return self.args[2]
    else:
      return 1

  @staticmethod
  def continue_loop(begin: Union[SymbolicValue, int], end: Union[SymbolicValue, int]) -> bool:
    """
    Checks if we are to continue iterating this loop.
    """
    condition = begin < end
    if isinstance(condition, bool):
      return condition
    elif isinstance(condition, SymbolicValue):
      return condition.v
    else:
      raise SymbolicVariableExpected


class RangeIterator:
  @staticmethod
  def max_loop_iterations() -> int:
    """
    Max loop iterations.
    Default currently is `10`.
    """
    return 10

  def __init__(self, lineno: int, colno: int, starting_value, ending_value, stride):
    """
    Initializer for the iterator.
    """
    self.lineno = lineno
    self.colno = colno
    self.starting_value = starting_value
    self.ending_value = ending_value
    self.stride = stride

  def __iter__(self):
    """
    Prepares the iterator for execution.
    Marks if this loop is skipped as branch history.

    The return value is `RangeIterator`.
    """
    self.ctr = 0
    if not RangeHelper.continue_loop(self.starting_value, self.ending_value):
      mark_taken((self.lineno, self.colno), False)
    return self

  def __next__(self) -> SymbolicValue:
    """
    Gets the next value from iterating this object.
    Raises `StopIteration` if there is nothing more to iterate.

    Marks if a new value is yielded as branch history.
    """
    ret = self.starting_value
    self.starting_value += self.stride

    if RangeHelper.continue_loop(ret, self.ending_value) and self.ctr <= RangeIterator.max_loop_iterations():
      mark_taken((self.lineno, self.colno), True)
      self.ctr += 1
      return ret
    else:
      raise StopIteration


class SymbolicIO:
  filename: str
  read_iteration: int
  contents: SymbolicValue
  lines: Optional[SymbolicValue]
  line: Optional[int]

  def __init__(self, filename: Union[SymbolicValue, str]):
    self.read_iteration = 0
    self.lines = None
    self.line = None

    filename_str = filename.get_value() if isinstance(
      filename, SymbolicValue) else filename
    assert type(filename_str) is str
    self.filename = Path(filename_str).absolute().as_posix()

    self.contents = self._get_contents()

  def _sanitize_filename(self) -> str:
    ret = ""
    for c in self.filename:
      if c.isalnum():
        ret += c
      else:
        ret += "_"
    return ret

  def _get_contents(self) -> SymbolicValue:
    engine = get_engine()
    file_name = f"read_var_{self._sanitize_filename()}"
    smt_variable = smt.Const(file_name, util.any_sort)
    make_assertion(makeSymbolicValue(
     v=True, formula=util.is_string(smt_variable)))

    engine.filemap[self.filename, file_name] = smt_variable
    record_path(makeSymbolicValue(
      v=False, formula=util.get_string(smt_variable) == ""))

    self.contents = makeSymbolicValue(v=engine.file_concs.get(
      (self.filename, file_name), ""), formula=smt_variable)

    return self.contents

  def __enter__(self, *args, **kwargs) -> "SymbolicIO":
    return self

  def __exit__(self, *args, **kwargs) -> None:
    pass

  def write(self, text: Union[SymbolicValue, str]) -> None:
    pass

  def read(self) -> SymbolicValue:
    contents = self.contents
    self.contents = contents[contents.__len__():]
    return contents

  def readlines(self) -> SymbolicValue:
    raise NotImplementedError

  def readline(self) -> SymbolicValue:
    contents = self.contents
    conc_index = cast(str, contents.get_value()).find("\n")
    conc_index = conc_index + \
        1 if conc_index >= 0 else len(contents.get_value())
    sym_index = smt.IndexOf(util.get_string(contents.get_formula()), "\n", 0)
    sym_index = smt.If(sym_index >= 0, sym_index + 1,
                       smt.Length(util.get_string(contents.get_formula())))

    retval = makeSymbolicValue(v=contents.get_value()[:conc_index], formula=util.lift_expr_to_any(smt.SubString(
      util.get_string(contents.get_formula()), 0, sym_index)))
    self.contents = makeSymbolicValue(v=contents.get_value()[conc_index:], formula=util.lift_expr_to_any(smt.SubString(
      util.get_string(contents.get_formula()), sym_index, smt.Length(util.get_string(contents.get_formula())))))
    return retval
