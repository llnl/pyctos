# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import argparse
import ast
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from pyctest.util import Mode, PyctosTestConfig, get_test_config


# Describes the status of a test that has already been run
TestStatus: TypeAlias = Literal['passed', 'failed', 'xfailed', 'xpassed']

# Output color codes
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


@dataclass(frozen=True)
class PyctosTest:
  """
  A decorated FUT, and its config, to run through Pyctos
  """
  path: Path
  name: str
  config: PyctosTestConfig

  @property
  def id(self) -> str:
    return f'{self.path}::{self.name}'


@dataclass(frozen=True)
class ModeResult:
  """
  Result from trying one configured run mode for a FUT
  """
  run_mode: Mode
  passed: bool
  pyctos_status: int
  pyctat_status: int | None
  output: str


@dataclass(frozen=True)
class TestResult:
  """
  Result from running all configured modes for a FUT
  """
  status: TestStatus
  run_mode: Mode | None
  output: str

  @property
  def passed(self) -> bool:
    return self.status in ('passed', 'xfailed')


def main() -> None:
  """
  Main pyctest entrypoint.

  This process does discovery, recursively looking at Python files within the designated
  path and performing AST inspection to find functions decorated with @pyctos_test while
  avoiding any potential side effects or missing imports in example code.

  The actual execution is run through pyctos/pyctat subprocesses rather than directly
  calling the hooks in Python, to avoid having to reset any global state.
  """
  parser = argparse.ArgumentParser(
    prog='pyctest',
    description='Run the Pyctos test suite')
  parser.add_argument('path', nargs='?', type=Path,
                      default=Path('examples'),
                      help='file or directory to scan for decorated tests')
  parser.add_argument('-k', '--keyword',
                      help='only run tests whose ID contains this substring')
  parser.add_argument('-t', '--tag', dest='tags', action='append', default=[],
                      help='only run tests with this tag/tags; comma separated values are allowed')
  parser.add_argument('-x', '--exclude-tag', dest='exclude_tags', action='append', default=[],
                      help='exclude tests with this tag/tags; comma separated values are allowed')
  parser.add_argument('-n', '--num-workers', type=int, default=1,
                      help='number of tests to run in parallel (each gets a Python subprocess)')
  parser.add_argument('--list', action='store_true',
                      help='list selected tests without running them')
  parser.add_argument('--list-tags', action='store_true',
                      help='list tags from discovered tests without running them')
  args = parser.parse_args()

  # Collect the tags to filter and exclude
  include_tags = {tag
                  for item in args.tags
                  for tag in map(str.strip, item.split(','))
                  if len(tag) > 0}
  exclude_tags = {tag
                  for item in args.exclude_tags
                  for tag in map(str.strip, item.split(','))
                  if len(tag) > 0}

  # Collect tests
  if not args.list and not args.list_tags:
    print(f'Collecting tests from {args.path}...', flush=True)
  tests = discover_tests(args.path)
  if not args.list and not args.list_tags:
    print(f'Collected {len(tests)} tests', flush=True)

  if args.list_tags:
    # If --list-tags was specified, just dump the tags and exit
    for tag in sorted({tag for test in tests for tag in test.config.tags}):
      print(tag)
    return

  # Apply keyword filtering
  if args.keyword is not None:
    keyword = args.keyword.lower()
    tests = [test for test in tests if keyword in test.id.lower()]

  # Apply tag filtering
  if len(include_tags) > 0:
    tests = [test for test in tests if not include_tags.isdisjoint(
      test.config.tags)]

  # Apply tag exclusions
  tests = [test for test in tests if exclude_tags.isdisjoint(
    test.config.tags)]

  if args.list:
    # If --list was specified, just dump the filtered tests and exit
    for test in tests:
      print(test.id)
    return

  if args.num_workers < 1:
    raise SystemExit('--num-workers must be positive')

  print(f'Filtered to {len(tests)} tests', flush=True)
  print(
    f'Running {len(tests)} tests with {args.num_workers} worker(s)...', flush=True)

  # Iterate through tests and print their results
  results: list[tuple[PyctosTest, TestResult]] = []
  failed: list[tuple[PyctosTest, TestResult]] = []
  for test, result in run_tests(tests, args.num_workers):
    results.append((test, result))
    print_result(test, result)
    if not result.passed:
      failed.append((test, result))

  # Print the test results summary and exit
  print(
    f'Test results: {len(results) - len(failed)}/{len(results)} run successfully.', flush=True)

  if len(failed) > 0:
    print(color('Failures:', RED), flush=True)
    for test, result in failed:
      print(f'  {test.id} ({result.status})', flush=True)

  raise SystemExit(1 if len(failed) > 0 else 0)


def discover_tests(path: Path) -> list[PyctosTest]:
  """
  Parses files and collects FUTs marked with @pyctos_test.
  """
  tests: list[PyctosTest] = []

  # Get a list of Python files in the path recursively
  if path.is_file() and path.suffix == '.py':
    files = [path]
  elif path.is_dir():
    files = sorted(p for p in path.rglob('*.py')
                   if '__pycache__' not in p.parts)
  else:
    files = []

  for file_path in files:
    try:
      module = ast.parse(file_path.read_text(), filename=str(file_path))
    except SyntaxError as e:
      print(color(f'Skipping {file_path}: {e}', YELLOW), flush=True)
      continue

    # Find @pyctos_test annotated function nodes in the module
    for node in module.body:
      # Inspect a top-level function
      if isinstance(node, ast.FunctionDef):
        # Found a function; get the test config if it exists
        config = get_test_config(node.decorator_list)
        if config is not None:
          tests.append(PyctosTest(file_path, node.name, config))

      # Inspect a class definition for decorated methods
      elif isinstance(node, ast.ClassDef):
        for child in node.body:
          if isinstance(child, ast.FunctionDef):
            # Found a method; get the test config if it exists
            config = get_test_config(child.decorator_list)
            if config is not None:
              tests.append(PyctosTest(
                file_path, f'{node.name}.{child.name}', config))

  return tests


def run_tests(tests: list[PyctosTest],
              num_workers: int) -> Iterator[tuple[PyctosTest, TestResult]]:
  """
  Runs a list of tests, either serially or through a thread pool. Worker threads
  each spawn a Python process for pyctos, then one for pyctat.
  """
  if num_workers <= 1:
    for test in tests:
      yield test, run_test(test)
    return

  # Dispatch tests through a pool
  with ThreadPoolExecutor(max_workers=num_workers) as pool:
    futures = [pool.submit(lambda t: (t, run_test(t)), test) for test in tests]
    for future in as_completed(futures):
      yield future.result()  # result is already the (test, result) tuple we want


def run_test(test: PyctosTest) -> TestResult:
  """
  Tries this test's modes in order and accepts the first mode with full coverage.
  Equivalent to the old test runner shell script.
  """
  last_result: ModeResult | None = None

  for mode in test.config.modes:
    # Clear old generated inputs
    shutil.rmtree(Path(f'{test.path}_{test.name}_inputs'), ignore_errors=True)

    result = run_with_mode(test, mode)
    last_result = result

    if result.passed:
      # Test passed
      if test.config.xfail is not None:
        return TestResult('xpassed', mode, result.output)
      return TestResult('passed', mode, result.output)

    # Exit code 1 likely means a pyctos_assert failed; don't retry with another solver
    if result.pyctos_status == 1 or result.pyctat_status == 1:
      break

  output = last_result.output if last_result is not None else 'no modes configured'
  run_mode = last_result.run_mode if last_result is not None else None

  # If we got to here, the test failed
  if test.config.xfail is not None:
    return TestResult('xfailed', run_mode, output)
  return TestResult('failed', run_mode, output)


def run_with_mode(test: PyctosTest, run_mode: Mode) -> ModeResult:
  """
  Runs pyctos to generate inputs, then pyctat to validate replay coverage.
  """
  # Choose solver and fuzzing flag state from the run mode
  # ('fuzzing' is CVC5 with the fuzzer enabled)
  if run_mode == 'fuzzing':
    solver = 'CVC5'
    fuzzing = True
  else:
    solver = run_mode
    fuzzing = False

  # Build the pyctos run command with our overrides
  pyctos_cmd = ['pyctos', str(test.path), '-f',
                test.name, '--smt', solver]
  if fuzzing:
    pyctos_cmd.append('--fuzzing')
  pyctos_cmd += ['--timeout', str(test.config.solver_timeout)]
  if test.config.max_depth is not None:
    pyctos_cmd += ['--max-depth', str(test.config.max_depth)]

  # Run pyctos
  pyctos_status, pyctos_output = run_command(
    pyctos_cmd, test.config.run_timeout)

  # If pyctos fails, this is an immediate test failure (probably a pyctos_assert failed)
  if pyctos_status != 0:
    return ModeResult(run_mode, False, pyctos_status, None, pyctos_output)

  # Run pyctat
  pyctat_cmd = ['pyctat', test.name, str(test.path)]
  pyctat_status, pyctat_output = run_command(
    pyctat_cmd, test.config.run_timeout)

  # Concatenate pyctos + pyctat output for logging
  output = pyctos_output + pyctat_output

  # If pyctat failed to run, the test failed
  if pyctat_status != 0:
    return ModeResult(run_mode, False, pyctos_status, pyctat_status, output)

  # Check if pyctat reported full coverage
  is_covered = (re.search(r'Missing lines: 0', pyctat_output) is not None and
                re.search(r'Function coverage of [A-Za-z0-9_.]+: 100', pyctat_output) is not None and
                re.search(r'Branch coverage of [A-Za-z0-9_.]+: 100', pyctat_output) is not None)
  return ModeResult(run_mode, is_covered,
                    pyctos_status, pyctat_status, output)


def run_command(cmd: list[str], timeout_ms: int) -> tuple[int, str]:
  """
  Runs a subprocess and returns its exit code and combined output.
  """
  try:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          text=True,
                          timeout=timeout_ms / 1000)
    return proc.returncode, proc.stdout

  except subprocess.TimeoutExpired as exc:
    output = exc.stdout or ''
    if isinstance(output, bytes):
      output = output.decode(errors='replace')

    # Match the bash timeout exit code
    return 124, output


def color(text: str, code: str) -> str:
  """
  Adds terminal color codes (only if stdout is interactive).
  """
  if sys.stdout.isatty():
    return f'{code}{text}{RESET}'
  return text


def print_result(test: PyctosTest, result: TestResult) -> None:
  """
  Prints the result of a single test.
  """
  mode = result.run_mode if result.run_mode is not None else 'none'
  label = f'{result.status.upper():7}'
  if result.status == 'passed':
    label = color(label, GREEN)
  elif result.status == 'xfailed':
    label = color(label, YELLOW)
  else:
    label = color(label, RED)

  print(f'{label} {test.id} [{mode}]', flush=True)
  if result.status in ('failed', 'xpassed') and len(result.output) > 0:
    print(result.output.rstrip(), flush=True)


if __name__ == '__main__':
  main()
