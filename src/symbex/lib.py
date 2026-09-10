# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import inspect
import types
import ast
import sys
import logging
import symbex.symbolic as symbolic
from symbex.astmanip import InterceptStatements, get_all_fields, get_all_classes, classes, module_extensions, object_formatter
from symbex.types.symbolicvalue import makeSymbolicValue
from symbex.globals.globals import set_engine, get_engine
from symbex.symbolic.factories import concretize_args, lift_args, make_var
from symbex.engine.engine import GlobalVar
from symbex.engine.engine import ConcolicEngine
from inspect import BoundArguments, signature
from typing import Optional, Any, Dict, Union, overload, Literal, List, Type, Tuple, TYPE_CHECKING
from types import ModuleType
from dataclasses import dataclass
from collections.abc import Callable
from symbex.overrides import overrides
from symbex.smtlib import get_smt_lib
smt = get_smt_lib()

if TYPE_CHECKING:
  from symbex.engine.util import TraceResult
  from symbex.symbolic.symbolic import Formula

logger = logging.getLogger(__name__)


class UnspecifiedObjectType:
  def __repr__(self) -> str:
    return f"<unspecified object type: __dict__={self.__dict__}>"


def get_class(class_name: str) -> Type[object]:
  if class_name == "object":
    return UnspecifiedObjectType
  else:
    return classes[class_name]


def pretty_args(args: BoundArguments) -> str:
  ret = "["
  for arg in args.args:
    ret += f"{str(arg)},"

  # Remove trailing comma if there was at least one entry
  if len(ret) > 1:
    ret = ret[:-1]
  ret += "]"
  return ret


def import_from_path(module_name: str, file_path: str) -> ModuleType:
  with open(file_path, "r", encoding="utf-8") as f:
    source_code = f.read()

  tree: ast.Module = ast.parse(source_code, filename=file_path)
  tree = InterceptStatements(module_name, file_path).visit(tree)
  symbolic.util.initialize_sorts()

  logger.debug(ast.dump(tree, indent=2))
  all_fields = get_all_fields()
  all_classes = get_all_classes()
  logger.debug(f"All fields: {all_fields}")
  logger.debug(f"All classes: {all_classes}")

  modified_code = compile(tree, filename=file_path, mode="exec")
  module = types.ModuleType(module_name)

  overrides.install_overrides(module)

  for module_name, extensions in module_extensions.items():
    if module_name not in sys.modules:
      sys.modules[module_name] = extensions
    else:
      for key, value in extensions.__dict__.items():
        sys.modules[module_name].__dict__[key] = value

  exec(modified_code, module.__dict__)

  if module_name not in sys.modules:
    sys.modules[module_name] = module
  else:
    for key, value in module.__dict__.items():
      sys.modules[module_name].__dict__[key] = value

  for class_name in all_classes.keys():
    if hasattr(module, class_name):
      classes[class_name] = getattr(module, class_name)
      setattr(classes[class_name], "__repr__", object_formatter)

  return module


def load_module(name: str, path: str) -> ModuleType:
  mod = import_from_path(name, path)
  return mod


def load_path_function(name: str, path: str, func: str) -> Tuple[Callable[..., Any], ModuleType]:
  origin = load_module(name, path)
  ret = origin

  for attr in func.split('.'):
    ret = getattr(ret, attr)

  assert callable(ret)

  return ret, origin


def explore(f, origin) -> Tuple[List["TraceResult"], Optional["TraceResult"], ConcolicEngine]:
  engine = ConcolicEngine(signature(f))
  set_engine(engine)
  return *engine.explore(f, origin), engine


def build_substitution(f, *args, **kwargs) -> Dict["Formula", "Formula"]:
  bargs = signature(f).bind(*args, **kwargs)
  ret = {}

  for f_name, sym_valu in bargs.arguments.items():
    if sym_valu.typ() is int:
      ret[make_var(f_name)] = sym_valu.get_formula()
    else:
      logger.debug("Unhandled function parameter type")
      continue
  return ret


@dataclass
class FunctionSummary:
  ret_expr: "Formula"
  global_exprs: Dict[GlobalVar, "Formula"]


# If infer_model is False, summary is a handwritten FunctionSummary.
# If infer_model is True, summary is a python function for which we should infer the FunctionSummary.
@overload
def wrap_concrete(summary: Callable[..., Any],
                  infer_model: Literal[True]) -> Any: ...


@overload
def wrap_concrete(
  summary: Callable[..., FunctionSummary], infer_model: Literal[False]) -> Any: ...


def wrap_concrete(summary: Callable[..., Union[FunctionSummary, Any]], infer_model: bool = True) -> Any:
  f_model: Callable[[], Union[FunctionSummary, Any]
                    ] = lambda *args, **kwargs: None
  if infer_model:
    pass
    # Commenting this out because it's causing issues in the testing at the moment.
    # TODO: Fix this
    #
    # logger.debug("Done summarizing! Inferred summary:", f_model(*[], **{}))
  else:
    f_model = summary

  def wrap_outer(f):
    def wrapper(*args, **kwargs):
      bound_args = signature(f).bind(*args, **kwargs)
      concr_args = concretize_args(signature(f), bound_args)
      symb_args = lift_args(signature(f), bound_args)

      fun_summary = f_model(*symb_args.args, **symb_args.kwargs)
      assert fun_summary
      form = fun_summary.ret_expr
      if infer_model:
        subst = build_substitution(f, *symb_args.args, **symb_args.kwargs)
        form = smt.substitute(form, subst)
      return makeSymbolicValue(formula=form, v=f(*concr_args.args, **concr_args.kwargs))
    return wrapper

  return wrap_outer


def get_any_types(modules: dict[str, ModuleType]) -> List[Type]:
  types: List[Type] = []

  # Primitive types
  types += [int, float, bool]
  # List types
  # Technically there are an infinite number of list types with infinite nesting, but we do our best here
  types += [List[int], List[float], List[bool]]

  # Class types
  # We iterate through the modules and pull out any classes we find
  for _, obj in inspect.getmembers(modules):
    if inspect.isclass(obj):
      types.append(obj)

  return types


def found_new_paths(old: dict[tuple[int, int], tuple[bool, bool]], new: dict[tuple[int, int], tuple[bool, bool]]) -> bool:
  if len(new) > len(old):
    return True

  for pair in old.keys():
    old_history = old[pair]
    new_history = new[pair]

    if (not old_history[0] and new_history[0]) or (not old_history[1] and new_history[1]):
      return True

  return False
