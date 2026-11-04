# Pyctos benchmarking

This directory contains a test harness for running a couple of input discovery tools on a set of functions:

- Pyctos (this repository)
- CrossHair cover
- PyCT
- PyExZ3

Generation runs in a venv specific to the tool (one shared env for Pyctos and CrossHair, one for PyCT and PyExZ3). Replay/coverage run in the same interpreter (whichever one runs `benchmarks/main.py`).

## Python environments

We use three different virtual environments for benchmarking:
- `pyctos-venv` (Python 3.11.11) runs replay and coverage through the main script
- `benchmarks/venvs/venv-py3.11` (Python 3.11.11) runs generation for Pyctos and Crosshair
- `benchmarks/venvs/venv-py3.8` (Python 3.8.19) runs generation for PyCT and PyExZ3.

Create the tool-specific environments:

```sh
python3.11 -m venv pyctos-venv  # (if Pyctos is not already installed)
python3.11 -m venv benchmarks/venvs/venv-py3.11
python3.8 -m venv benchmarks/venvs/venv-py3.8
```

## Tools

### Pyctos

#### Installation

Pyctos requires Python 3.11 through 3.13. Install the repository itself in editable mode into the Python 3.11 generator environment:

```sh
benchmarks/venvs/venv-py3.11/bin/python -m pip install -e .
```

The interpreter used to run the harness also needs Pyctos installed because it imports the `checker` module directly. This should probably be changed. It also needs Pyan for collecting function scopes from the call graph:

```sh
pyctos-venv/bin/python -m pip install -e . pyan3==2.9.0
```

### CrossHair

#### Installation

We run CrossHair cover under Python 3.11:

```sh
benchmarks/venvs/venv-py3.11/bin/python -m pip install \
  -e benchmarks/tools/CrossHair
```

#### Patches

By default, CrossHair allocates new branches the entire time budget, but the amount of time we allot for generation is the limit for how much time the tool can take overall. We patch `explore_loop()` in `crosshair/core.py` to cap the allocated time for a new branch with the amount of time left for the entire run:

`benchmarks/tools/CrossHair/crosshair/core.py`:

```diff
def explore_loop(...):
    condition_start = process_time()
+   condition_deadline = condition_start + options.per_condition_timeout
    ...

-   if itr_start > condition_start + options.per_condition_timeout:
+   if itr_start >= condition_deadline:
        ...

-   per_path_timeout = options.get_per_path_timeout()
+   per_path_timeout = min(
+       options.get_per_path_timeout(),
+       condition_deadline - itr_start,
+   )
    ...
```

### PyCT

#### Installation

PyCT runs under Python 3.8. The project is not structured as a modern Python package so we need to do some setup to install it as one, namely adding `benchmarks/tools/PyCT/pyproject.toml` (described in patches below).

After creating this file, install the package as editable:

```sh
benchmarks/venvs/venv-py3.8/bin/python -m pip install -e benchmarks/tools/PyCT
```

PyCT also requires there to exist a CVC4 1.8 executable addressable as `cvc4`. You can just put this executable on PATH; PyCT doesn't use Python bindings for it.

#### Patches

##### Add setuptools metadata

Add a setuptools `pyproject.toml` packaging `pyct.py` and `libct` as well as PyCT's runtime dependencies:

New file: `benchmarks/tools/PyCT/pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=64"]
build-backend = "setuptools.build_meta"

[project]
name = "pyct"
version = "0.0.0"
requires-python = ">=3.8"
dependencies = ["coverage==4.5.4", "func-timeout"]

[tool.setuptools]
py-modules = ["pyct"]

[tool.setuptools.packages.find]
include = ["libct*"]
```

This allows for the installation described above.

##### Force `fork` multiprocessing context

This is system-dependent, but was required to run PyCT on my Mac: patch PyCT to create the worker processes with `multiprocessing.get_context("fork").Process(...)`. PyCT's implementation assumes this context, but Python 3.8 on MacOS defaults to `spawn` instead and pickling fails.

`benchmarks/tools/PyCT/libct/explore.py`:

```diff
def _one_execution_concolic(...):
    ...
-   process = multiprocessing.Process(target=child_process); process.start()
+   process = multiprocessing.get_context("fork").Process(target=child_process); process.start()

...

def _one_execution_primitive(...):
    ...
-   process = multiprocessing.Process(target=child_process); process.start()
+   process = multiprocessing.get_context("fork").Process(target=child_process); process.start()
```

##### Use SMT-LIB 2.0

Change CVC4's language argument in `libct/solver.py`:

```diff
if solver == "cvc4":
    ...
-   cls.cmd = ["cvc4"] + ["--produce-models", "--lang", "smt", "--quiet", "--strings-exp"]
+   cls.cmd = ["cvc4"] + ["--produce-models", "--lang", "smt2.0", "--quiet", "--strings-exp"]
```

PyCT generates some formulas that are only accepted by CVC4 1.8 under SMT-LIB 2.0; I'm not sure why this is set to the legacy version explicitly.

### PyExZ3

#### Installation

PyExZ3 runs under Python 3.8. It's also not structured as a Python module, but the harness just runs `pyexz3.py` directly. We should probably add a `pyproject.toml` eventually akin to PyCT.

For now, just install the required Z3 bindings into the Python 3.8 environment:

```sh
benchmarks/venvs/venv-py3.8/bin/python -m pip install z3-solver==5.1.0.0
```

#### Patches

##### Use Python 3 arg spec

Replace `inspect.getargspec()` with `inspect.getfullargspec()` in
`symbolic/loader.py`.

##### Seed symbolic inputs from annotation types

PyExZ3 allows seeding arguments with its `@symbolic_args` decorator rather than deriving types from parameter annotations. For parameters whose seed isn't specific in that decorator, inspect the annotation and if it's a supported type (`int` or `str`) then seed it with the respective symbolic type (`getSymbolic(seed)`):

`benchmarks/tools/PyExZ3/symbolic/loader.py`:

```diff
def createInvocation(self):
    ...
-   argspec = inspect.getargspec(func)
+   argspec = inspect.getfullargspec(func)
    ...

    for a in argspec.args:
        if not a in inv.getNames():
-           Loader._initializeArgumentSymbolic(inv, a, 0, SymbolicInteger)
+           annotation = argspec.annotations.get(a, int)
+           seed = annotation() if annotation in (int, str) else 0
+           Loader._initializeArgumentSymbolic(inv, a, seed, getSymbolic(seed))
```

##### NOT APPLIED: Use CVC4 for string support

PyExZ3 supports ints and strings, but string reasoning only works with the CVC4 backend. We should install compatible cvc4 bindings and add `--cvc` to the harness command to support cases with string parameters.

```diff
class PyExZ3(KeywordInputTool):
    ...
    command = (
        str(self.python), '-u', str(self.script),
+       '--cvc',
        '--start', case.function,
        ...
    )
```
