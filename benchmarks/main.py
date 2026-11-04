from argparse import ArgumentParser
import json
from pathlib import Path
import shutil
import sys

from harness import TOOLS, build_scopes, load_datasets, run_tool


data_spec_path = Path(__file__).with_name('benchmarks.toml')
datasets = load_datasets(data_spec_path)


def main() -> None:
  parser = ArgumentParser()
  parser.add_argument(
      'dataset',
      choices=datasets,
      help='dataset to benchmark',
  )
  tool_group = parser.add_mutually_exclusive_group()
  tool_group.add_argument(
      '-t', '--tool',
      dest='tool_names',
      action='append',
      choices=TOOLS,
      help='tools to benchmark'
  )
  tool_group.add_argument(
      '-a', '--all',
      action='store_true',
      help='benchmark all tools',
  )
  parser.add_argument(
      '-o', '--output',
      type=Path,
      default='coverage',
      help='coverage report output directory',
  )
  parser.add_argument(
      '--timeout',
      type=int,
      default=60,
      help='generation and replay timeout per case',
  )

  args = parser.parse_args()
  if args.timeout <= 0:
    parser.error('--timeout must be positive')
  dataset = datasets[args.dataset]
  tool_names = TOOLS if args.all or args.tool_names is None else args.tool_names
  dataset_output = args.output / dataset.name
  if dataset.root.is_relative_to(dataset_output.resolve()):
    parser.error('--output must not contain the dataset source directory')
  scopes = build_scopes(dataset)
  # Make the combined report an exact snapshot of this run
  shutil.rmtree(dataset_output, ignore_errors=True)
  combined_report = dataset_output / 'coverage.json'
  reports = {}
  combined_report.parent.mkdir(parents=True, exist_ok=True)
  combined_report.write_text('{}\n', encoding='utf-8')

  for name in tool_names:
    try:
      report = run_tool(
          dataset, scopes, name, TOOLS[name], args.output, args.timeout)
      reports[name] = json.loads(
          report.read_text(encoding='utf-8'))['cases']
    except Exception as error:
      reports[name] = {
          'error': f'{type(error).__name__}: {error}',
      }
      print(f'{name}: {error}', file=sys.stderr)

    combined_report.write_text(
        json.dumps(reports, indent=2) + '\n',
        encoding='utf-8',
    )

  print(combined_report)


if __name__ == '__main__':
  main()
