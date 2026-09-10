# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from .smtlib import *
import argparse
import atexit
import logging
import sys
import dill
import os

from pathlib import Path
from importlib.metadata import version
from typing import NamedTuple, cast, Any, Callable
from types import ModuleType

logger: logging.Logger


def run_concolic_execution(func: Callable[..., Any], func_name: str, func_path: str, fuzzing: bool, origin: ModuleType):
  import symbex.lib as lib
  from symbex.symbolic.factories import concretize_args
  from symbex.engine.engine import untaken_branches, ConcolicEngine

  explored_inputs, yaml_input, engine = lib.explore(func, origin)

  if len(untaken_branches()) > 0 and fuzzing:
    logger.info("Fuzzing %s", func_name)
    explored_inputs += engine.fuzz(func)

  if engine.hit_max_depth:
    logger.info(
      "Warning: encountered maximum exploration depth, some branches might be missing")

  if len(ConcolicEngine.features) == 0:
    logger.info("Inputs for all paths:")

    skipped_invalid_inputs = 0
    dump_id = -1
    for inp_id, inp in enumerate(explored_inputs):
      conc_args = concretize_args(engine.params, inp.input_args)

      glob_args = {g: expr.get_value() for g, expr in inp.global_vars.items()}

      global_print = f"[{','.join(g.name + '=' + str(v) for g, v in glob_args.items())}]"

      def wrap_in_quotes(v: str): return f'"{v}"'.replace("\n", "\\n")

      filesystem_print = f"{{{','.join(key[0] + '=' + wrap_in_quotes(value) for key, value in inp.file_vars.items())}}}"

      # Preprocess arguments for pickling and validity checks
      any_invalid = False

      param_values: dict[str, Any] = {}
      glob_values: dict[str, Any] = {}

      # Preprocess params
      # __prepare_replay_arg__ is a method that returns the actual object to be pickled, if defined
      # The method may raise an exception if the input is invalid, in which case we skip the arg set
      # See `libraries.impls.numpy.array.ndarray` for an example
      for i, param in enumerate(engine.params.parameters.keys()):
        param_value = conc_args.args[i]
        class_attr = getattr(type(param_value), '__prepare_replay_arg__', None)
        if callable(class_attr):
          # This argument has a preprocessing method
          try:
            param_value = class_attr(param_value)
          except:
            # If the preprocessor raised, the argument is invalid
            logger.debug(
              'preprocessing argument "%s" in input set %d failed', param, inp_id, exc_info=True)
            any_invalid = True
        param_values[param] = param_value

      # Preprocess globals
      for i, glob_param in enumerate(inp.global_vars.items()):
        param_value = glob_param[1].get_value()
        class_attr = getattr(type(param_value), '__prepare_replay_arg__', None)
        if callable(class_attr):
          # This argument has a preprocessing method
          try:
            param_value = class_attr(param_value)
          except:
            # If the preprocessor raised, the argument is invalid
            logger.debug(
              'preprocessing global "%s" in input set %d failed', glob_param[0].name, inp_id, exc_info=True)
            any_invalid = True
        glob_values[glob_param[0].name] = param_value

      # If any parameter or global is invalid, the input set is bad
      if any_invalid:
        skipped_invalid_inputs += 1
        continue

      dump_id += 1
      logger.info(global_print + filesystem_print + func_name +
                  make_args(*conc_args.args, **conc_args.kwargs))

      for param, param_value in param_values.items():
        pickle_arguments(param_value, func_path,
                         func_name, param, dump_id, False)

      for glob_param_name, param_value in glob_values.items():
        pickle_arguments(param_value, func_path, func_name,
                         glob_param_name, dump_id, True)

      for file_name, file_value in inp.file_vars.items():
        write_file(file_name[0], file_value, func_path, func_name, dump_id)

    if skipped_invalid_inputs > 0:
      logger.info("Skipped %d invalid inputs", skipped_invalid_inputs)
  elif yaml_input is not None:
    # TODO: argument preprocessing (via __prepare_replay_arg__) does not currently work with a YAML spec
    logger.info("Input which matched YAML:")

    conc_args = concretize_args(engine.params, yaml_input.input_args)

    glob_args = {g: expr.get_value()
                 for g, expr in yaml_input.global_vars.items()}

    global_print = f"[{','.join(g.name + '=' + str(v) for g, v in glob_args.items())}]"

    logger.info(global_print + func_name +
                make_args(*conc_args.args, **conc_args.kwargs))

    for i, param in enumerate(engine.params.parameters.keys()):
      param_value = conc_args.args[i]
      pickle_arguments(param_value, func_path,
                       func_name, param, "yaml_match", False)

    for i, glob_param in enumerate(yaml_input.global_vars.items()):
      param_value = glob_param[1].get_value()
      pickle_arguments(param_value, func_path, func_name,
                       glob_param[0].name, "yaml_match", True)
  else:
    logger.info("Could not find input which matched YAML!")


def make_args(*args, **kwargs):
  ret = "("
  newargs = [repr(x) for x in args]
  newkwargs = [f"{str(k)}={repr(v)}" for k, v in kwargs.items()]
  ret += ", ".join(newargs + newkwargs)
  ret += ")"
  return ret


def create_folder(filename: str, funcname: str, pairing: Union[str, int]) -> str:
  foldername = filename + "_" + funcname + "_inputs"
  if not os.path.isdir(foldername):
    os.mkdir(foldername)
  foldername += "/" + str(pairing)
  if not os.path.isdir(foldername):
    os.mkdir(foldername)
  filesystem = f"{foldername}/filesystem"
  if not os.path.isdir(filesystem):
    os.mkdir(filesystem)
  return foldername


def pickle_arguments(obj: Any, filename: str, funcname: str, argname: str, pairing: Union[int, str], isglobal: bool) -> None:
  foldername = create_folder(filename, funcname, pairing)
  filename = ("arg_" if not isglobal else "glob_") + argname
  fullpath = foldername + "/" + filename
  with open(fullpath, "wb") as file:
    dill.dump(obj, file)


def write_file(name: str, contents: str, filename: str, funcname: str, pairing: Union[int, str]) -> None:
  foldername = create_folder(filename, funcname, pairing) + "/filesystem"
  # `name` is always absolute because of how we've overridden the `open` function
  # thus, we need to strip off the first part of the path
  path = os.path.join(foldername, "/".join(Path(name).parts[1:]))
  # create the owning directory
  os.makedirs(Path(path).parent.as_posix(), exist_ok=True)
  with open(path, "w") as file:
    file.write(contents)


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


class PySymbArgs(NamedTuple):
  filename: str
  function: str
  verbose: bool
  smt: str
  fuzzing: bool
  max_depth: int
  timeout: int
  yaml: str
  float: str


def main():
  global logger

  FMT = "%(asctime)s | %(levelname)-8s | %(message)s"
  DATEFMT = "%Y-%m-%d %H:%M:%S"

  handler = logging.StreamHandler(sys.stdout)
  handler.setFormatter(ColorFormatter(FMT, datefmt=DATEFMT))

  logging.basicConfig(level=logging.INFO, handlers=[handler])
  logger = logging.getLogger(__name__)

  parser = argparse.ArgumentParser(
    prog='pyctos',
    description='Concolic execution for Python')

  parser.add_argument('--version', action='version', version=version('pyctos'))
  parser.add_argument('filename', type=str,
                      help='path to source file of function to test')
  parser.add_argument('-f', '--function', type=str,
                      help='name of function to test, relative to the source file')
  parser.add_argument('-v', '--verbose', action='store_true',
                      help='display debugging info')
  parser.add_argument('--fuzzing', action='store_true',
                      help='enable fuzzing for this run')
  parser.add_argument('--smt', type=str, default='cvc5',
                      help='SMT solver to use (z3, cvc5 (default))')
  parser.add_argument('--float', type=str, default='exreal',
                      help='specify the SMT theory to use for Python floats (fp64, real, exreal (default))')
  parser.add_argument('--max-depth', type=int,
                      help='maximum exploration depth before terminating execution')
  parser.add_argument('--timeout', type=int,
                      help='maximum duration for SMT solver to attempt to generate new input (milliseconds)')
  parser.add_argument('--yaml', type=str,
                      help='YAML rule file to guide concolic testing')

  args = cast(PySymbArgs, parser.parse_args())

  if args.verbose:
    logger.setLevel(logging.DEBUG)

  if args.smt.lower() == "z3":
    logger.debug("Using Z3 solver")
    set_smt_lib(SMTLibrary.Z3)
  elif args.smt.lower() == "cvc5":
    logger.debug("Using CVC5 solver")
    set_smt_lib(SMTLibrary.CVC5)
  else:
    raise ValueError("--smt should be one of 'z3' or 'cvc5'!")

  if args.float.lower() == "real":
    set_float_theory(FloatTheory.REAL)
  elif args.float.lower() == "fp64":
    set_float_theory(FloatTheory.FP64)
  elif args.float.lower() == "exreal":
    set_float_theory(FloatTheory.EXREAL)
  else:
    raise ValueError("--float should be one of 'real', 'fp64', or 'exreal'!")

  import symbex.lib as lib
  import symbex.engine.engine as engine
  from symbex.yaml import parse_yaml

  if args.max_depth:
    engine.ConcolicEngine.set_max_execution_depth(args.max_depth)
  if args.timeout:
    engine.ConcolicEngine.set_timeout(args.timeout)
  if args.yaml:
    yaml_rule = parse_yaml(args.yaml)
    engine.ConcolicEngine.set_yaml(yaml_rule)

  atexit.register(on_exit)

  if isinstance(args.function, str):
    func, origin = lib.load_path_function("FUT", args.filename, args.function)
    logger.info("Exploring %s", args.function)
    run_concolic_execution(
      func, args.function, args.filename, args.fuzzing, origin)
  else:
    lib.load_module("FUT", args.filename)


def on_exit():
  import symbex.engine.engine as engine

  logger = logging.getLogger(__name__)

  for line, column in engine.untaken_branches():
    logger.info(f"Branch at line {line} column {column} was not taken!")

  if len(engine.untaken_branches()) == 0:
    logger.info("No branches were left unturned!")
