# The Pyctos Object Model

Pyctos models Python's `Any` type and a heap. The exact breakdown of the object model is as follows:

```ocaml
(* Represents top-level Any objects *)
any ::=
    | None
    | Int int
    | Float real
    | Bool bool
    | String string
    | Reference reference

(* References onto the heap. References can be
   compared for equality/inequality, but have
   no ordering as it is not needed. *)
reference ::= (uninterpreted sort)

(* Items that reside in the heap. *)
heapItem ::=
    | List   (int -> any,                    (* list data *)
              bool,                          (* mutable *)
              int)                           (* length of list *)

    | Object (class,                         (* type of class *)
              string -> any,                 (* attribute-data map *)
              string -> bool)                (* set of object attributes *)

    | Dict   (any -> any,                    (* key-value map *)
              int -> any,                    (* lookup for dict keys *)
              int)                           (* cardinality of dictionary *)

    | Set    (int -> any |    (* Z3 ONLY *)  (* lookup for set items *)
              FiniteSet any) (* CVC5 ONLY *) (* set of set items *)

(* The heap itself is a map from references to
   items that reside in the heap. *)
heap ::= reference -> heapItem

(* The class type is simply an enum of all classes
   found in the Python input file. *)
class ::=
    | PythonClassFoo
    | PythonClassBar
    | PythonClassBaz
    | ...
```
