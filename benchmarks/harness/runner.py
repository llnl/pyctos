import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from typing import Any

from .cases import Case, Dataset
from .measure import FunctionScope, measure_function
from .tools import Tool


def run_tool(
    dataset: Dataset,
    scopes: dict[Case, FunctionScope],
    tool_name: str,
    tool: Tool,
    output_dir: Path,
    timeout: int,
) -> Path:
  """
  Generate and measure every case in a given dataset with a specific tool.
  Returns a path to a coverage report JSON file.
  """
  report_dir = output_dir / dataset.name / tool_name
  shutil.rmtree(report_dir, ignore_errors=True)
  report_dir.mkdir(parents=True, exist_ok=True)
  report = report_dir / 'coverage.json'
  reports: dict[str, dict[str, Any]] = {}
  report_data = {
      'dataset': dataset.name,
      'tool': tool_name,
      'cases': reports,
  }

  def save_report() -> None:
    report.write_text(
        json.dumps(report_data, indent=2) + '\n',
        encoding='utf-8',
    )

  save_report()
  for case in dataset.cases:
    case_name = f'{case.module}:{case.function}'
    case_dir = report_dir.joinpath(
        *case.module.split('.'),
        case.function,
    ).absolute()
    case_dir.mkdir(parents=True, exist_ok=True)
    case_report = {
        'generation': 'not_run',
        'replay': 'not_run',
    }
    reports[case_name] = case_report

    try:
      tool.generate(dataset, case, case_dir, timeout)
    except subprocess.TimeoutExpired as error:
      case_report['generation'] = 'timed_out'
      case_report['generation_error'] = f'{type(error).__name__}: {error}'
      generation_traceback = traceback.format_exc()
    except Exception as error:
      case_report['generation'] = 'error'
      case_report['generation_error'] = f'{type(error).__name__}: {error}'
      generation_traceback = traceback.format_exc()
    else:
      case_report['generation'] = 'completed'

    if 'generation_error' in case_report:
      with (case_dir / 'generation.log').open('a', encoding='utf-8') as log:
        log.write('\n' + generation_traceback)

    # Failed generators may still leave partial inputs worth measuring
    try:
      case_report.update(measure_function(
          tool=tool,
          dataset=dataset,
          case=case,
          output_dir=case_dir,
          function_scope=scopes[case],
          timeout=timeout,
      ))
    except Exception as error:
      case_report['replay'] = 'error'
      case_report['replay_error'] = f'{type(error).__name__}: {error}'

    statuses = [
        f'{phase} {case_report[phase]}'
        for phase in ('generation', 'replay')
        if case_report[phase] != 'completed'
    ]
    if statuses:
      print(
          f'{tool_name} {case_name}: {", ".join(statuses)}; see {case_dir}',
          file=sys.stderr,
      )
    save_report()

  return report
