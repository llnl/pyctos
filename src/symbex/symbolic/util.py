# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import logging
import math
from typing import Any, Type, Tuple, Callable, Dict, List, Optional

from symbex.types.symbolicvalue import SymbolicValue, makeSymbolicValue
from symbex.astmanip import get_all_classes

from symbex.smtlib import *
smt = get_smt_lib()


logger = logging.getLogger(__name__)

any_sort: DatatypeSortRef = None
"""
The `any` sort
"""

float_sort: DatatypeSortRef = None
"""
The sort used to represent a Python `float`.
Is:

- `smt.RealSort`
- `smt.FPSort`
- `ExRealSort`
"""

float_val: Callable[[float], ExprRef]
"""
Constructor for floating-point literals.

- If `float_sort` is `smt.RealSort`, this function corresponds to `smt.RealVal`.
- If `float_sort` is `smt.FPSort`, this function corresponds to `smt.FPVal`.
- If `float_sort` is `ExRealSort`, this function corresponds to a `smt.RealVal` call followed bt a `create_finite` call.
"""

to_float: Callable[[ExprRef], ExprRef]
"""
Convert a number to a floating-point sort.

- If `float_sort` is `smt.RealSort`, this function corresponds to `smt.ToReal`.
- If `float_sort` is `smt.FPSort`, this function corresponds to a `smt.ToReal` call followed by a `smt.fpRealToFP` call.
"""

to_int: Callable[[ExprRef], IntNumRef]
"""
Convert a number to an integer sort.

- If `float_sort` is `smt.RealSort`, this function corresponds to `smt.ToInt`.
- If `float_sort` is `smt.FPSort`, this function corresponds to a `smt.fpToReal` call followed by a `smt.ToInt` call.
"""

is_nan: Callable[[ExprRef], ExprRef]
"""
Returns an expression that checks if the input is NaN.

- If `float_sort` is `smt.RealSort`, this function returns `smt.BoolVal(False)`.
- If `float_sort` is `smt.FPSort`, this function corresponds to `smt.fpIsNaN`.
- If `float_sort` is `ExRealSort`, this function returns `is_nan`.
"""

is_pos_inf: Callable[[ExprRef], ExprRef]
"""
Returns an expression that checks if the input is NaN.

- If `float_sort` is `smt.RealSort`, this function returns `smt.BoolVal(False)`.
- If `float_sort` is `smt.FPSort`, this function corresponds to `x == +oo`.
- If `float_sort` is `ExRealSort`, this function returns `is_inf`.
"""

is_neg_inf: Callable[[ExprRef], ExprRef]
"""
Returns an expression that checks if the input is NaN.

- If `float_sort` is `smt.RealSort`, this function returns `smt.BoolVal(False)`.
- If `float_sort` is `smt.FPSort`, this function corresponds to `x == -oo`.
- If `float_sort` is `ExRealSort`, this function returns `is_neg_inf`.
"""

is_finite: Callable[[ExprRef], ExprRef]
"""
Returns an expression that checks if the input is finite.

- If `float_sort` is `smt.RealSort`, this function returns `smt.BoolVal(True)`.
- If `float_sort` is `smt.FPSort`, this function corresponds to `not(smt.fpIsNaN \/ smt.fpIsInf)`.
- If `float_sort` is `ExRealSort`, this function returns `is_real`.
"""

nan: ExprRef
"""
Contains an SMT expression representing NaN.

- If `float_sort` is `smt.RealSort`, this value is `0`.
- If `float_sort` is `smt.FPSort`, this function corresponds to `smt.fpNaN`
- If `float_sort` is `ExRealSort`, this function corresponds to `create_nan`
"""

pos_inf: ExprRef
"""
Contains an SMT expression representing NaN.

- If `float_sort` is `smt.RealSort`, this value is `0`.
- If `float_sort` is `smt.FPSort`, this function corresponds to `smt.FPVal(math.inf, smt.Float64())`
- If `float_sort` is `ExRealSort`, this function corresponds to `create_inf`
"""

neg_inf: ExprRef
"""
Contains an SMT expression representing NaN.

- If `float_sort` is `smt.RealSort`, this value is `0`.
- If `float_sort` is `smt.FPSort`, this function corresponds to `smt.FPVal(-math.inf, smt.Float64())`
- If `float_sort` is `ExRealSort`, this function corresponds to `create_neg_inf`
"""

get_int: FuncDeclRef = None
"""
`any -> int`

Gets the integer value from an `any` value
"""

get_float: FuncDeclRef = None
"""
`any -> float`

Gets the floating-point value from an `any` value
"""

get_bool: FuncDeclRef = None
"""
`any -> bool`

Gets the boolean value from an `any` value
"""

get_reference: FuncDeclRef = None
"""
`any -> reference`

Gets the reference value from an `any` value
"""

get_string: FuncDeclRef = None
"""
`any -> string`

Gets the string value from an `any` value
"""

is_int: FuncDeclRef = None
"""
`any -> bool`

Checks if an `any` value is an integer
"""

is_float: FuncDeclRef = None
"""
`any -> bool`

Checks if an `any` value is a float
"""

is_bool: FuncDeclRef = None
"""
`any -> bool`

Checks if an `any` value is a boolean
"""

is_reference: FuncDeclRef = None
"""
`any -> bool`

Checks if an `any` value is a reference
"""

is_none: FuncDeclRef = None
"""
`any -> bool`

Checks if an `any` value is `None`
"""

is_string: FuncDeclRef = None
"""
`any -> bool`

Checks if an `any` value is a string
"""

create_int: FuncDeclRef = None
"""
`int -> any`

Creates an `any` value from an integer
"""

create_float: FuncDeclRef = None
"""
`float -> any`

Creates an `any` value from a float
"""

create_bool: FuncDeclRef = None
"""
`bool -> any`

Creates an `any` value from a bolean
"""

create_reference: FuncDeclRef = None
"""
`reference -> any`

Creates an `any` value from a reference
"""

create_none: FuncDeclRef = None
"""
`() -> any`

Creates an `any` value representing `None`
"""

create_string: FuncDeclRef = None
"""
`string -> any`

Creates an `any` value from a string
"""

heap_sort: DatatypeSortRef = None
"""
Represents the sort of heap items (e.g., lists, objects)
"""

get_list: FuncDeclRef = None
"""
`heap_sort -> (int -> any)`

Gets the list value from a `heap` value
"""

get_list_length: FuncDeclRef = None
"""
`heap_sort -> int`

Gets the list length value from a `heap` value
"""

get_list_mutable: FuncDeclRef = None
"""
`heap_sort -> bool`

Gets the list mutability property from a `heap` value
"""

get_object: FuncDeclRef = None
"""
`heap_sort -> (string -> any)`

Gets the object value from a `heap` value
"""

get_object_type: FuncDeclRef = None
"""
`heap_sort -> class_sort`

Gets the object type from a `heap` value
"""

get_object_members: FuncDeclRef = None
"""
`heap_sort -> (string -> bool)`

Gets the object members from a `heap` value
"""

get_dict_keys: FuncDeclRef = None
"""
`heap_sort -> (int -> any)`

Gets a list of keys in the dict in the order they were added
"""

get_dict: FuncDeclRef = None
"""
`heap_sort -> (any -> any)`

Gets the dictionary value from a `heap` value
"""

get_dict_cardinality: FuncDeclRef = None
"""
`heap_sort -> int`

Gets the number of keys in a dictionary
"""

get_set: FuncDeclRef = None
"""
Z3: `heap_sort -> (int -> any)`

CVC5: `heap_sort -> (set any)`

Gets the set value from a `heap` value
"""

get_intarray: FuncDeclRef = None
"""
`heap_sort -> seq int`

Gets the integer array value from a `heap` value
"""

get_floatarray: FuncDeclRef = None
"""
`heap_sort -> seq float`

Gets the float array value from a `heap` value
"""

get_boolarray: FuncDeclRef = None
"""
`heap_sort -> seq bool`

Gets the bool array value from a `heap` value
"""

is_list: FuncDeclRef = None
"""
`heap_sort -> bool`

Checks if a `heap` value is a list
"""

is_object: FuncDeclRef = None
"""
`heap_sort -> bool`

Checks if a `heap` value is an object
"""

is_dict: FuncDeclRef = None
"""
`heap_sort -> bool`

Checks if a `heap` value is a dictionary
"""

is_set: FuncDeclRef = None
"""
`heap_sort -> bool`

Checks if a `heap` value is a set
"""

is_intarray: FuncDeclRef = None
"""
`heap_sort -> bool`

Checks if a `heap` value is an integer array
"""

is_floatarray: FuncDeclRef = None
"""
`heap_sort -> bool`

Checks if a `heap` value is a float array
"""

is_boolarray: FuncDeclRef = None
"""
`heap_sort -> bool`

Checks if a `heap` value is a bool array
"""

heap: ExprRef = None
"""
Represents the heap, a value of sort `reference -> heap_sort`
"""

bound: FuncDeclRef = None
"""
`reference -> int`

Represents the cardinality of an object's domain.
Only defined when the SMT solver is Z3.
"""

reference_sort: SortRef = None
"""
Represents a reference sort
"""

class_sort: DatatypeSortRef = None
"""
Represents the sort of the associated class with an object
"""

get_class_type: Callable[[ExprRef], Optional[Type[object]]]
"""
Obtains the class type of an `ExprRef` which represents the `objecttype` field of a heap object.
This function allows one to call the constructor associated with a symbolic object.
"""

class_type_recognizer: Callable[[str], ExprRef]
"""
This function returns the recognizer `ExprRef` associated with the name of a class.
"""

get_axioms: Callable[[], List[ExprRef]]
"""
This function returns a list of all global axioms which must be asserted before solving for any variables.
"""

exists_in_dict_keys: Callable[[ExprRef, ExprRef, int, Dict[Any, Any]], ExprRef]
"""
First parameter: `t`, an `any` value to check if it's in the keys of a dictionary

Second parameter `ref`, a `reference` which points to the associated dictionary on the heap

Second parameter `length`, the length of the concrete half of the dictionary

Returns an expression which represents the notion of `t` being in the keys of the dictionary pointed to by `ref`.
"""

exists_in_set: Callable[[ExprRef, ExprRef], ExprRef]
"""
First parameter: `t`, an `any` value to check if it's in a set

Second parameter `ref`, a `reference` which points to the associated set on the heap

Returns an expression which represents the notion of `t` being in the set pointed to by `ref`.
"""

get_cardinality: Callable[[SetRef], ExprRef]
"""
Gets the cardinality of a CVC5 set.
Must be in CVC5 mode to call this function.
"""


def dereference(expr: ExprRef) -> ExprRef:
  """
  Dereference a reference value if `expr` is an `any` type.

  Equivalent to: `heap[get_reference(expr)]`.
  If `expr` is not an `any` type, return `expr`.
  """
  if is_any(expr):
    return heap[get_reference(expr)]
  else:
    return expr


def create_subtree_graph(superclasses: Dict[str, List[str]]) -> Dict[str, List[str]]:
  """
  Inverts the direction of a directed acyclic graph.
  """
  ret: Dict[str, List[str]] = {}

  for name in superclasses.keys():
    if name not in ret.keys():
      ret[name] = []
    for to in superclasses[name]:
      if to not in ret.keys():
        ret[to] = []
      ret[to].append(name)

  return ret


def initialize_sorts() -> None:
  """
  Initializes all of the SMT sorts to be used during concolic execution.
  Creates the heap and initializes the `get_*`, `is_*`, and `create_*`
  functions, as well as several other functions in this namespace.
  """
  global any_sort, get_int, get_float, get_bool, get_reference, is_int, is_float, is_bool, \
      is_reference, create_int, create_float, create_bool, create_reference, reference_sort, \
      class_sort, heap_sort, get_list, get_list_length, get_object, get_object_type, heap, \
      get_object_members, is_list, is_object, get_class_type, class_type_recognizer, \
      is_none, create_none, get_string, is_string, create_string, exists_in_dict_keys, \
      get_axioms, get_dict, get_dict_cardinality, is_dict, bound, get_set, is_set, exists_in_set, \
      get_cardinality, get_list_mutable, get_dict_keys, get_intarray, get_floatarray, is_intarray, \
      is_floatarray, get_boolarray, is_boolarray, float_sort, float_val, to_float, to_int, is_nan, \
      is_pos_inf, is_neg_inf, is_finite, nan, pos_inf, neg_inf

  import symbex.lib as lib
  from symbex.symbolic.factories import lift_value

  classes = {clas: superclasses for clas,
             (_, superclasses) in get_all_classes().items()}
  class_names = [*classes.keys()] if len(classes.keys()) > 0 else ["object"]
  subtree_graph = create_subtree_graph(classes)

  classSort = smt.Datatype('class')
  for name in class_names:
    classSort.declare(name)
  class_sort = classSort.create()

  def get_class_type_prot(expr: ExprRef) -> Optional[Type[object]]:
    for id in range(len(class_names)):
      if smt.simplify(class_sort.recognizer(id)(expr)):
        return lib.get_class(class_names[id])
    return None

  def class_type_recognizer_prot(class_name: str) -> Callable[[ExprRef], ExprRef]:
    disjuncts: List[ExprRef] = []
    id = [i for i, x in enumerate(classes) if x == class_name][0]
    disjuncts.append(class_sort.recognizer(id))

    for subclass in subtree_graph[class_name]:
      disjuncts.append(class_type_recognizer_prot(subclass))

    if len(disjuncts) > 1:
      return lambda class_type: smt.Or(*map(lambda disjunct: disjunct(class_type), disjuncts))
    else:
      assert len(disjuncts) == 1
      return lambda class_type: disjuncts[0](class_type)

  get_class_type = get_class_type_prot
  class_type_recognizer = class_type_recognizer_prot

  reference_sort = smt.DeclareSort('reference')

  if get_float_theory() == FloatTheory.FP64:
    float_sort = smt.Float64()

    def float_val(x):
      return smt.FPVal(x, float_sort)

    def to_float(x):
      return smt.fpRealToFP(smt.RNE(), smt.ToReal(x), float_sort)

    def to_int(x):
      val = smt.fpToReal(x)
      return smt.If(val >= 0, smt.ToInt(val), -smt.ToInt(-val))

    nan = smt.fpNaN(float_sort)
    pos_inf = smt.FPVal(math.inf, float_sort)
    neg_inf = smt.FPVal(-math.inf, float_sort)
    is_nan = smt.fpIsNaN

    def is_pos_inf(x):
      return smt.fpEQ(x, pos_inf)

    def is_neg_inf(x):
      return smt.fpEQ(x, neg_inf)

    def is_finite(x):
      return smt.Not(smt.Or(is_nan(x), smt.fpIsInf(x)))
  elif get_float_theory() == FloatTheory.EXREAL:
    exreal = smt.Datatype('exreal')
    exreal.declare('finite', ('real', smt.RealSort()))
    exreal.declare('nan')
    exreal.declare('inf')
    exreal.declare('neginf')
    float_sort = exreal.create()

    nan = float_sort.constructor(1)()
    pos_inf = float_sort.constructor(2)()
    neg_inf = float_sort.constructor(3)()

    def float_val(x):
      if math.isnan(x):
        return nan
      elif x == math.inf:
        return pos_inf
      elif x == -math.inf:
        return neg_inf
      else:
        return float_sort.constructor(0)(smt.RealVal(x))

    def to_float(x):
      return float_sort.constructor(0)(smt.ToReal(x))

    def to_int(x):
      val = float_sort.accessor(0, 0)(x)
      return smt.If(val >= 0, smt.ToInt(val), -smt.ToInt(-val))

    is_nan = float_sort.recognizer(1)
    is_pos_inf = float_sort.recognizer(2)
    is_neg_inf = float_sort.recognizer(3)
    is_finite = float_sort.recognizer(0)
  else:
    float_sort = smt.RealSort()
    float_val = smt.RealVal
    to_float = smt.ToReal

    def to_int(x):
      return smt.If(x >= 0, smt.ToInt(x), -smt.ToInt(-x))

    def is_nan(x):
      return smt.BoolVal(False)

    def is_pos_inf(x):
      return smt.BoolVal(False)

    def is_neg_inf(x):
      return smt.BoolVal(False)

    def is_finite(x):
      return smt.BoolVal(True)

    nan = smt.RealVal(0)
    pos_inf = smt.RealVal(0)
    neg_inf = smt.RealVal(0)

  anySort = smt.Datatype('any')
  anySort.declare('int', ('intval', smt.IntSort()))
  anySort.declare('float', ('floatval', float_sort))
  anySort.declare('bool', ('boolval', smt.BoolSort()))
  anySort.declare('reference', ('referenceval', reference_sort))
  anySort.declare('none')
  anySort.declare('string', ('stringval', smt.StringSort()))

  # Think about ways of getting rid of magic numbers
  any_sort = anySort.create()
  get_int = any_sort.accessor(0, 0)
  get_float = any_sort.accessor(1, 0)
  get_bool = any_sort.accessor(2, 0)
  get_reference = any_sort.accessor(3, 0)
  get_string = any_sort.accessor(5, 0)

  is_int = any_sort.recognizer(0)
  is_float = any_sort.recognizer(1)
  is_bool = any_sort.recognizer(2)
  is_reference = any_sort.recognizer(3)
  is_none = any_sort.recognizer(4)
  is_string = any_sort.recognizer(5)

  create_int = any_sort.constructor(0)
  create_float = any_sort.constructor(1)
  create_bool = any_sort.constructor(2)
  create_reference = any_sort.constructor(3)
  create_none = any_sort.constructor(4)
  create_string = any_sort.constructor(5)

  heapSort = smt.Datatype('heap')
  heapSort.declare(
    'list',
    ('listlength', smt.IntSort()),
    ('listval', smt.ArraySort(smt.IntSort(), any_sort)),
    ('listmutable', smt.BoolSort()))
  heapSort.declare(
    'object',
    ('objecttype', class_sort),
    ('objectval', smt.ArraySort(smt.StringSort(), any_sort)),
    ('objectmembers', smt.ArraySort(smt.StringSort(), smt.BoolSort())))
  heapSort.declare(
    'dict',
    ('dictcard', smt.IntSort()),
    ('dictkeys', smt.ArraySort(smt.IntSort(), any_sort)),
    ('dictassoc', smt.ArraySort(any_sort, any_sort)))
  if configured_library == SMTLibrary.Z3:
    heapSort.declare(
      'set',
      ('setmembers', smt.ArraySort(smt.IntSort(), any_sort)))
  else:
    heapSort.declare(
      'set',
      ('setmembers', smt.SetSort(any_sort)))

  heapSort.declare(
    'intarray',
    ('intarrayval', smt.SeqSort(smt.IntSort())))
  heapSort.declare(
    'floatarray',
    ('floatarrayval', smt.SeqSort(float_sort)))
  heapSort.declare(
    'boolarray',
    ('boolarrayval', smt.SeqSort(smt.BoolSort())))

  heap_sort = heapSort.create()
  get_list_length = heap_sort.accessor(0, 0)
  get_list = heap_sort.accessor(0, 1)
  get_list_mutable = heap_sort.accessor(0, 2)
  get_object_type = heap_sort.accessor(1, 0)
  get_object = heap_sort.accessor(1, 1)
  get_object_members = heap_sort.accessor(1, 2)
  get_dict_cardinality = heap_sort.accessor(2, 0)
  get_dict_keys = heap_sort.accessor(2, 1)
  get_dict = heap_sort.accessor(2, 2)
  get_set = heap_sort.accessor(3, 0)
  get_intarray = heap_sort.accessor(4, 0)
  get_floatarray = heap_sort.accessor(5, 0)
  get_boolarray = heap_sort.accessor(6, 0)

  is_list = heap_sort.recognizer(0)
  is_object = heap_sort.recognizer(1)
  is_dict = heap_sort.recognizer(2)
  is_set = heap_sort.recognizer(3)
  is_intarray = heap_sort.recognizer(4)
  is_floatarray = heap_sort.recognizer(5)
  is_boolarray = heap_sort.recognizer(6)

  heap = smt.Const('__heap', smt.ArraySort(reference_sort, heap_sort))

  r = smt.Const('__r', reference_sort)
  r2 = smt.Const('__r2', reference_sort)
  x = smt.Int('__x')
  y = smt.Int('__y')
  i = smt.Int('__i')

  if configured_library == SMTLibrary.Z3:
    s = smt.Function('__s', reference_sort, smt.IntSort(), smt.BoolSort())
    bound = smt.Function('__bound', reference_sort, smt.IntSort())

  def exists_in_dict_keys_prot(t: ExprRef, ref: ExprRef, length: int, modifications: Dict[Any, Any]) -> ExprRef:
    assert is_any(t)
    assert ref.sort() == reference_sort
    assert length >= 0

    disjuncts: List[ExprRef] = [smt.And(get_dict_cardinality(
      heap[ref]) >= length + 1, get_dict_keys(heap[ref])[length] == t)]

    for i in range(length):
      if i not in modifications:
        disjuncts.append(smt.And(i < get_dict_cardinality(
          heap[ref]), get_dict_keys(heap[ref])[i] == t))

    for v in modifications.values():
      if not isinstance(v, SymbolicValue):
        v = lift_value(v)
      disjuncts.append(lift_expr_to_any(
        t) == lift_expr_to_any(v.get_formula()))

    if len(disjuncts) > 1:
      return smt.Or(*disjuncts)
    else:
      return disjuncts[0]

  def exists_in_set_prot(t: ExprRef, ref: ExprRef) -> ExprRef:
    assert is_any(t)
    assert ref.sort() == reference_sort

    if configured_library == SMTLibrary.Z3:
      return smt.Exists([x], smt.And(get_set(heap[ref])[x] == t, s(ref, x)))
    else:
      return get_set(heap[ref])[t]

  def get_cardinality_prot(s: SetRef) -> ExprRef:
    assert configured_library == SMTLibrary.CVC5

# mypy: disable-error-code="import-untyped"
    from cvc5 import Kind
    return smt.SetRef(s.ctx.tm.mkTerm(Kind.SET_CARD, s.as_ast()))

  def get_axioms_prot() -> List[ExprRef]:
    axiom_list: List[ExprRef] = []

    if configured_library == SMTLibrary.Z3:
      # S is True for 0 <= x < bound
      axiom_list.append(smt.ForAll(
        [r, x], smt.Implies(smt.And(0 <= x, x < bound(r)), s(r, x))))
      # S is False for x < 0
      axiom_list.append(smt.ForAll(
        [r, x], smt.Implies(x < 0, smt.Not(s(r, x)))))
      # S is False for x >= bound
      axiom_list.append(smt.ForAll(
        [r, x], smt.Implies(x >= bound(r), smt.Not(s(r, x)))))
      # Bound represents the size of a set
      axiom_list.append(smt.ForAll(
        [r, x, y], smt.Implies(smt.And(s(r, x), s(r, y), is_set(heap[r])),
                               smt.Implies(get_set(heap[r])[x] == get_set(heap[r])[y], x == y))))

    # References may not appear as keys in a dict
    axiom_list.append(smt.ForAll(
      [r, x], smt.Implies(smt.And(is_dict(heap[r]), -1 < x, x < get_dict_cardinality(heap[r])),
                          smt.Not(is_reference(get_dict_keys(heap[r])[x])))))
    # For keys in a dict, 0 == 0.0 == False
    axiom_list.append(smt.ForAll(
      [r, x, y], smt.Implies(
        smt.And(is_dict(heap[r]), -1 < x, x < get_dict_cardinality(heap[r]),
                -1 < y, y < get_dict_cardinality(heap[r]), smt.Or(x < y, y < x)),
        smt.Not(smt.Or(
          smt.And(
            get_dict_keys(heap[r])[x] ==
              create_int(smt.IntVal(0)),
            get_dict_keys(heap[r])[x] ==
              create_bool(smt.BoolVal(False))),
          smt.And(
            get_dict_keys(heap[r])[x] ==
              create_int(smt.IntVal(0)),
            get_dict_keys(heap[r])[x] ==
              create_float(float_val(0.0))))))))
    # For keys in a dict, 1 == 1.0 == True
    axiom_list.append(smt.ForAll(
      [r, x, y], smt.Implies(
        smt.And(is_dict(heap[r]), -1 < x, x < get_dict_cardinality(heap[r]),
                -1 < y, y < get_dict_cardinality(heap[r]), smt.Or(x < y, y < x)),
        smt.Not(smt.Or(
          smt.And(
            get_dict_keys(heap[r])[x] ==
              create_int(smt.IntVal(1)),
            get_dict_keys(heap[r])[x] ==
              create_bool(smt.BoolVal(True))),
          smt.And(
            get_dict_keys(heap[r])[x] ==
              create_int(smt.IntVal(1)),
            get_dict_keys(heap[r])[x] ==
              create_float(float_val(1.0))))))))
    # For keys in a dict, an int is equal to its corresponding float
    axiom_list.append(smt.ForAll(
      [r, x, y, i], smt.Implies(
        smt.And(is_dict(heap[r]), -1 < x, x < get_dict_cardinality(heap[r]),
                -1 < y, y < get_dict_cardinality(heap[r]), smt.Or(x < y, y < x)),
        smt.Not(
          smt.And(
            get_dict_keys(heap[r])[x] ==
              create_int(i),
            get_dict_keys(heap[r])[x] ==
              create_float(to_float(i)))))))
    # Every dict key must be distinct
    axiom_list.append(smt.ForAll(
      [r, x, y], smt.Implies(
        smt.And(is_dict(heap[r]), -1 < x, x < get_dict_cardinality(heap[r]),
                -1 < y, y < get_dict_cardinality(heap[r]), smt.Or(x < y, y < x)),
        get_dict_keys(heap[r])[x] != get_dict_keys(heap[r])[y])))
    # Lists may not appear in sets
    axiom_list.append(smt.ForAll(
      [r, r2], smt.Implies(smt.And(is_set(heap[r]), exists_in_set_prot(create_reference(r2), r)),
                           smt.Not(is_list(heap[r2])))))
    # For elements in a set, 0 == 0.0 == False
    axiom_list.append(smt.ForAll(
      [r], smt.Implies(is_set(heap[r]), smt.And(smt.Not(smt.And(exists_in_set_prot(create_bool(smt.BoolVal(False)), r),
                                                                exists_in_set_prot(create_int(smt.IntVal(0)), r))),
                                                smt.Not(smt.And(exists_in_set_prot(create_bool(smt.BoolVal(False)), r),
                                                                exists_in_set_prot(create_float(float_val(0.0)), r)))))))
    # For elements in a set, 1 == 1.0 == True
    axiom_list.append(smt.ForAll(
      [r], smt.Implies(is_set(heap[r]), smt.And(smt.Not(smt.And(exists_in_set_prot(create_bool(smt.BoolVal(True)), r),
                                                                exists_in_set_prot(create_int(smt.IntVal(1)), r))),
                                                smt.Not(smt.And(exists_in_set_prot(create_bool(smt.BoolVal(True)), r),
                                                                exists_in_set_prot(create_float(float_val(1.0)), r)))))))
    # For elements in a set, an int is equal to its corresponding float
    axiom_list.append(smt.ForAll(
      [r, x], smt.Implies(is_set(heap[r]), smt.Not(smt.And(exists_in_set_prot(create_int(x), r),
                                                           exists_in_set_prot(create_float(to_float(x)), r))))))

    return axiom_list

  get_axioms = get_axioms_prot
  exists_in_dict_keys = exists_in_dict_keys_prot
  exists_in_set = exists_in_set_prot
  get_cardinality = get_cardinality_prot


def is_any(f: ExprRef) -> bool:
  """
  Checks if `f` is an `any` type, returns a boolean.
  """
  try:
    return f.sort() == any_sort
  except:
    return False


def get_default_value() -> Any:
  """
  Returns the default concrete value (`0`).
  """
  return 0


def as_datatype_sort_ref(sort: SortRef) -> DatatypeSortRef:
  """
  Converts a `SortRef` to a `DatatypeSortRef` if it is not one already.
  """
  if not isinstance(sort, smt.DatatypeSortRef):
    sort = smt.DatatypeSortRef(sort.ast, sort.ctx)
  return sort


def lift_expr_to_any(v: ExprRef) -> ExprRef:
  """
  Takes an arbitrary SMT expression and lifts it to an `any` type.
  If expression is already an `any` type, just return the original expression.

  Input should be either an `Int`, `Real`/`FP`, `Bool`, `Reference`, or `String`.
  """
  if is_any(v):
    return v
  elif v.sort() == smt.IntSort():
    return create_int(v)
  elif v.sort() == float_sort:
    return create_float(v)
  elif v.sort() == smt.BoolSort():
    return create_bool(v)
  elif smt.is_string(v):
    return create_string(v)
  elif v.sort() == reference_sort:
    return create_reference(v)
  elif v.sort() == smt.CharSort():
    return create_string(smt.Unit(v))
  else:
    raise NotImplementedError


def narrow_from_any(s: SymbolicValue) -> SymbolicValue:
  """
  Narrows an expression from an `any` type to its underlying type (e.g., `Int`, `Reference`, etc.).
  Concrete values are unchanged.

  If the input is not an `any` type, just return the original symbolic value.
  """
  if is_any(s.get_formula()):
    if type(s.get_value()) is int:
      return makeSymbolicValue(v=s.get_value(), formula=get_int(s.get_formula()))
    elif type(s.get_value()) is float:
      return makeSymbolicValue(v=s.get_value(), formula=get_float(s.get_formula()))
    elif type(s.get_value()) is bool:
      return makeSymbolicValue(v=s.get_value(), formula=get_bool(s.get_formula()))
    elif s.get_value() is None:
      return makeSymbolicValue(v=s.get_value(), formula=s.get_formula())
    elif type(s.get_value()) is str:
      return makeSymbolicValue(v=s.get_value(), formula=get_string(s.get_formula()))
    else:
      return makeSymbolicValue(v=s.get_value(), formula=get_reference(s.get_formula()))
  else:
    return s


def narrow_from_any_t(s: SymbolicValue, t: Type) -> SymbolicValue:
  """
  Narrows a type from `any` to the specified type, performing conversions along the way.
  Concrete values are unchanged.

  Builds an expression which checks the underlying type behind the `any` and converts it to
  the specified type using Python's conversion sequence (e.g., 2 is truthy if converted to
  a boolean).

  If the symbolic expression is not of `any` type, a conversion will still occur.
  The underlying expression will be simpler, as the type checks in this case are done at
  the Python level, not the SMT level.
  """
  if is_any(s.get_formula()):
    f = s.get_formula()

    if t is int:
      return makeSymbolicValue(v=s.get_value(), formula=smt.If(is_int(f), get_int(f), smt.If(is_float(f), to_int(get_float(f)), smt.If(is_bool(f), smt.If(get_bool(f), 1, 0), smt.IntVal(1)))))
    elif t is float:
      return makeSymbolicValue(v=s.get_value(), formula=smt.If(is_int(f), to_float(get_int(f)), smt.If(is_float(f), get_float(f), smt.If(is_bool(f), smt.If(get_bool(f), float_val(1.0), float_val(0.0)), float_val(1.0)))))
    elif t is bool:
      return makeSymbolicValue(v=s.get_value(), formula=smt.If(is_int(f), get_int(f) != 0, smt.If(is_float(f), smt.And(get_float(f) != float_val(0.0), get_float(f) != float_val(-0.0)), smt.If(is_bool(f), get_bool(f), smt.BoolVal(True)))))
    else:
      raise NotImplementedError
  else:
    if t is int:
      if s.get_formula().sort() == smt.IntSort():
        return s
      elif s.get_formula().sort() == float_sort:
        return makeSymbolicValue(v=s.get_value(), formula=to_int(s.get_formula()))
      elif s.get_formula().sort() == smt.BoolSort():
        return makeSymbolicValue(v=s.get_value(), formula=smt.If(s.get_formula(), 1, 0))
      else:
        raise NotImplementedError
    elif t is float:
      if s.get_formula().sort() == smt.IntSort():
        return makeSymbolicValue(v=s.get_value(), formula=to_float(s.get_formula()))
      elif s.get_formula().sort() == float_sort:
        return s
      elif s.get_formula().sort() == smt.BoolSort():
        return makeSymbolicValue(v=s.get_value(), formula=smt.If(s.get_formula(), float_val(1.0), float_val(0.0)))
      else:
        raise NotImplementedError
    elif t is bool:
      if s.get_formula().sort() == smt.IntSort():
        return makeSymbolicValue(v=s.get_value(), formula=s.get_formula() != 0)
      elif s.get_formula().sort() == float_sort:
        return makeSymbolicValue(v=s.get_value(), formula=smt.And(s.get_formula() != float_val(0.0), s.get_formula() != float_val(-0.0)))
      elif s.get_formula().sort() == smt.BoolSort():
        return s
      else:
        raise NotImplementedError
    else:
      raise NotImplementedError


def convert_both_halves(sv1: SymbolicValue, sv2: SymbolicValue) -> Tuple[SymbolicValue, SymbolicValue]:
  """
  Convert a pair of values into the same type following Python's conversion rules for binary operators.
  E.g., passing in a `float` and a `bool` will convert both halves to a `float`.

  Accounts for both the case where the symbolic values are `any` and the case where they are not `any`.
  """
  type1, type2 = type(sv1.get_value()), type(sv2.get_value())

  if type1 is type2:
    return narrow_from_any_t(sv1, type1), narrow_from_any_t(sv2, type2)
  elif (type1 is int and type2 is float) or (type1 is float and type2 is int):
    return narrow_from_any_t(sv1, float), narrow_from_any_t(sv2, float)
  elif (type1 is int and type2 is bool) or (type1 is bool and type2 is int):
    return narrow_from_any_t(sv1, int), narrow_from_any_t(sv2, int)
  elif (type1 is float and type2 is bool) or (type1 is bool and type2 is float):
    return narrow_from_any_t(sv1, float), narrow_from_any_t(sv2, float)
  else:
    logger.debug(f"Encountered types {type1} and {type2}")
    raise NotImplementedError


def are_same_any_type(ex1: ExprRef, ex2: ExprRef) -> ExprRef:
  """
  Builds an expression to check if `ex1` and `ex2` are the same type.

  - If `ex1` and `ex2` are both `any`, build an SMT expression which checks if they are the same type.
  - If only one of `ex1` and `ex2` is `any`, build an SMT expression which checks if the `any` type is equal
  to the non-`any` type.
  - If neither `ex1` and `ex2` are `any`, return a `BoolVal` which is either `True` or `False`.
  """
  if is_any(ex1) and is_any(ex2):
    return smt.Or(smt.And(is_int(ex1), is_int(ex2)),
                  smt.And(is_float(ex1), is_float(ex2)),
                  smt.And(is_bool(ex1), is_bool(ex2)),
                  smt.And(is_none(ex1), is_none(ex2)),
                  smt.And(is_string(ex1), is_string(ex2)),
                  smt.And(is_reference(ex1), is_reference(ex2),
                  smt.Or(
                      smt.And(is_set(heap[get_reference(ex1)]),
                              is_set(heap[get_reference(ex2)])),
                      smt.And(is_list(heap[get_reference(ex1)]),
                              is_list(heap[get_reference(ex2)])),
                      smt.And(is_dict(heap[get_reference(ex1)]),
                              is_dict(heap[get_reference(ex2)])),
                      smt.And(is_object(heap[get_reference(ex1)]),
                              is_object(heap[get_reference(ex2)])))))
  elif is_any(ex1):
    if ex2.sort() == smt.IntSort():
      return is_int(ex1)
    elif ex2.sort() == float_sort:
      return is_float(ex1)
    elif ex2.sort() == smt.BoolSort():
      return is_bool(ex1)
    elif ex2.sort() == smt.StringSort():
      return is_string(ex1)
    else:
      return is_reference(ex1)
  elif is_any(ex2):
    if ex1.sort() == smt.IntSort():
      return is_int(ex2)
    elif ex1.sort() == float_sort:
      return is_float(ex2)
    elif ex1.sort() == smt.BoolSort():
      return is_bool(ex2)
    elif ex1.sort() == smt.StringSort():
      return is_string(ex2)
    else:
      return is_reference(ex2)
  else:
    return smt.BoolVal(ex1.sort() == ex2.sort())


def is_type(ex: ExprRef, typ: Type) -> ExprRef:
  """
  Builds an SMT expression which checks if `ex` has a corresponding type as `typ` (a Python type).

  For example, `is_type(ex, int)` returns `is_int(ex)`.

  Accounts for the cases where `ex` is `any` or non-`any`.
  If `ex` is non-`any`, return a `BoolVal` which is either `True` or `False`,
  as this check cannot occur within the SMT theory.
  """
  if is_any(ex):
    if typ is int:
      return is_int(ex)
    elif typ is float:
      return is_float(ex)
    elif typ is bool:
      return is_bool(ex)
    elif typ is None or typ is type(None):
      return is_none(ex)
    elif typ is str:
      return is_string(ex)
    elif typ is list:
      return smt.And(is_reference(ex), is_list(dereference(ex)), get_list_mutable(dereference(ex)))
    elif typ is tuple:
      return smt.And(is_reference(ex), is_list(dereference(ex)), smt.Not(get_list_mutable(dereference(ex))))
    elif typ is dict:
      return smt.And(is_reference(ex), is_dict(dereference(ex)))
    elif typ is set:
      return smt.And(is_reference(ex), is_set(dereference(ex)))
    else:
      return smt.And(is_reference(ex), is_object(dereference(ex)))
  else:
    if typ is int:
      return smt.BoolVal(ex.sort() == smt.IntSort())
    elif typ is float:
      return smt.BoolVal(ex.sort() == float_sort)
    elif typ is bool:
      return smt.BoolVal(ex.sort() == smt.BoolSort())
    elif typ is str:
      return smt.BoolVal(ex.sort() == smt.StringSort())
    else:
      raise NotImplementedError


def is_not_builtin(typ: Type) -> bool:
  """
  Checks if `typ` is a class object.
  """
  return typ is not int and \
      typ is not float and \
      typ is not bool and \
      typ is not None and \
      typ is not type(None) and \
      typ is not str and \
      typ is not list and \
      typ is not tuple and \
      typ is not dict and \
      typ is not set
