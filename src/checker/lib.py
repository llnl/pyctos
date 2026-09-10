# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import importlib
import importlib.util
import sys
import dill
import os
import logging
import inspect
import signal
import traceback
import builtins
from pathlib import Path
from collections.abc import Callable
from types import ModuleType
from typing import Any, List, Dict, Generator, Tuple, Set
from coverage import Coverage
from contextlib import contextmanager
from functools import partial

from symbex.runtime import PyctosAssertionError

logger = logging.getLogger(__name__)


class TimeoutException(Exception):
  pass


@contextmanager
def time_limit(seconds: int) -> Generator[None, None, None]:
  def signal_handler(*args):
    del args
    raise TimeoutException("Execution timed out.")

  signal.signal(signal.SIGALRM, signal_handler)
  signal.alarm(seconds)

  try:
    yield
  finally:
    signal.alarm(0)


class hide_prints:
  def __enter__(self):
    self._original_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')

  def __exit__(self, *args):
    del args
    sys.stdout.close()
    sys.stdout = self._original_stdout


def import_from_path(module_name: str, file_path: str) -> ModuleType:
  spec = importlib.util.spec_from_file_location(module_name, file_path)
  if not spec or not spec.loader:
    raise ModuleNotFoundError
  module = importlib.util.module_from_spec(spec)
  sys.modules[module_name] = module
  spec.loader.exec_module(module)
  return module


def load_path_function(name: str, path: str, func: str) -> Callable[..., Any]:
  mod = import_from_path(name, path)
  ret: ModuleType = mod

  for attr in func.split('.'):
    ret = getattr(ret, attr)

  assert callable(ret)

  return ret


def unpickle_arguments(filename: str, funcname: str) -> List[Tuple[Dict[str, Any], Dict[str, Any], str]]:
  inputs: List[Tuple[Dict[str, Any], Dict[str, Any], str]] = []
  path = filename + "_" + funcname + "_inputs"

  input_dirs = os.listdir(path)

  for input_dir in input_dirs:
    specific_path = path + "/" + input_dir
    input_args = os.listdir(specific_path)
    func_input_dict = {}
    glob_input_dict = {}

    for input_arg in input_args:
      if input_arg[:4] == "arg_":
        arg_name = input_arg[4:]

        with open(specific_path + "/" + input_arg, "rb") as file:
          input = dill.load(file)
          func_input_dict[arg_name] = input
      elif input_arg[:5] == "glob_":
        arg_name = input_arg[5:]

        with open(specific_path + "/" + input_arg, "rb") as file:
          input = dill.load(file)
          glob_input_dict[arg_name] = input
      elif input_arg != "filesystem":
        raise NotImplementedError

    inputs.append((func_input_dict, glob_input_dict,
                  f"{specific_path}/filesystem"))

  return inputs


def new_open(old_open: Callable, old_cwd: str, filename: str, *args, **kwargs):
  path = Path(filename)
  if not path.is_absolute():
    path = Path(os.path.join(old_cwd, filename))

  newpath = "/".join(path.parts[1:])
  return old_open(newpath, *args, **kwargs)


def test_path_function(func: Callable[..., Any], path: str, func_name: str) -> None:
  logger.debug("Unpickling...")

  inputs = unpickle_arguments(path, func_name)
  cov = Coverage(
    data_file=None, config_file=False, branch=True, omit=[__file__])

  excepted_inputs: Set[int] = set()

  with cov.collect():
    for idx, (func_input_set, global_input_set, filesystem) in enumerate(inputs):
      # logger.debug(
      #  f"Testing input set #{idx}: {func_input_set}, {global_input_set}...")

      for key, value in global_input_set.items():
        inspect.getmodule(func).__setattr__(key, value)

      owd = os.getcwd()
      os.chdir(filesystem)
      oopen = builtins.open
      builtins.open = partial(new_open, oopen, owd)  # type: ignore

      try:
        with time_limit(1):
          func(**func_input_set)
      except PyctosAssertionError:
        # Re-raise a pyctos assertion to count as test failure through pyctat as well as pyctos
        raise
      except:
        logger.debug(traceback.format_exc())
        excepted_inputs.add(idx)
      finally:
        builtins.open = oopen
        # Fix coverage.py issue where the data lock remains locked after the time limit is hit
        assert cov._collector
        assert cov._collector.data_lock
        if cov._collector.data_lock.locked():
          cov._collector.data_lock.release()
        os.chdir(owd)

  analysis = cov.analysis2(path)
  branch = cov.branch_stats(path)

  func_info = inspect.getsourcelines(func)
  func_linenos = list(
    range(func_info[1] + 1, func_info[1] + len(func_info[0])))

  executed_lines = [x for x in func_linenos if x in analysis[1]]
  missing_lines = [x for x in func_linenos if x in analysis[3]
                   and x not in executed_lines]

  executed_branches = {k: v for k, v in branch.items() if k in func_linenos}
  missing_branches = [
    k for k in executed_branches if executed_branches[k][0] > executed_branches[k][1]]

  logger.info(f"Executed lines: {len(executed_lines)}")
  logger.info(f"Missing lines: {len(missing_lines)}")

  if len(executed_lines) + len(missing_lines) == 0:
    func_cov_percent = 100.0
  else:
    func_cov_percent = round(
      len(executed_lines) / (len(executed_lines) + len(missing_lines)) * 100, 2)

  if len(executed_branches) + len(missing_branches) == 0:
    branch_cov_percent = 100.0
  else:
    branch_cov_percent = round(len(
      executed_branches) / (len(executed_branches) + len(missing_branches)) * 100, 2)

  logger.info(
    f"Function coverage of {func_name}: {func_cov_percent}%")
  if len(missing_lines) > 0:
    logger.info(
      f"Missing lines from coverage: {', '.join(map(lambda x: str(x), missing_lines))}")

  logger.info(
    f"Branch coverage of {func_name}: {branch_cov_percent}%")
  if len(missing_branches) > 0:
    logger.info(
      f"Missing branches from coverage: {', '.join(map(lambda x: str(x), missing_branches))}")

  logger.info(
    f"Inputs that raised an exception in the function: {len(excepted_inputs)}/{len(inputs)} ({len(excepted_inputs) / len(inputs) * 100:.2f}%)")
