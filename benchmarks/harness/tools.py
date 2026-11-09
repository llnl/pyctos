# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from abc import ABC, abstractmethod
import ast
from dataclasses import dataclass
import inspect
import os
from pathlib import Path
import pickle
import shutil
import signal
import subprocess
from tempfile import TemporaryFile
from typing import ClassVar, TYPE_CHECKING

if TYPE_CHECKING:
  from .cases import Case, Dataset


# Grace period to keep finalization within the exploration time limit
_FINALIZATION_GRACE_SECONDS = 5


class MissingArtifactError(Exception):
  pass


@dataclass(frozen=True)
class Tool(ABC):
  venv: Path

  @property
  def python(self) -> Path:
    return self.venv / 'bin' / 'python'

  def _run(
      self,
      command: tuple[str, ...],
      cwd: Path,
      output_dir: Path,
      timeout: float | None,
      check: bool = True,
  ) -> subprocess.CompletedProcess[str]:
    """
    Run an exploration/generation command and save its output.
    """
    with TemporaryFile(mode='w+', encoding='utf-8') as stdout_file, \
        TemporaryFile(mode='w+', encoding='utf-8') as stderr_file:
      process = subprocess.Popen(
          command,
          cwd=cwd,
          stdout=stdout_file,
          stderr=stderr_file,
          text=True,
          start_new_session=True,
      )
      try:
        process.wait(timeout=timeout)
      except subprocess.TimeoutExpired as error:
        self._stop_process_group(process)
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read()
        stderr = stderr_file.read()
        self._save_generation_log(output_dir, stdout, stderr, timeout)

        # Save whatever inputs were generated before failure
        error.output = stdout.encode()
        error.stderr = stderr.encode()
        raise

      stdout_file.seek(0)
      stderr_file.seek(0)
      stdout = stdout_file.read()
      stderr = stderr_file.read()

    result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    self._save_generation_log(output_dir, stdout, stderr)
    if check:
      result.check_returncode()
    return result

  @staticmethod
  def _stop_process_group(process: subprocess.Popen[str]) -> None:
    for shutdown_signal in (signal.SIGTERM, signal.SIGKILL):
      try:
        os.killpg(process.pid, shutdown_signal)
      except ProcessLookupError:
        pass
      try:
        process.wait(timeout=1)
      except subprocess.TimeoutExpired:
        pass

  @staticmethod
  def _save_generation_log(
      output_dir: Path,
      stdout: str,
      stderr: str,
      timeout: float | None = None,
  ) -> None:
    output = stdout
    if stderr:
      output += ('\n' if output and not output.endswith('\n') else '')
      output += stderr
    if timeout is not None:
      output += ('\n' if output and not output.endswith('\n') else '')
      output += f'timed out after {timeout} seconds\n'
    (output_dir / 'generation.log').write_text(output, encoding='utf-8')

  @abstractmethod
  def generate(
      self,
      dataset: Dataset,
      case: Case,
      output_dir: Path,
      timeout: int,
  ) -> None:
    """
    Run exploration and save generated inputs for a single case.
    """
    raise NotImplementedError

  @abstractmethod
  def replay(
      self,
      dataset: Dataset,
      case: Case,
      output_dir: Path,
  ) -> None:
    """
    Replay this tool's generated inputs for one case.
    """
    raise NotImplementedError


class KeywordInputTool(Tool):
  """
  Tool that saves to and replays from dumped kwarg dictionaries.
  """

  inputs_path: ClassVar[Path]

  def replay(
      self,
      dataset: Dataset,
      case: Case,
      output_dir: Path,
  ) -> None:
    inputs_file = output_dir / self.inputs_path
    if not inputs_file.is_file():
      raise MissingArtifactError(inputs_file)
    function = dataset.load_target(case)
    with inputs_file.open('rb') as file:
      inputs = pickle.load(file)

    for arguments in inputs:
      try:
        function(**arguments)
      except KeyboardInterrupt:
        raise
      except BaseException:
        # Target exceptions are covered paths; continue with remaining inputs
        pass


class Pyctos(Tool):
  def generate(
      self,
      dataset: Dataset,
      case: Case,
      output_dir: Path,
      timeout: int,
  ) -> None:
    target = dataset.target_file(case)
    generated_inputs = Path(f'{target}_{case.function}_inputs')
    input_base = output_dir / 'inputs'
    saved_inputs = Path(f'{input_base}_{case.function}_inputs')
    generation_marker = output_dir / 'generated.ok'
    shutil.rmtree(generated_inputs, ignore_errors=True)
    shutil.rmtree(saved_inputs, ignore_errors=True)
    generation_marker.unlink(missing_ok=True)

    try:
      self._run(
          (
              str(self.venv / 'bin' / 'pyctos'),
              str(target),
              '--function', case.function,
          ),
          dataset.root,
          output_dir,
          timeout,
      )
      # Distinguish a clean no-input run from failure with no native artifact
      generation_marker.touch()
    finally:
      if generated_inputs.exists():
        shutil.move(generated_inputs, saved_inputs)

  def replay(
      self,
      dataset: Dataset,
      case: Case,
      output_dir: Path,
  ) -> None:
    import builtins
    from functools import partial

    from checker.lib import (
        load_path_function,
        new_open,
        unpickle_arguments,
    )

    function = load_path_function(
        'FUT', str(dataset.target_file(case)), case.function)
    target_module = inspect.getmodule(function)
    assert target_module is not None

    input_base = output_dir / 'inputs'
    input_dir = Path(f'{input_base}_{case.function}_inputs')
    if input_dir.exists():
      replay_inputs = unpickle_arguments(str(input_base), case.function)
    elif (output_dir / 'generated.ok').exists():
      # No input directory is valid only when the target needs no arguments
      inspect.signature(function).bind()
      replay_inputs = [({}, {}, None)]
    else:
      raise MissingArtifactError(input_dir)

    for arguments, globals_, filesystem in replay_inputs:
      for name, value in globals_.items():
        setattr(target_module, name, value)

      old_cwd = os.getcwd()
      old_open = builtins.open
      try:
        if filesystem is not None:
          os.chdir(filesystem)
          builtins.open = partial(new_open, old_open, old_cwd)
        try:
          function(**arguments)
        except KeyboardInterrupt:
          raise
        except BaseException:
          pass
      finally:
        builtins.open = old_open
        os.chdir(old_cwd)


class CrossHair(KeywordInputTool):
  inputs_path = Path('inputs.pkl')

  def generate(
      self,
      dataset: Dataset,
      case: Case,
      output_dir: Path,
      timeout: int,
  ) -> None:
    # Leave a grace period for finalization within the exploration time limit
    search_timeout = max(1, timeout - _FINALIZATION_GRACE_SECONDS)
    result = self._run(
        (
            str(self.python), '-m', 'crosshair', 'cover',
            # Differentiate inputs by symbolic paths, not just concrete instructions
            '--coverage_type=path',
            '--example_output_format=arg_dictionary',
            # Reenable plateau stops so we don't use the full time limit for every case
            '--max_uninteresting_iterations=5',
            # Limit each path's exploration time to avoid spending the whole budget on one branch
            # '--per_path_timeout=5',
            f'--per_condition_timeout={search_timeout}',
            f'{case.module}.{case.function}',
        ),
        dataset.root,
        output_dir,
        timeout,
        check=False,
    )
    with (output_dir / self.inputs_path).open('wb') as file:
      pickle.dump([
          eval(line, {'__builtins__': {}, 'float': float})
          for line in result.stdout.splitlines()
      ], file)
    result.check_returncode()


@dataclass(frozen=True)
class PyCT(KeywordInputTool):
  inputs_path = Path('generated/inputs.pkl')
  script: Path

  def generate(
      self,
      dataset: Dataset,
      case: Case,
      output_dir: Path,
      timeout: int,
  ) -> None:
    stats_dir = (
        self.script.parent / 'project_statistics' / dataset.root.name
        / case.module / case.function
    )
    saved_stats = output_dir / 'generated'

    # Leave a grace period for finalization within the exploration time limit
    search_timeout = max(1, timeout - _FINALIZATION_GRACE_SECONDS)
    shutil.rmtree(stats_dir, ignore_errors=True)
    shutil.rmtree(saved_stats, ignore_errors=True)
    try:
      self._run(
          (
              str(self.python), str(self.script),
              case.module, '{}',
              '--root', str(dataset.root),
              '--func', case.function,
              '--total_timeout', str(search_timeout),
              # Keep explored inputs
              '--dump_projstats',
          ),
          dataset.root,
          output_dir,
          timeout,
      )
    finally:
      if stats_dir.exists():
        shutil.move(stats_dir, saved_stats)

    if not saved_stats.exists():
      raise FileNotFoundError(stats_dir)


@dataclass(frozen=True)
class PyExZ3(KeywordInputTool):
  inputs_path = Path('inputs.pkl')
  script: Path

  def generate(
      self,
      dataset: Dataset,
      case: Case,
      output_dir: Path,
      timeout: int,
  ) -> None:
    inputs_file = output_dir / 'inputs.pkl'
    inputs_file.unlink(missing_ok=True)
    command = (
        # Flush each input so a timeout does not lose buffered results
        str(self.python), '-u', str(self.script),
        # FIXME: use cvc4, but install it (and bindings) first
        '--start', case.function,
        str(dataset.target_file(case)),
    )
    try:
      result = self._run(
          command,
          dataset.root,
          output_dir,
          timeout,
          check=False,
      )
    except subprocess.TimeoutExpired as error:
      partial_output = error.stdout
      if isinstance(partial_output, bytes):
        stdout = partial_output.decode(errors='replace')
      else:
        stdout = partial_output or ''
      self._save_inputs(inputs_file, stdout)
      raise

    self._save_inputs(inputs_file, result.stdout)
    result.check_returncode()

  @staticmethod
  def _save_inputs(inputs_file: Path, stdout: str) -> None:
    """
    Normalize PyExZ3's printed inputs into kwarg objects for replay.
    """
    inputs = []
    for line in stdout.splitlines():
      try:
        value = ast.literal_eval(line)
      except (SyntaxError, ValueError):
        continue
      if isinstance(value, list) and all(
          isinstance(item, tuple)
          and len(item) == 2
          and isinstance(item[0], str)
          for item in value
      ):
        inputs.append(dict(value))

    with inputs_file.open('wb') as file:
      pickle.dump(inputs, file)


_BENCHMARKS = Path(__file__).resolve().parents[1]
_PYTHON_311 = _BENCHMARKS / 'venvs' / 'venv-py3.11'
_PYTHON_38 = _BENCHMARKS / 'venvs' / 'venv-py3.8'
_TOOLS = _BENCHMARKS / 'tools'

TOOLS: dict[str, Tool] = {
    'pyctos': Pyctos(_PYTHON_311),
    'crosshair': CrossHair(_PYTHON_311),
    'pyct': PyCT(_PYTHON_38, _TOOLS / 'PyCT' / 'pyct.py'),
    'pyexz3': PyExZ3(_PYTHON_38, _TOOLS / 'PyExZ3' / 'pyexz3.py'),
}
