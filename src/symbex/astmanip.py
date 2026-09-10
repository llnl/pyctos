# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from typing import Union, Callable, List, Dict, Tuple, Optional, Type
import symbex.overrides as overrides
import ast
import os
import types
import sys

all_fields: List[str] = []
all_classes: Dict[str, Tuple[List[str], List[str]]] = {}

classes: Dict[str, Type[object]] = {}

module_extensions: Dict[str, types.ModuleType] = {}


def object_formatter(self) -> str:
  return f"{self.__class__.__name__}({self.__dict__})"


def get_all_fields() -> List[str]:
  return all_fields


def get_all_classes() -> Dict[str, Tuple[List[str], List[str]]]:
  """
  Return type is: `Class Name -> Tuple[ List[Class's Methods], List[Superclasses] ]`
  """
  return all_classes


def generate_interception(node: Union[ast.expr, List[ast.expr]], funcname: str) -> ast.expr:
  if isinstance(node, ast.expr):
    lineno = node.lineno
    col_offset = node.col_offset
    args = [node]
  else:
    lineno = node[0].lineno
    col_offset = node[0].col_offset
    args = node
  return ast.Call(
      ast.Name(funcname, lineno=lineno,
               col_offset=col_offset, ctx=ast.Load()),
      [ast.Constant(lineno, lineno=lineno, col_offset=col_offset),
       ast.Constant(col_offset, lineno=lineno,
                    col_offset=col_offset),
       *args], [],
      lineno=lineno, col_offset=col_offset)


def generate_if_interception(node: Union[ast.expr, List[ast.expr]]) -> ast.expr:
  return generate_interception(node, "_symbex_intercept_atomic_if_condition")


def generate_while_interception(node: Union[ast.expr, List[ast.expr]]) -> ast.expr:
  return generate_interception(node, "_symbex_intercept_atomic_while_condition")


def generate_range_interception(node: Union[ast.expr, List[ast.expr]]) -> ast.expr:
  return generate_interception(node, "_symbex_intercept_for_range")


def generate_in_interception(node: ast.Compare) -> ast.expr:
  return ast.Call(ast.Name("_symbex_intercept_in_operator", lineno=node.lineno, col_offset=node.col_offset, ctx=ast.Load()),
                  [node.left, *node.comparators], [],
                  lineno=node.lineno, col_offset=node.col_offset)


def generate_function_call_interception(node: ast.Call) -> ast.Call:
  return ast.Call(ast.Name("_symbex_intercept_function_call", lineno=node.lineno, col_offset=node.col_offset, ctx=ast.Load()),
                  [ast.Constant(node.lineno, lineno=node.lineno, col_offset=node.col_offset),
                   ast.Constant(node.col_offset, lineno=node.lineno,
                                col_offset=node.col_offset),
                   node.func, *node.args], keywords=node.keywords, lineno=node.lineno, col_offset=node.col_offset)


def generate_isinstance_interception(node: ast.Call) -> ast.expr:
  return ast.Call(ast.Name("_symbex_intercept_isinstance_call", lineno=node.lineno, col_offset=node.col_offset, ctx=ast.Load()),
                  node.args, [], lineno=node.lineno, col_offset=node.col_offset)


def is_atom(node: ast.AST) -> bool:
  return not (isinstance(node, ast.BoolOp) or (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not)))


class InterceptAtoms(ast.NodeTransformer):
  def __init__(self, replace_func: Callable[[ast.expr], ast.expr]) -> None:
    self.replace_func = replace_func

  def visit_BoolOp(self, node: ast.BoolOp) -> ast.BoolOp:
    node = super().generic_visit(node)  # type: ignore
    values = node.values
    newvalues: List[ast.expr] = []
    for v in values:
      if is_atom(v):
        newvalues.append(self.replace_func(v))
      else:
        newvalues.append(v)
    return ast.BoolOp(node.op, newvalues, lineno=v.lineno, col_offset=v.col_offset)

  def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.UnaryOp:
    node = super().generic_visit(node)  # type: ignore
    operand = node.operand
    if isinstance(node.op, ast.Not) and is_atom(operand):
      return ast.UnaryOp(node.op, self.replace_func(operand), lineno=operand.lineno, col_offset=operand.col_offset)
    else:
      return node


class InterceptStatements(ast.NodeTransformer):
  is_method_call: bool = False
  class_name: Optional[str] = None
  module_name: str
  file_path: str
  inmodule: str

  def __init__(self, module_name: str, file_path: str, inmodule: str = "") -> None:
    self.module_name = module_name
    self.file_path = file_path
    self.inmodule = inmodule

  def visit_If(self, node: ast.If) -> ast.If:
    node = super().generic_visit(node)  # type: ignore
    if is_atom(node.test):
      newcond = generate_if_interception(node.test)
    else:
      newcond = InterceptAtoms(generate_if_interception).visit(node.test)
    return ast.If(newcond, node.body, node.orelse, lineno=node.lineno, col_offset=node.col_offset)

  def visit_While(self, node: ast.While) -> ast.While:
    node = super().generic_visit(node)  # type: ignore
    if is_atom(node.test):
      newcond = generate_while_interception(node.test)
    else:
      newcond = InterceptAtoms(generate_while_interception).visit(node.test)
    return ast.While(newcond, node.body, node.orelse, lineno=node.lineno, col_offset=node.col_offset)

  def visit_For(self, node: ast.For) -> ast.For:
    if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
      newiter = generate_range_interception(node.iter.args)
    else:
      newiter = node.iter
    node = ast.For(node.target, newiter, node.body, node.orelse,
                   lineno=node.lineno, col_offset=node.col_offset)
    return super().generic_visit(node)  # type: ignore

  def visit_Compare(self, node: ast.Compare) -> ast.expr:
    node = super().generic_visit(node)  # type: ignore
    if isinstance(node.ops[0], ast.In):
      return generate_in_interception(node)
    elif isinstance(node.ops[0], ast.NotIn):
      return ast.UnaryOp(ast.Not(), generate_in_interception(node),
                         lineno=node.lineno, col_offset=node.col_offset)
    elif isinstance(node.ops[0], ast.Is) and isinstance(node.comparators[0], ast.Constant) and node.comparators[0].value is None:
      return ast.Compare(node.left, [ast.Eq()], node.comparators, lineno=node.lineno, col_offset=node.col_offset)
    elif isinstance(node.ops[0], ast.IsNot) and isinstance(node.comparators[0], ast.Constant) and node.comparators[0].value is None:
      return ast.UnaryOp(ast.Not(), ast.Compare(node.left, [ast.Eq()], node.comparators, lineno=node.lineno, col_offset=node.col_offset),
                         lineno=node.lineno, col_offset=node.col_offset)
    else:
      return node

  def visit_Attribute(self, node: ast.Attribute) -> ast.Attribute:
    node = super().generic_visit(node)  # type: ignore
    if node.attr[0:2] != "__" and not self.is_method_call and str(node.attr) not in all_fields:
      all_fields.append(str(node.attr))
    return node

  def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
    self.class_name = str(node.name)
    all_classes[self.class_name] = ([], [])
    for base in node.bases:
      if isinstance(base, ast.Name):
        all_classes[self.class_name][1].append(str(base.id))
    node = super().generic_visit(node)  # type: ignore
    self.class_name = None
    return node

  def visit_Call(self, node: ast.Call) -> ast.expr:
    old_is_method_call = self.is_method_call
    self.is_method_call = True
    node = super().generic_visit(node)  # type: ignore
    self.is_method_call = old_is_method_call

    if isinstance(node.func, ast.Name) and node.func.id == "isinstance":
      return generate_isinstance_interception(node)
    else:
      return generate_function_call_interception(node)

  def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
    if self.class_name is not None:
      all_classes[self.class_name][0].append(node.name)
    node = super().generic_visit(node)  # type: ignore
    return node

  def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
    node = super().generic_visit(node)  # type: ignore
    if node.module == "paho.mqtt.client" and self.inmodule != "mqtt":
      node.module = "symbex.libraries.mqtt"
      file_path = os.path.dirname(
        os.path.abspath(__file__)) + "/libraries/mqtt.py"
      with open(file_path, "r", encoding="utf-8") as f:
        source_code = f.read()
      tree = ast.parse(source_code, filename=file_path)
      InterceptStatements(self.module_name, self.file_path, "mqtt").visit(tree)
    return node

  def override_Import(self, alias: ast.alias, old_import: str, module: str, need_asname_override: bool = False):
    if alias.name == old_import and self.inmodule != module:
      instrumented_name = "symbex.libraries." + module
      alias.name = instrumented_name
      if need_asname_override and alias.asname is None:
        alias.asname = module
      file_path = os.path.dirname(
        os.path.abspath(__file__)) + "/libraries/" + module + ".py"
      with open(file_path, "r", encoding="utf-8") as f:
        source_code = f.read()
      tree = ast.parse(source_code, filename=file_path)
      InterceptStatements(
        instrumented_name, self.file_path, module).visit(tree)

  def visit_Import(self, node: ast.Import) -> ast.Import:
    node = super().generic_visit(node)  # type: ignore
    for alias in node.names:
      self.override_Import(
        alias, "paho.mqtt.client", "mqtt")
      self.override_Import(
        alias, "json", "json", True)
      self.override_Import(
        alias, "numpy", "numpy", True)
      self.override_Import(
        alias, "math", "math", True)
    return node

  def visit_Module(self, node: ast.Module) -> ast.Module:
    node = super().generic_visit(node)  # type: ignore
    module = types.ModuleType(self.module_name)

    overrides.overrides.install_overrides(module)

    classes_only_module = ast.Module(body=[item for item in node.body
                                           if isinstance(item, ast.ClassDef)
                                           or isinstance(item, ast.FunctionDef)
                                           or isinstance(item, ast.Import)
                                           or isinstance(item, ast.ImportFrom)],
                                     type_ignores=[])
    classes_only = compile(classes_only_module,
                           filename=self.file_path, mode="exec")

    exec(classes_only, module.__dict__)

    if self.module_name not in module_extensions:
      module_extensions[self.module_name] = module
    else:
      for key, value in module.__dict__.items():
        module_extensions[self.module_name].__dict__[key] = value

    for class_name in all_classes.keys():
      if hasattr(module, class_name):
        classes[class_name] = getattr(module, class_name)
        setattr(classes[class_name], "__repr__", object_formatter)

    return node
