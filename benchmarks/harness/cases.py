# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from dataclasses import dataclass
import importlib
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class Case:
  """
  Describes a single test case (FUT within some module).
  """
  module: str
  function: str


@dataclass(frozen=True)
class Dataset:
  """
  Describes a set of test cases in some directory.
  """
  name: str
  root: Path
  cases: tuple[Case, ...]

  def target_file(self, case: Case) -> Path:
    return self.root.joinpath(*case.module.split('.')).with_suffix('.py')

  def load_target(self, case: Case):
    """
    Import and resolve a case's possibly qualified function name.
    """
    value = importlib.import_module(case.module)
    for name in case.function.split('.'):
      value = getattr(value, name)
    return value


def load_datasets(path: Path) -> dict[str, Dataset]:
  """
  Loads datasets and associated cases from the toml spec.
  """
  with path.open('rb') as file:
    config = tomllib.load(file)

  datasets: dict[str, Dataset] = {}
  for name, spec in config['datasets'].items():
    cases = tuple(
        Case(*str(target).split(':'))
        for target in spec['targets'])

    datasets[name] = Dataset(
        name=name,
        root=(path.parent / str(spec['root'])).resolve(),
        cases=cases)

  return datasets
