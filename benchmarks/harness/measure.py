from contextlib import redirect_stderr, redirect_stdout
import json
import logging
import multiprocessing
import os
from pathlib import Path
import sys
import traceback
from typing import Any

from coverage import Coverage
from pyan.analyzer import CallGraphVisitor
from pyan.node import Flavor

from .cases import Case, Dataset
from .tools import MissingArtifactError, Tool


FunctionScope = tuple[dict[Path, set[str]], tuple[Path, str]]

_CALLABLES = {
    Flavor.FUNCTION,
    Flavor.METHOD,
    Flavor.STATICMETHOD,
    Flavor.CLASSMETHOD,
}


def build_scopes(dataset: Dataset) -> dict[Case, FunctionScope]:
  """
  Build each target's static dataset-function closure with Pyan.
  """
  root = dataset.root.resolve()
  visitor = CallGraphVisitor(
      sorted(str(path) for path in root.rglob('*.py')),
      root=str(root),
      # Invalid unrelated files do not affect configured target resolution
      logger=logging.Logger('benchmark-pyan', logging.ERROR),
  )

  def function_key(node):
    if node.filename is None:
      return None
    path = Path(node.filename).resolve()
    name = node.get_name()
    modules = [
        module
        for module, filename in visitor.module_to_filename.items()
        if Path(filename).resolve() == path
        and name.startswith(module + '.')
    ]
    if not modules:
      return None
    module = max(modules, key=len)
    return path, name[len(module) + 1:]

  def case_scope(case: Case) -> FunctionScope:
    target_name = f'{case.module}.{case.function}'
    namespace, _, name = target_name.rpartition('.')
    target = visitor.get_node(namespace, name)
    if not target.defined:
      raise ValueError(f'Pyan did not find {target_name}')

    pending = [target]
    reachable = set()
    while pending:
      node = pending.pop()
      if node in reachable:
        continue
      reachable.add(node)
      # Definition edges would add every method on a referenced class
      pending.extend(visitor.uses_edges.get(node, ()))

    scope: dict[Path, set[str]] = {}
    for node in reachable:
      if not node.defined or node.flavor not in _CALLABLES:
        continue
      key = function_key(node)
      if key is None or not key[0].is_relative_to(root):
        continue
      path, qualname = key
      scope.setdefault(path, set()).add(qualname)

    target_key = function_key(target)
    if target_key is None:
      raise ValueError(f'Pyan could not locate {target_name}')
    return scope, target_key

  return {case: case_scope(case) for case in dataset.cases}


def _summary(functions: list[dict[str, Any]]) -> dict[str, Any]:
  summary = {
      name: sum(function['summary'][name] for function in functions)
      for name in (
          'covered_lines',
          'num_statements',
          'missing_lines',
          'excluded_lines',
          'num_branches',
          'num_partial_branches',
          'covered_branches',
          'missing_branches',
      )
  }
  covered = summary['covered_lines'] + summary['covered_branches']
  total = summary['num_statements'] + summary['num_branches']
  summary['percent_statements_covered'] = (
      100 * summary['covered_lines'] / summary['num_statements']
      if summary['num_statements'] else None
  )
  summary['percent_branches_covered'] = (
      100 * summary['covered_branches'] / summary['num_branches']
      if summary['num_branches'] else None
  )
  summary['percent_covered'] = 100 * covered / total if total else None
  return summary


def _measure_function(
    tool: Tool,
    dataset: Dataset,
    case: Case,
    output_dir: Path,
    function_scope: FunctionScope,
) -> dict[str, Any]:
  """
  Replay a generated case and return its function coverage report.
  """
  data_file = (output_dir / '.coverage').absolute()
  report_file = (output_dir / 'coverage.json').absolute()
  scope, target_key = function_scope

  coverage = Coverage(
      data_file=str(data_file),
      config_file=False,
      branch=True,
  )
  coverage.erase()
  coverage.start()
  try:
    tool.replay(dataset, case, output_dir)
  finally:
    coverage.stop()
    coverage.save()

  # Score the static dataset-function closure shared by every tool
  coverage.json_report(
      morfs=[str(path) for path in scope],
      outfile=str(report_file),
  )

  report = json.loads(report_file.read_text(encoding='utf-8'))
  files = {
      Path(name).resolve(): file_report
      for name, file_report in report['files'].items()
  }
  functions = {
      f'{path.relative_to(dataset.root)}:{name}': files[path]['functions'][name]
      for path, names in scope.items()
      for name in sorted(names)
  }
  return {
      'target_executed': (
          functions[
              f'{target_key[0].relative_to(dataset.root)}:{target_key[1]}'
          ]['summary']['covered_lines'] > 0
      ),
      'summary': _summary(list(functions.values())),
      'functions': functions,
  }


def _replay_worker(
    tool: Tool,
    dataset: Dataset,
    case: Case,
    output_dir: Path,
    function_scope: FunctionScope,
    connection,
) -> None:
  """
  Measure one replay in an isolated process.
  """
  output_dir.mkdir(parents=True, exist_ok=True)
  with (output_dir / 'replay.log').open(
      'w', encoding='utf-8', buffering=1) as log:
    with redirect_stdout(log), redirect_stderr(log):
      old_path = sys.path[:]
      try:
        os.chdir(dataset.root)
        sys.path.insert(0, str(dataset.root))
        report = _measure_function(
            tool, dataset, case, output_dir, function_scope)
        if report.pop('target_executed'):
          result = {'replay': 'completed', **report}
        else:
          result = {
              'replay': 'not_run',
              'replay_error': 'target was not executed',
          }
      except MissingArtifactError as error:
        result = {
            'replay': 'not_run',
            'replay_error': f'{type(error).__name__}: {error}',
        }
      except BaseException as error:
        traceback.print_exc()
        result = {
            'replay': 'error',
            'replay_error': f'{type(error).__name__}: {error}',
        }
      finally:
        sys.path[:] = old_path

  try:
    connection.send(result)
  finally:
    connection.close()


def measure_function(
    tool: Tool,
    dataset: Dataset,
    case: Case,
    output_dir: Path,
    function_scope: FunctionScope,
    timeout: int,
) -> dict[str, Any]:
  """
  Replay and measure a generated case with a wall-clock timeout.
  """
  context = multiprocessing.get_context('spawn')
  receiver, sender = context.Pipe(duplex=False)
  process = context.Process(
      target=_replay_worker,
      args=(tool, dataset, case, output_dir, function_scope, sender),
  )

  process.start()
  sender.close()
  timed_out = False
  try:
    if receiver.poll(timeout):
      try:
        result = receiver.recv()
      except EOFError:
        result = None
    else:
      timed_out = True
      result = {
          'replay': 'timed_out',
          'replay_error': f'replay timed out after {timeout} seconds',
      }
  finally:
    if not timed_out:
      process.join(1)
    if process.is_alive():
      process.terminate()
      process.join(1)
    if process.is_alive():
      process.kill()
      process.join(1)
    receiver.close()

  if timed_out:
    with (output_dir / 'replay.log').open('a', encoding='utf-8') as log:
      log.write(f'replay timed out after {timeout} seconds\n')
  if result is None:
    result = {
        'replay': 'error',
        'replay_error': f'replay worker exited with status {process.exitcode}',
    }
  return result
