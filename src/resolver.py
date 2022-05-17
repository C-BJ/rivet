# Copyright (C) 2022 The Rivet Team. All rights reserved.
# Use of this source code is governed by an MIT license
# that can be found in the LICENSE file.

from .token import Kind
from .ast import sym, type
from .ast.sym import Visibility
from . import ast, report, register, utils

class Resolver:
    def __init__(self, comp):
        self.comp = comp
        self.cur_sym = None

        self.inside_is_comparation = False

        self.self_sym = None

    def resolve_files(self, source_files):
        register.Register(self.comp).visit_source_files(source_files)
        if report.ERRORS > 0:
            return

        self.cur_sym = self.comp.pkg_sym
        for sf in source_files:
            self.resolve_file(sf)

    def resolve_file(self, sf):
        self.resolve_decls(sf.decls)

    def resolve_decls(self, decls):
        for decl in decls:
            self.resolve_decl(decl)

    def resolve_decl(self, decl):
        should_check = True
        if not decl.__class__ in (
            ast.TestDecl, ast.ExternPkg, ast.DestructorDecl
        ):
            should_check = decl.attrs.if_check
        if isinstance(decl, ast.ExternDecl):
            if should_check:
                self.resolve_decls(decl.protos)
        elif isinstance(decl, ast.ConstDecl):
            if should_check:
                self.resolve_type(decl.typ)
                self.resolve_expr(decl.expr)
        elif isinstance(decl, ast.StaticDecl):
            if should_check:
                self.resolve_type(decl.typ)
                self.resolve_expr(decl.expr)
        elif isinstance(decl, ast.ModDecl):
            if should_check:
                old_sym = self.cur_sym
                self.cur_sym = decl.sym
                self.resolve_decls(decl.decls)
                self.cur_sym = old_sym
        elif isinstance(decl, ast.TypeDecl):
            if should_check:
                self.resolve_type(decl.parent)
        elif isinstance(decl, ast.TraitDecl):
            if should_check:
                self.resolve_decls(decl.decls)
        elif isinstance(decl, ast.UnionDecl):
            if should_check:
                self.self_sym = decl.sym
                for v in decl.variants:
                    self.resolve_type(v)
                self.resolve_decls(decl.decls)
                self.self_sym = None
        elif isinstance(decl, ast.EnumDecl):
            if should_check:
                self.self_sym = decl.sym
                self.resolve_decls(decl.decls)
                self.self_sym = None
        elif isinstance(decl, ast.StructDecl):
            if should_check:
                self.self_sym = decl.sym
                self.resolve_decls(decl.decls)
                self.self_sym = None
        elif isinstance(decl, ast.StructField):
            if should_check:
                self.resolve_type(decl.typ)
                if decl.has_def_expr:
                    self.resolve_expr(decl.def_expr)
        elif isinstance(decl, ast.ExtendDecl):
            if should_check:
                if self.resolve_type(decl.typ):
                    self.self_sym = decl.typ.get_sym()
                    if isinstance(
                        decl.typ, (type.Array, type.Slice, type.Tuple)
                    ):
                        # TODO(StunxFS): better error messages
                        s = decl.typ.get_sym()
                        for d in decl.decls:
                            if isinstance(d, ast.FnDecl):
                                if d.is_method:
                                    self_typ = type.Type(self.self_sym)
                                    if d.self_is_ref:
                                        self_typ = type.Ref(self_typ)
                                    if not d.scope.exists("self"):
                                        d.scope.add(
                                            sym.Object(
                                                d.self_is_mut, "self", self_typ,
                                                True
                                            )
                                        )
                                    try:
                                        d.sym = sym.Fn(
                                            sym.ABI.Rivet, d.vis, d.is_extern,
                                            d.is_unsafe, d.is_method, d.name,
                                            d.args, d.ret_is_mut, d.ret_typ,
                                            d.has_named_args
                                        )
                                        s.add(d.sym)
                                    except utils.CompilerError as e:
                                        report.error(e.args[0], d.name_pos)
                                else:
                                    report.error("expected method", d.name_pos)
                            else:
                                report.error("expected method", d.pos)
                    self.resolve_decls(decl.decls)
                    self.self_sym = None
        elif isinstance(decl, ast.TestDecl):
            self.resolve_stmts(decl.stmts)
        elif isinstance(decl, ast.FnDecl):
            if should_check:
                for arg in decl.args:
                    self.resolve_type(arg.typ)
                    if arg.has_def_expr: self.resolve_expr(arg.def_expr)
                self.resolve_type(decl.ret_typ)
                self.resolve_stmts(decl.stmts)
        elif isinstance(decl, ast.DestructorDecl):
            self.resolve_stmts(decl.stmts)

    def resolve_stmts(self, stmts):
        for stmt in stmts:
            self.resolve_stmt(stmt)

    def resolve_stmt(self, stmt):
        if isinstance(stmt, ast.LetStmt):
            for l in stmt.lefts:
                self.resolve_type(l.typ)
            self.resolve_expr(stmt.right)
        elif isinstance(stmt, ast.AssignStmt):
            self.resolve_expr(stmt.left)
            self.resolve_expr(stmt.right)
        elif isinstance(stmt, ast.ExprStmt):
            self.resolve_expr(stmt.expr)
        elif isinstance(stmt, ast.WhileStmt):
            self.resolve_expr(stmt.cond)
            self.resolve_stmt(stmt.stmt)
        elif isinstance(stmt, ast.ForInStmt):
            self.resolve_expr(stmt.iterable)
            self.resolve_stmt(stmt.stmt)

    def resolve_expr(self, expr):
        if isinstance(expr, ast.ParExpr):
            self.resolve_expr(expr.expr)
        elif isinstance(expr, ast.Ident):
            if expr.name == "_":
                return # ignore special var
            elif expr.is_comptime:
                if not ast.is_known_comptime_constant(expr.name):
                    report.error(
                        f"unknown comptime constant `{expr.name}`", expr.pos
                    )
            elif obj := expr.scope.lookup(expr.name):
                if isinstance(obj, sym.Label):
                    report.error("expected value, found label", expr.pos)
                else:
                    expr.is_obj = True
                    expr.obj = obj
                    expr.typ = obj.typ
            elif s := self.cur_sym.lookup(expr.name):
                expr.sym = s
            else:
                report.error(
                    f"cannot find `{expr.name}` in this scope", expr.pos
                )
        elif isinstance(expr, ast.SelfExpr):
            if self_ := expr.scope.lookup("self"):
                expr.typ = self_.typ
            else:
                report.error(f"cannot find `self` in this scope", expr.pos)
        elif isinstance(expr, ast.SelfTyExpr):
            if self.self_sym != None:
                expr.typ = type.Type(self.self_sym)
            else:
                report.error(f"cannot resolve type for `Self`", expr.pos)
        elif isinstance(expr, ast.TypeNode):
            self.resolve_type(expr.typ)
        elif isinstance(expr, ast.TupleLiteral):
            for e in expr.exprs:
                self.resolve_expr(e)
        elif isinstance(expr, ast.ArrayLiteral):
            for e in expr.elems:
                self.resolve_expr(e)
        elif isinstance(expr, ast.StructLiteral):
            self.resolve_expr(expr.expr)
            for f in expr.fields:
                self.resolve_expr(f.expr)
        elif isinstance(expr, ast.UnaryExpr):
            self.resolve_expr(expr.right)
        elif isinstance(expr, ast.BinaryExpr):
            self.inside_is_comparation = expr.op in (Kind.KeyNotIs, Kind.KeyIs)
            self.resolve_expr(expr.left)
            self.resolve_expr(expr.right)
        elif isinstance(expr, ast.PostfixExpr):
            self.resolve_expr(expr.left)
        elif isinstance(expr, ast.CastExpr):
            self.resolve_expr(expr.expr)
        elif isinstance(expr, ast.IndexExpr):
            self.resolve_expr(expr.left)
            self.resolve_expr(expr.index)
        elif isinstance(expr, ast.RangeExpr):
            if expr.has_start: self.resolve_expr(expr.start)
            if expr.has_end: self.resolve_expr(expr.end)
        elif isinstance(expr, ast.SelectorExpr):
            self.resolve_expr(expr.left)
        elif isinstance(expr, ast.PathExpr):
            self.resolve_path_expr(expr)
        elif isinstance(expr, ast.BuiltinCallExpr):
            for a in expr.args:
                self.resolve_expr(a)
        elif isinstance(expr, ast.CallExpr):
            self.resolve_expr(expr.left)
            for a in expr.args:
                self.resolve_expr(a.expr)
            if expr.has_err_handler():
                self.resolve_expr(expr.err_handler.expr)
        elif isinstance(expr, ast.ReturnExpr):
            self.resolve_expr(expr.expr)
        elif isinstance(expr, ast.RaiseExpr):
            self.resolve_expr(expr.expr)
        elif isinstance(expr, ast.Block):
            for stmt in expr.stmts:
                self.resolve_stmt(stmt)
            if expr.is_expr: self.resolve_expr(expr.expr)
        elif isinstance(expr, ast.IfExpr):
            if expr.is_comptime:
                if expr.branch_idx > -1:
                    self.resolve_expr(expr.branches[expr.branch_idx].expr)
            else:
                for b in expr.branches:
                    if not b.is_else: self.resolve_expr(b.cond)
                    self.resolve_expr(b.expr)
        elif isinstance(expr, ast.MatchExpr):
            self.resolve_expr(expr.expr)
            for b in expr.branches:
                for p in b.pats:
                    self.resolve_expr(p)
                self.resolve_expr(b.expr)

    def find_symbol(self, symbol, name, pos):
        if s := symbol.lookup(name):
            self.check_visibility(s, pos)
            return s
        elif isinstance(symbol, sym.Type) and symbol.kind == sym.TypeKind.Enum:
            if name in symbol.info.variants:
                return s
            else:
                report.error(
                    f"enum `{symbol.name}` has no variant `{name}`", pos
                )
                return None
        report.error(
            f"could not find `{name}` in {symbol.sym_kind()} `{symbol.name}`",
            pos
        )
        return None

    def resolve_path_expr(self, path):
        if isinstance(path.left, ast.PkgExpr):
            path.left_info = self.comp.pkg_sym
            if field_info := self.find_symbol(
                self.comp.pkg_sym, path.field_name, path.field_pos
            ):
                path.field_info = field_info
            else:
                path.has_error = True
        elif isinstance(path.left, ast.Ident):
            if local_sym := self.cur_sym.lookup(path.left.name):
                path.left_info = local_sym
                if field_info := self.find_symbol(
                    local_sym, path.field_name, path.field_pos
                ):
                    path.field_info = field_info
                else:
                    path.has_error = True
            elif package := self.comp.universe.lookup(path.left.name):
                path.left_info = package
                # external package?
                if field_info := self.find_symbol(
                    package, path.field_name, path.field_pos
                ):
                    path.field_info = field_info
                else:
                    path.has_error = True
            else:
                report.error(
                    f"use of undeclared external package `{path.left.name}`",
                    path.left.pos
                )
                path.has_error = True
        elif isinstance(path.left, ast.PathExpr):
            self.resolve_expr(path.left)
            if not path.left.has_error:
                path.left_info = path.left.field_info
                if field_info := self.find_symbol(
                    path.left.field_info, path.field_name, path.field_pos
                ):
                    path.field_info = field_info
                else:
                    path.has_error = True
        else:
            report.error("bad use of path expression", path.pos)
            path.has_error = True

    def check_visibility(self, sym, pos):
        if sym.vis == Visibility.Private and sym.parent != self.cur_sym:
            report.error(f"{sym.sym_kind()} `{sym.name}` is private", pos)

    def disallow_errtype_use(self, kind, pos):
        if (not self.inside_is_comparation) and kind == sym.TypeKind.ErrType:
            report.error("cannot use error type as a normal type", pos)
            report.note(
                "only inside `raise` statement or `is` comparation can be used"
            )

    def resolve_type(self, typ):
        if isinstance(typ, type.Ref):
            return self.resolve_type(typ.typ)
        elif isinstance(typ, type.Ptr):
            return self.resolve_type(typ.typ)
        elif isinstance(typ, type.Slice):
            if self.resolve_type(typ.typ):
                typ.resolve(self.comp.universe.add_or_get_slice(typ.typ))
                return True
        elif isinstance(typ, type.Array):
            if self.resolve_type(typ.typ):
                typ.resolve(
                    self.comp.universe.add_or_get_array(typ.typ, typ.size)
                )
                return True
        elif isinstance(typ, type.Tuple):
            res = False
            for t in typ.types:
                res = self.resolve_type(t)
            typ.resolve(self.comp.universe.add_or_get_tuple(typ.types))
            return res
        elif isinstance(typ, type.Fn):
            res = False
            for arg in typ.args:
                res = self.resolve_type(arg.typ)
            res = self.resolve_type(typ.ret_typ)
            return res
        elif isinstance(typ, type.Optional):
            return self.resolve_type(typ.typ)
        elif isinstance(typ, type.Result):
            return self.resolve_type(typ.typ)
        elif isinstance(typ, type.Type):
            if typ.is_resolved():
                return True # resolved
            if isinstance(typ.expr, ast.Ident):
                if s := self.cur_sym.lookup(typ.expr.name):
                    if isinstance(s, sym.Type):
                        pos = typ.expr.pos
                        typ.resolve(s)
                        if s.kind == sym.TypeKind.Alias: # unalias
                            if self.resolve_type(s.info.parent):
                                typ.unalias()
                        self.disallow_errtype_use(s.kind, pos)
                        return True
                    else:
                        report.error(
                            f"expected type, found {s.sym_kind()}", typ.expr.pos
                        )
                else:
                    report.error(
                        f"cannot find type `{typ.expr.name}` in this scope",
                        typ.expr.pos
                    )
            elif isinstance(typ.expr, ast.PathExpr):
                self.resolve_path_expr(typ.expr)
                if not typ.expr.has_error:
                    if isinstance(typ.expr.field_info, sym.Type):
                        pos = typ.expr.pos
                        typ.resolve(typ.expr.field_info)
                        if typ.expr.field_info.kind == sym.TypeKind.Alias: # unalias
                            if self.resolve_type(
                                typ.expr.field_info.info.parent
                            ):
                                typ.unalias()
                        self.disallow_errtype_use(typ.expr.field_info.kind, pos)
                        return True
                    else:
                        report.error(
                            f"expected type, found {typ.expr.field_info.sym_kind()}",
                            typ.expr.pos
                        )
            elif isinstance(typ.expr, ast.SelfTyExpr):
                if self.self_sym != None:
                    typ.resolve(self.self_sym)
                else:
                    report.error(
                        f"cannot resolve type for `Self`", typ.expr.pos
                    )
            else:
                report.error(f"expected type, found {typ.expr}", typ.expr.pos)
        return False
