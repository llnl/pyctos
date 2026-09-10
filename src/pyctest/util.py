# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import ast
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias, TypeVar


Mode: TypeAlias = Literal['CVC5', 'Z3', 'fuzzing']
VALID_MODES = ('CVC5', 'Z3', 'fuzzing')

FunctionT = TypeVar('FunctionT', bound=Callable[..., Any])


@dataclass(frozen=True)
class PyctosTestConfig:
  """
  Represents a run configuration for an FUT in the Pyctos test suite.
  """
  modes: tuple[Mode, ...] = ('CVC5', 'Z3')
  run_timeout: int = 60_000
  solver_timeout: int = 5_000
  max_depth: int | None = None
  tags: set[str] = field(default_factory=set)
  xfail: str | None = None


def pyctos_test(fun: FunctionT | str | None = None,
                *tags: str,
                mode: Mode | tuple[Mode, ...] = ('CVC5', 'Z3'),
                run_timeout: int = 60_000,
                solver_timeout: int = 5_000,
                max_depth: int | None = None,
                xfail: str | None = None) -> Callable[[FunctionT], FunctionT]:
  """
  Registers an FUT to be run as part of the Pyctos test suite. Defaults to running with
  both CVC5 and Z3, but not attempting fuzzing.

  If `run_timeout` is provided, overrides the default number of milliseconds to
  allow pyctos/tat to run before aborting.

  If `solver_timeout` is provided, overrides the default number of milliseconds
  to allow an individual SMT query to run before aborting.

  If `max_depth` are provided, overrides the Pyctos path depth limit.

  If `xfail` is provided, the test failing will be the success condition. The value of
  `xfail` should be a string explaining the reason for an expected failure.

  `mode` is a tuple of any subset of 'CVC5', 'Z3', 'fuzzing'. SMT solver modes ('CVC5',
  'Z3') are run without the fuzzer.

  This FUT is grouped in with tests sharing its tags, and all tests under a certain tag
  or tags may be run at once. Nested tags are expanded (e.g. `numpy.views`,
  `numpy.broadcasting` would apply the `numpy` tag as well as `numpy.views` and
  `numpy.broadcasting`).
  """
  # Handle *tags passed without a function input
  if fun is not None and not callable(fun):
    tags = (fun, *tags)
    fun = None

  # Expand nested tags
  all_tags: set[str] = set()
  for tag in tags:
    tag_parts = tag.split('.')
    for i in range(len(tag_parts)):
      all_tags.add('.'.join(tag_parts[:i + 1]))

  # Normalize and validate modes
  modes = mode if isinstance(mode, tuple) else (mode,)
  if not all(s in VALID_MODES for s in modes):
    raise ValueError(f'one or more invalid test modes: {modes}')

  # Construct the run configuration
  config = PyctosTestConfig(
    modes, run_timeout, solver_timeout, max_depth, all_tags, xfail)

  # The decorator just adds the run configuration as an attribute to the FUT
  def decorate(fun: FunctionT) -> FunctionT:
    setattr(fun, '__pyctos_test_config__', config)
    return fun

  # Support both zero-argument @pyctos_test and configured @pyctos_test(...)
  if fun is None:
    return decorate
  return decorate(fun)


def get_test_config(decorators: list[ast.expr]) -> PyctosTestConfig | None:
  """
  Extracts test configuration from a function. If the function is not decorated
  with `@pyctos_test`, returns `None`.
  """
  for decorator in decorators:
    # Determine whether this function is annotated with @pyctos_test
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    is_test = ((isinstance(target, ast.Name) and target.id == 'pyctos_test') or
               (isinstance(target, ast.Attribute) and target.attr == 'pyctos_test'))
    if not is_test:
      continue

    # Zero-args @pyctos_test uses default options for the test config
    if not isinstance(decorator, ast.Call):
      fun = pyctos_test(lambda: None)
      return getattr(fun, '__pyctos_test_config__')

    # Otherwise, evaluate the decorator call and read the config it attaches
    # We first have to evaluate literals in the function arguments
    args = [ast.literal_eval(arg) for arg in decorator.args]
    kwargs = {}
    for keyword in decorator.keywords:
      if keyword.arg is None:
        raise ValueError("invalid keyword argument to @pyctos_test")
      kwargs[keyword.arg] = ast.literal_eval(keyword.value)

    # Now annotate the function and read from its attached config
    fun = pyctos_test(*args, **kwargs)(lambda: None)
    return getattr(fun, '__pyctos_test_config__')

  return None
