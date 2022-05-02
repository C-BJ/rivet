# Copyright (C) 2022 The Rivet Team. All rights reserved.
# Use of this source code is governed by an MIT license
# that can be found in the LICENSE file.

from . import type

class SourceFile:
    def __init__(self, file, decls):
        self.file = file
        self.decls = decls

# ---- Declarations ----
class EmptyDecl:
    pass

class Attr:
    def __init__(self, name, pos):
        self.name = name
        self.pos = pos

class Attrs:
    def __init__(self):
        self.attrs = []

    def add(self, attr):
        self.attrs.append(attr)

    def lookup(self, name):
        for attr in self.attrs:
            if attr.name == name:
                return attr
        return None

class ExternPkg:
    def __init__(self, pkg_name, pos):
        self.pkg_name = pkg_name
        self.pos = pos

class ModDecl:
    def __init__(self, name, is_pub, decls, pos):
        self.name = name
        self.is_pub = is_pub
        self.decls = decls
        self.pos = pos

# ------ Statements --------
class ExprStmt:
    def __init__(self, expr, pos):
        self.expr = expr
        self.pos = pos

# ------ Expressions -------
class EmptyExpr:
    def __init__(self, pos):
        self.pos = pos

    def __repr__(self):
        return f"<rivet.EmptyExpr pos={self.pos}>"

    def __str__(self):
        return self.__repr__()

class Block:
    def __init__(self, stmts, expr, is_expr, pos):
        self.stmts = stmts
        self.expr = expr
        self.is_expr = is_expr
        self.typ = None
        self.pos = pos

    def __repr__(self):
        if len(self.stmts) == 0:
            if self.is_expr:
                return f"{{ {self.expr} }}"
            else:
                return "{}"
        return f"{{ {'; '.join([str(s) for s in self.stmts])}; {self.expr} }}"

    def __str__(self):
        return self.__repr__()

class TypeNode:
    def __init__(self, typ, pos):
        self.typ = typ
        self.pos = pos

    def __repr__(self):
        return "{self.ty}"

    def __str__(self):
        return self.__repr__()

class Ident:
    def __init__(self, name, pos, scope):
        self.name = name
        self.pos = pos
        self.ty = None
        self.scope = scope

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.__repr__()

class EnumVariantExpr:
    def __init__(self, variant, pos):
        self.variant = variant
        self.pos = pos
        self.ty = None

    def __repr__(self):
        return f".{self.name}"

    def __str__(self):
        return self.__repr__()

class NoneLiteral:
    def __init__(self, pos):
        self.pos = pos
        self.typ = None

    def __repr__(self):
        return "none"

    def __str__(self):
        return self.__repr__()

class BoolLiteral:
    def __init__(self, lit, pos):
        self.lit = lit
        self.pos = pos
        self.typ = None

    def __repr__(self):
        return "true" if self.lit else "false"

    def __str__(self):
        return self.__repr__()

class CharLiteral:
    def __init__(self, lit, pos, is_byte=False):
        self.lit = lit
        self.pos = pos
        self.is_byte = is_byte
        self.typ = None

    def __repr__(self):
        p = "b" if self.is_byte else ""
        return f"{p}'{self.lit}'"

    def __str__(self):
        return self.__repr__()

class IntegerLiteral:
    def __init__(self, lit, pos):
        self.lit = lit
        self.pos = pos

    def __repr__(self):
        return self.lit

    def __str__(self):
        return self.__repr__()

class FloatLiteral:
    def __init__(self, lit, pos):
        self.lit = lit
        self.pos = pos

    def __repr__(self):
        return self.lit

    def __str__(self):
        return self.__repr__()

class StringLiteral:
    def __init__(self, lit, is_raw, is_bytestr, pos):
        self.lit = lit
        self.is_raw = is_raw
        self.is_bytestr = is_bytestr
        self.pos = pos
        self.typ = None

    def __repr__(self):
        p = "b" if self.is_bytestr else "r" if self.is_raw else ""
        return f'{p}"{self.lit}"'

    def __str__(self):
        return self.__repr__()

class TupleLiteral:
    def __init__(self, exprs, pos):
        self.exprs = exprs
        self.typ = None
        self.pos = pos

    def __repr__(self):
        return f"({', '.join([str(e) for e in self.exprs])})"

    def __str__(self):
        return self.__repr__()

class StructLiteral:
    def __init__(self, expr, fields, pos):
        self.expr = expr
        self.fields = fields
        self.typ = None
        self.field_types = {}
        self.pos = pos

class ArrayLiteral:
    def __init__(self, elem_ty, elems, size, pos):
        self.elem_ty = elem_ty
        self.elems = elems
        self.size = size
        self.typ = None
        self.pos = pos

    def __repr__(self):
        if len(self.elems) == 0:
            return f"[{self.elem_ty}; {self.size}]{{}}"
        return f"[{self.elem_ty}; {self.size}]{{ {', '.join([str(e) for e in self.elems])} }}"

    def __str__(self):
        return self.__repr__()

class GoExpr:
    def __init__(self, expr, pos):
        self.expr = expr
        self.pos = pos
        self.typ = None

    def __repr__(self):
        return f"go {self.expr}"

    def __str__(self):
        return self.__repr__()

class SelfExpr:
    def __init__(self, scope, pos):
        self.scope = scope
        self.pos = pos

    def __repr__(self):
        return "self"

    def __str__(self):
        return self.__repr__()

class CastExpr:
    def __init__(self, expr, typ, pos):
        self.expr = expr
        self.typ = typ
        self.pos = pos

    def __repr__(self):
        return f"cast({self.expr}, {self.ty})"

    def __str__(self):
        return self.__repr__()

class UnsafeExpr:
    def __init__(self, expr, pos, typ=None):
        self.expr = expr
        self.typ = typ
        self.pos = pos

    def __repr__(self):
        return f"unsafe {{ {self.expr} }}"

    def __str__(self):
        return self.__repr__()

class NoneCheckExpr:
    def __init__(self, expr, pos, typ=None):
        self.expr = expr
        self.typ = typ
        self.pos = pos

    def __repr__(self):
        return f"{self.expr}.?"

    def __str__(self):
        return self.__repr__()

class IndirectExpr:
    def __init__(self, expr, pos, typ=None):
        self.expr = expr
        self.typ = typ
        self.pos = pos

    def __repr__(self):
        return f"{self.expr}.*"

    def __str__(self):
        return self.__repr__()

class GuardExpr:
    # if (let x = optional_or_result_fn()) { ... }
    # if (let x = "".split(", "); x.len > 5) { ... }
    def __init__(self, ident, is_mut, expr, pos):
        self.ident = ident
        self.is_mut = is_mut
        self.expr = expr
        self.pos = pos

    def __repr__(self):
        kmut = "mut" if self.is_mut else ""
        return f"let {kmut} {self.ident} = {self.expr}"

    def __str__(self):
        return self.__repr__()

class IfBranch:
    def __init__(self, cond, expr, is_else):
        self.cond = cond
        self.expr = expr
        self.is_else = is_else

class IfExpr:
    def __init__(self, branches, pos):
        self.branches = branches
        self.pos = pos
        self.typ = None

class UnaryExpr:
    def __init__(self, right, op, pos=None):
        self.right = right
        self.op = op
        self.pos = pos
        self.typ = None

    def __repr__(self):
        return f"{self.op}{self.right}"

    def __str__(self):
        return self.__repr__()

class BinaryExpr:
    def __init__(self, left, op, right, pos=None):
        self.left = left
        self.op = op
        self.right = right
        self.pos = pos
        self.typ = None

    def __repr__(self):
        return f"{self.left} {self.op} {self.right}"

    def __str__(self):
        return self.__repr__()

class PostfixExpr:
    def __init__(self, left, op, pos=None):
        self.left = left
        self.op = op
        self.pos = pos
        self.typ = None

    def __repr__(self):
        return f"{self.left}{self.op}"

    def __str__(self):
        return self.__repr__()

class ParExpr:
    def __init__(self, expr, pos):
        self.expr = expr
        self.typ = None
        self.pos = pos

    def __repr__(self):
        return f"({self.expr})"

class IndexExpr:
    def __init__(self, left, index, pos):
        self.left = left
        self.index = index
        self.left_typ = None
        self.typ = None
        self.pos = pos

    def __repr__(self):
        return f"{self.left}[{self.index}]"

    def __str__(self):
        return self.__repr__()

class CallExpr:
    def __init__(self, left, args, pos):
        self.left = left
        self.args = args
        self.pos = pos
        self.typ = None
        self.info = None

    def get_named_arg(self, name):
        for arg in self.args:
            if arg.is_named and arg.name == name:
                return arg
        return None

    # Returns the number of pure arguments, that is, not named, that
    # this call has.
    def pure_args_count(self):
        l = 0
        for arg in self.args:
            if not arg.is_named:
                l += 1
        return l

    def __repr__(self):
        return f"{self.left}({', '.join([str(a) for a in self.args])})"

    def __str__(self):
        return self.__repr__()

class CallArg:
    def __init__(self, expr, pos, name=""):
        self.expr = expr
        self.pos = pos
        self.name = name
        self.is_named = name != ""

    def __repr__(self):
        return (f"{self.name}: " if self.is_named else "") + f"{self.expr}"

    def __str__(self):
        return self.__repr__()

class RangeExpr:
    def __init__(
        self, start, end, is_inclusive, pos, has_start=True, has_end=True
    ):
        self.start = start
        self.end = end
        self.is_inclusive = is_inclusive
        self.has_start = has_start
        self.has_end = has_end
        self.pos = pos
        self.typ = None

    def __repr__(self):
        sep = "=" if self.is_inclusive else ""
        return f"{self.start}..{sep}{self.end}"

    def __str__(self):
        return self.__repr__()

class BuiltinCallExpr:
    def __init__(self, left, args, pos):
        self.left = left
        self.args = args
        self.typ = None
        self.pos = pos

    def __repr__(self):
        return f"{self.left}!({', '.join([str(a) for a in self.args])})"

    def __str__(self):
        return self.__repr__()

class SelectorExpr:
    def __init__(self, left, field_name, pos):
        self.left = left
        self.field_name = field_name
        self.field_info = None
        self.left_typ = None
        self.typ = None
        self.pos = pos

    def __repr__(self):
        return f"{self.left}.{self.field_name}"

    def __str__(self):
        return self.__repr__()

class PathExpr:
    def __init__(self, left, field_name, pos):
        self.left = left
        self.field_name = field_name
        self.field_info = None
        self.left_typ = None
        self.typ = None
        self.is_last = False
        self.pos = pos

    def __repr__(self):
        return f"{self.left}::{self.field_name}"

    def __str__(self):
        return self.__repr__()

class TryExpr:
    def __init__(self, expr, pos):
        self.expr = expr
        self.pos = pos

    def __repr__(self):
        return f"try {self.expr}"

    def __str__(self):
        return self.__repr__()
