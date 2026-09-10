# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import dataclasses
import logging
import traceback
from dataclasses import dataclass
from copy import deepcopy
from typing import List, Tuple, Dict, Any, ClassVar
from inspect import Signature, BoundArguments, Parameter

from symbex.runtime import PyctosAssertionError
import symbex.symbolic.factories as factories
from symbex.types.symbolicvalue import SymbolicValue, Formula, makeSymbolicValue
from symbex.engine.globalvar import GlobalVar, gather_globals
from symbex.yaml import *
from symbex.engine.util import *

from symbex.smtlib import get_smt_lib
smt = get_smt_lib()

logger = logging.getLogger(__name__)


class StopSearching(Exception):
  def __init__(self, *args):
    super().__init__(*args)

# Psuedo code for overall algorithm:

# Unexplored inputs = {(\vec{v} = 0, True) | v is a parameter or global variable of the FUT}
# While there are Unexplored inputs:
#    Starting input, Current branch condition <- next unexplored input.
#    Execute the program with new starting input.
#    Foreach branch b encountered in the program:
#       if not b /\ current branch condition is SAT:
#          Add the SAT model, (not b /\ current branch condition) to Unexplored inputs.
#       Current branch condition /\= b.


@dataclass(frozen=True)
class ConcolicFrame:
  """
  Represents all of the information necessary to do a concolic run of a function.
  """
  path_condition: SymbolicValue
  function_arguments: BoundArguments
  global_variables: Dict[GlobalVar, SymbolicValue]
  # (file name, SMT file variable) -> file contents
  filesystem_variables: Dict[Tuple[str, str], str]


@dataclass
class ConcolicEngine:
  params: Signature
  unexplored_inputs: List[ConcolicFrame] = dataclasses.field(
    default_factory=list)
  path_condition: SymbolicValue = dataclasses.field(default_factory=lambda: factories.lift_value(
    True))
  axioms: SymbolicValue = dataclasses.field(default_factory=lambda: factories.lift_value(
    True))

  varmap: Dict[Parameter, Formula] = dataclasses.field(
    default_factory=dict)
  globmap: Dict[GlobalVar, Formula] = dataclasses.field(
    default_factory=dict)
  filemap: Dict[Tuple[str, str], Formula] = dataclasses.field(  # (file name, SMT file variable) -> formula
    default_factory=dict)

  file_concs: Dict[Tuple[str, str], str] = dataclasses.field(
    default_factory=dict)  # (file name, SMT file variable) -> file contents

  execution_depth: int = 0
  hit_max_depth: bool = False
  max_depth: int = 64
  timeout: int = 5000
  features: ClassVar[List[YamlFeature]] = []

  @staticmethod
  def set_max_execution_depth(depth: int) -> None:
    """
    Set maximum execution depth for concolic execution.
    """
    ConcolicEngine.max_depth = depth

  @staticmethod
  def max_execution_depth() -> int:
    """
    Maximum execution depth for concolic execution.
    Default=`64`
    """
    return ConcolicEngine.max_depth

  @staticmethod
  def set_timeout(timeout: int) -> None:
    """
    Set the SMT solver timeout.
    """
    ConcolicEngine.timeout = timeout

  @staticmethod
  def set_yaml(features: List[YamlFeature]) -> None:
    """
    Set features from parsed YAML to search for.
    """
    ConcolicEngine.features = features

  @staticmethod
  def get_timeout() -> int:
    """
    Timeout for SMT solver.
    Default=`5000`
    """
    return ConcolicEngine.timeout

  @staticmethod
  def max_fuzzing_attempts() -> int:
    """
    Maximum attempts for the fuzzer to perform.
    Default=`100`
    """
    return 100

  @staticmethod
  def max_fuzzing_nesting() -> int:
    """
    Maximum nesting for fuzzing objects (e.g., an object containing a list containing an integer).
    Default=`4`
    """
    return 4

  def setup_unexplored_inputs(self, app, origin) -> None:
    """
    Prepares the first iteration of unexplored inputs at the beginning of a concolic execution run.

    Includes global variables and function parameters.
    """
    self.varmap.clear()
    self.filemap.clear()
    self.file_concs.clear()
    for x in self.params.parameters:
      param = self.params.parameters[x]
      self.varmap[param] = factories.make_var(x)

    for glob_var in gather_globals(app, origin):
      nme = glob_var.name
      self.globmap[glob_var] = factories.make_var(nme)

    self.unexplored_inputs = [ConcolicFrame(
      self.path_condition,
      self.params.bind(*[factories.make_default_symbolic_var(x)
                         for x, p in self.params.parameters.items()]),
      {key: factories.make_symbolic_var(key.get(), key.name)
       for key in self.globmap.keys()},
      {}
    )]

  def make_assertion(self, v: SymbolicValue, skip_max_depth: bool = True) -> None:
    """
    Make an assertion to the path condition.
    Assertions are different from path conditions in that their negation is never attempted.
    """
    if not skip_max_depth:
      self.execution_depth += 1
      if self.execution_depth > self.max_execution_depth():
        self.hit_max_depth = True
        raise ExecutionDepthExceeded

    valu = v.to_sbool()

    self.path_condition = self.path_condition._and(valu)

  def add_axiom(self, v: SymbolicValue, skip_max_depth: bool = True) -> None:
    """
    Make an assertion to the path condition.
    Assertions are different from path conditions in that their negation is never attempted.
    """
    if not skip_max_depth:
      self.execution_depth += 1
      if self.execution_depth > self.max_execution_depth():
        self.hit_max_depth = True
        raise ExecutionDepthExceeded

    valu = v.to_sbool()

    self.axioms = self.axioms._and(valu)

  def record_path(self, v: Union[SymbolicValue, bool]) -> None:
    """
    Record a new path to the path condition.
    The negation is taken and is solved for by the SMT solver.
    If `SAT` is returned, the SMT model is converted into concrete python objects and added to the list of unexplored inputs.
    """
    if isinstance(v, bool):
      return

    self.execution_depth += 1
    if self.execution_depth > self.max_execution_depth():
      self.hit_max_depth = True
      raise ExecutionDepthExceeded

    valu = get_path_condition_append(v)

    other_path: SymbolicValue = self.path_condition._and(valu._not())
    self.path_condition = self.path_condition._and(valu)

    solver = Solver_(ConcolicEngine.timeout)

    solver.add(other_path.get_formula(), self.axioms.get_formula())

    logger.debug(solver.sexpr())
    logger.debug("Symbolic Value: %s", valu._not().get_formula().sexpr())

    result = solver.check()

    logger.debug(result)
    if result == smt.unknown:
      logger.debug("unknown reason:", solver.reason_unknown())

    if result == smt.sat:
      new_params: Dict[str, SymbolicValue] = {}
      model = solver.model()

      logger.debug("model: %s", model)

      for param, formula in self.varmap.items():
        evaluated = model.evaluate(formula)

        logger.debug("evaluated: %s", evaluated)

        if smt.eq(evaluated, formula):
          # if this variable wasn't used anywhere in the path condition
          new_params[param.name] = factories.make_default_symbolic_var(
            param.name)
        else:
          # if Z3 assigns a value to this variable
          newv = convert_model(evaluated, model)

          new_params[param.name] = factories.make_symbolic_var(
            newv, param.name)
          logger.debug(f"newv: {repr(newv)}")

      new_globals: Dict[GlobalVar, SymbolicValue] = {}

      for glob_param, formula in self.globmap.items():
        newv = convert_model(
          model.evaluate(formula), model)
        new_globals[glob_param] = factories.make_symbolic_var(
           newv, glob_param.name)

      new_files: Dict[Tuple[str, str], str] = {}

      for file_name, formula in self.filemap.items():
        newv = convert_model(
          model.evaluate(formula), model)
        new_files[file_name] = newv

      self.unexplored_inputs.append(
        ConcolicFrame(other_path, self.params.bind(**new_params), new_globals, new_files))

      reset_references()

  def prove(self, v: SymbolicValue) -> bool:
    """
    Returns whether the expression can be proven true against the current path
    condition and axioms.
    """
    valu = v.to_sbool()
    if not valu.get_value():
      return False

    # Initialize solver with the path condition and axioms
    solver = Solver_(ConcolicEngine.timeout)
    solver.add(self.path_condition.get_formula(), self.axioms.get_formula())

    # Negate the theorem to prove and attempt a proof BWOC
    solver.add(valu._not().get_formula())
    return solver.check() == smt.unsat

  @staticmethod
  def add_to_explored_inputs(explored_inputs: List[TraceResult], input: TraceResult) -> None:
    for explored_input in explored_inputs:
      barguments = explored_input.input_args
      bglobals = explored_input.global_vars
      bfiles = explored_input.file_vars

      farguments = [bargument.v for bargument in barguments.args]
      fglobals = [(key.name, value.v) for key, value in sorted(
        bglobals.items(), key=lambda x: x[0].name)]
      ffiles = [(key[0], value)
                for key, value in sorted(bfiles.items(), key=lambda x: x[0][0])]

      fcomp = farguments + fglobals + ffiles

      ibarguments = input.input_args
      ibglobals = input.global_vars
      ibfiles = input.file_vars

      ifarguments = [ibargument.v for ibargument in ibarguments.args]
      ifglobals = [(key.name, value.v) for key, value in sorted(
        ibglobals.items(), key=lambda x: x[0].name)]
      iffiles = [(key[0], value) for key, value in sorted(
        ibfiles.items(), key=lambda x: x[0][0])]

      ifcomp = ifarguments + ifglobals + iffiles

      if are_same_concrete_object(fcomp, ifcomp):
        raise DuplicateInputConfiguration

    explored_inputs.append(input)

  def explore(self, app, origin) -> Tuple[List[TraceResult], Optional[TraceResult]]:
    """
    Perform a run of concolic execution on a program. Returns a list of trace results, i.e.,
    a list of different assignments to variables to maximally cover encountered branches.
    """
    try:
      self.setup_unexplored_inputs(app, origin)
    except TypeError:
      logger.debug(traceback.format_exc())

    explored_inputs: List[TraceResult] = []
    yaml_input: Optional[TraceResult] = None

    for axiom in util.get_axioms():
      self.add_axiom(makeSymbolicValue(
        v=True, formula=axiom), skip_max_depth=True)

    # We terminate the loop if one of two conditions are hit:
    # 1. We have run out of unexplored inputs of Z3. There still may yet be untaken branches,
    #    but they are unsolvable by Z3, probably due to an indirect data dependency. If there
    #    are more untaken branches, we fall back to fuzzing to try to catch them.
    # 2. We have explored the function at least once and we have no remaining untaken branches.
    #    We ensure that we execute the function at least once, because branches are only registered
    #    after being hit. We need to see at least one branch during the first run anyway for Z3 to
    #    have anything to work with, so we bet on the fact that we'll see at least one branch on the
    #    first execution, which allows "untaken_branches()" to produce a real result. It's nice to
    #    exit early here, because certain loops spin up infinite path conditions, so there are
    #    perpetual unexplored inputs, even though we may have already hit every branch.
    # while len(self.unexplored_inputs) > 0 and not (len(explored_inputs) > 0 and len(untaken_branches()) == 0):

    # There is actually the case that a symbolic list is iterated over (see examples/list.py:iter_list)
    # In this case, no explicit branches are hit, so the number of untaken branches after the first run
    # remains 0, but we have generated a legal unexplored input that should be checked.
    while len(self.unexplored_inputs) > 0:
      logger.debug("Unexplored: %s", len(self.unexplored_inputs))

      concolic_frame = self.unexplored_inputs.pop()
      self.path_condition = concolic_frame.path_condition
      self.file_concs = concolic_frame.filesystem_variables
      self.execution_depth = 0

      next_input = concolic_frame.function_arguments
      next_globals = concolic_frame.global_variables
      next_files = concolic_frame.filesystem_variables

      logger.debug("Exploring: %s", str(next_input))

      try:
        for g, val in next_globals.items():
          g.put(val)
        for feature in self.features:
          feature.reset()

        # A deep copy of the input is made, because the program might mutate the input before we can
        # show it to the user
        next_input_copy = deepcopy(next_input)

        result = TraceResult(input_args=next_input_copy,
                             global_vars=next_globals,
                             file_vars=next_files,
                             path_condition=self.path_condition)

        ConcolicEngine.add_to_explored_inputs(explored_inputs, result)
        app(*next_input.args, **next_input.kwargs)

      except ExecutionDepthExceeded:
        self.execution_depth = 0
        continue

      except DuplicateInputConfiguration:
        logger.debug("Found duplicate input!")
        self.execution_depth = 0
        continue

      except StopSearching:
        logger.debug("Instructed to stop searching!")
        yaml_input = explored_inputs[-1]
        break

      except PyctosAssertionError:
        # If a pyctos_assert failed, re-raise so this test fails
        raise

      except KeyboardInterrupt:
        raise

      except:
        # TODO: track and report?
        logger.debug(traceback.format_exc())
        continue

    return explored_inputs, yaml_input

  def fuzz(self, app) -> List[TraceResult]:
    """
    Perform a run of fuzzing on a program. Returns a list of trace results, i.e.,
    a list of different assignments to variables to maximally cover encountered branches.
    """
    explored_inputs: List[TraceResult] = []
    missing_branches = untaken_branches()
    counter = 0

    while len(missing_branches) > 0 and counter < ConcolicEngine.max_fuzzing_attempts():
      parameters: List[Any] = []

      for param in self.params.parameters.values():
        parameters.append(generate_arbitrary(self.max_fuzzing_nesting()))

      args = self.params.bind(*parameters)

      try:
        r = app(*args.args, **args.kwargs)

      except Exception:
        logger.debug(traceback.format_exc())
        counter += 1
        continue

      new_missing_branches = untaken_branches()

      for pair in missing_branches:
        if not pair in new_missing_branches:
          explored_inputs.append(TraceResult(
            args, {}, {}, None))
          missing_branches = new_missing_branches

      counter += 1

    return explored_inputs
