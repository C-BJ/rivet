# Copyright (C) 2022 The Rivet Team. All rights reserved.
# Use of this source code is governed by an MIT license
# that can be found in the LICENSE file.

from .ast import sym, type
from .lexer import Lexer
from .tokens import Kind
from . import report, tokens, ast

class Parser:
    def __init__(self, comp):
        self.comp = comp
        self.lexer = None

        self.prev_tok = None
        self.tok = None
        self.peek_tok = None

        self.scope = None

        # This field is `true` when we are in a root module, that is,
        # a package.
        self.is_pkg_level = False

        self.inside_extern = False
        self.inside_struct_decl = False
        self.inside_block = False
        self.inside_trait = False

    def parse_pkg(self):
        self.is_pkg_level = True
        return self.parse_module_files()

    def parse_module_files(self):
        source_files = []
        for input in self.comp.prefs.inputs:
            source_files.append(self.parse_file(input))
        return source_files

    def parse_file(self, file):
        self.lexer = Lexer.from_file(file)
        if report.ERRORS > 0:
            return ast.SourceFile(file, [])
        self.advance(2)
        return ast.SourceFile(file, self.parse_decls())

    # ---- useful functions for working with tokens ----
    def next(self):
        self.prev_tok = self.tok
        self.tok = self.peek_tok
        self.peek_tok = self.lexer.next()

    def peek_token(self, n):
        return self.lexer.peek_token(n - 2)

    def advance(self, n):
        for _ in range(n):
            self.next()

    def accept(self, kind):
        if self.tok.kind == kind:
            self.next()
            return True
        return False

    def expect(self, kind):
        if self.accept(kind):
            return
        kstr = str(kind)
        if tokens.is_key(kstr) or (len(kstr) > 0 and not kstr[0].isalpha()):
            kstr = f"`{kstr}`"
        report.error(f"expected {kstr}, found {self.tok} ", self.tok.pos)
        self.next()

    # ---- utilities ------------------
    def parse_name(self):
        lit = self.tok.lit
        self.expect(Kind.Name)
        return lit

    # ---- declarations --------------
    def parse_decls(self):
        decls = []
        while self.tok.kind != Kind.EOF:
            decls.append(self.parse_decl())
        return decls

    def parse_doc_comment(self):
        pos = self.tok.pos
        lines = []
        while self.accept(Kind.DocComment):
            lines.append(self.prev_tok.lit)
        return ast.DocComment(lines, pos)

    def parse_attrs(self):
        attrs = ast.Attrs()
        while self.accept(Kind.Hash):
            self.expect(Kind.Lbracket)
            while True:
                pos = self.tok.pos
                if self.accept(Kind.KeyIf):
                    self.expect(Kind.Lparen)
                    cond = self.parse_expr()
                    self.expect(Kind.Rparen)
                    attrs.add(ast.Attr("if", pos, cond, True))
                else:
                    attrs.add(ast.Attr(self.parse_name(), pos))
                if not self.accept(Kind.Semicolon):
                    break
            self.expect(Kind.Rbracket)
        return attrs

    def parse_vis(self):
        if self.accept(Kind.KeyPub):
            if self.accept(Kind.Lparen):
                self.expect(Kind.KeyPkg)
                self.expect(Kind.Rparen)
                return ast.Visibility.PublicInPkg
            return ast.Visibility.Public
        return ast.Visibility.Private

    def parse_decl(self):
        doc_comment = self.parse_doc_comment()
        attrs = self.parse_attrs()
        vis = self.parse_vis()
        is_unsafe = self.accept(Kind.KeyUnsafe)
        pos = self.tok.pos
        if self.accept(Kind.KeyExtern):
            if self.inside_extern:
                report.error("`extern` declarations cannot be nested", pos)
            elif vis.is_pub():
                report.error(
                    "`extern` declarations cannot be declared public", pos
                )
            elif is_unsafe:
                report.error(
                    "`extern` declarations cannot be declared unsafe", pos
                )
            elif not self.is_pkg_level:
                report.error(
                    "extern packages or functions can only be declared at the package level",
                    pos,
                )
            self.inside_extern = True
            if self.accept(Kind.KeyPkg):
                # extern package
                extern_pkg = self.parse_name()
                self.expect(Kind.Semicolon)
                decl = ast.ExternPkg(extern_pkg, pos)
            else:
                # extern function
                abi = self.parse_string_literal()
                protos = []
                if self.accept(Kind.Lbrace):
                    while not self.accept(Kind.Rbrace):
                        self.expect(Kind.KeyFn)
                        protos.append(
                            self.parse_fn_decl(doc_comment, attrs, True, True)
                        )
                        self.expect(Kind.Semicolon)
                else:
                    self.expect(Kind.KeyFn)
                    protos.append(
                        self.parse_fn_decl(doc_comment, attrs, True, True)
                    )
                    self.expect(Kind.Semicolon)
                decl = ast.ExternDecl(abi, protos, pos)
            self.inside_extern = False
            return decl
        elif self.accept(Kind.KeyConst):
            pos = self.tok.pos
            if is_unsafe:
                report.error("constants cannot be declared unsafe", pos)
            name = self.parse_name()
            self.expect(Kind.Colon)
            typ = self.parse_type()
            self.expect(Kind.Assign)
            expr = self.parse_expr()
            self.expect(Kind.Semicolon)
            return ast.ConstDecl(vis, name, typ, expr)
        elif self.accept(Kind.KeyStatic):
            pos = self.tok.pos
            if is_unsafe:
                report.error("static values cannot be declared unsafe", pos)
            is_mut = self.accept(Kind.KeyMut)
            name = self.parse_name()
            self.expect(Kind.Colon)
            typ = self.parse_type()
            self.expect(Kind.Assign)
            expr = self.parse_expr()
            self.expect(Kind.Semicolon)
            return ast.StaticDecl(vis, is_mut, name, typ, expr)
        elif self.accept(Kind.KeyMod):
            pos = self.tok.pos
            if is_unsafe:
                report.error("modules cannot be declared unsafe", pos)
            name = self.parse_name()

            old_is_pkg_level = self.is_pkg_level
            self.is_pkg_level = False

            decls = []
            self.expect(Kind.Lbrace)
            while not self.accept(Kind.Rbrace):
                decls.append(self.parse_decl())

            self.is_pkg_level = old_is_pkg_level
            return ast.ModDecl(doc_comment, attrs, name, vis, decls, pos)
        elif self.accept(Kind.KeyType):
            pos = self.tok.pos
            if is_unsafe:
                report.error("type aliases cannot be declared unsafe", pos)
            name = self.parse_name()
            self.expect(Kind.Assign)
            parent = self.parse_type()
            self.expect(Kind.Semicolon)
            return ast.TypeDecl(vis, name, parent, pos)
        elif self.accept(Kind.KeyErrType):
            pos = self.tok.pos
            if is_unsafe:
                report.error("error types cannot be declared unsafe", pos)
            name = self.parse_name()
            self.expect(Kind.Semicolon)
            return ast.ErrTypeDecl(vis, name, pos)
        elif self.accept(Kind.KeyTrait):
            pos = self.tok.pos
            if is_unsafe:
                report.error("traits cannot be declared unsafe", pos)
            name = self.parse_name()
            decls = []
            old_inside_trait = self.inside_trait
            self.inside_trait = True
            self.expect(Kind.Lbrace)
            while not self.accept(Kind.Rbrace):
                doc_comment = self.parse_doc_comment()
                attrs_pos = self.tok.pos
                attrs = self.parse_attrs()
                if attrs.has_attrs():
                    report.error(
                        "attributes should be applied to a function or method",
                        attrs_pos
                    )
                if self.accept(Kind.KeyPub):
                    report.error(
                        "unnecessary visibility qualifier", self.prev_tok.pos
                    )
                is_unsafe = self.accept(Kind.KeyUnsafe)
                self.expect(Kind.KeyFn)
                decls.append(
                    self.parse_fn_decl(
                        doc_comment, attrs, ast.Visibility.Public, is_unsafe
                    )
                )
            self.inside_trait = old_inside_trait
            return ast.TraitDecl(vis, name, decls, pos)
        elif self.accept(Kind.KeyUnion):
            pos = self.tok.pos
            if is_unsafe:
                report.error("unions cannot be declared unsafe", pos)
            name = self.parse_name()
            self.expect(Kind.Lbrace)
            variants = []
            while True:
                variants.append(self.parse_type())
                if not self.accept(Kind.Comma):
                    break
            decls = []
            if self.accept(Kind.Semicolon):
                # declarations: methods, consts, etc.
                while self.tok.kind != Kind.Rbrace:
                    decls.append(self.parse_decl())
            self.expect(Kind.Rbrace)
            return ast.UnionDecl(vis, name, variants, decls, pos)
        elif self.accept(Kind.KeyStruct):
            old_inside_struct_decl = self.inside_struct_decl
            self.inside_struct_decl = True
            pos = self.tok.pos
            if is_unsafe:
                report.error("structs cannot be declared unsafe", pos)
            name = self.parse_name()
            self.expect(Kind.Lbrace)
            decls = []
            if self.tok.kind != Kind.Rbrace:
                while self.tok.kind != Kind.Rbrace:
                    if self.accept(Kind.BitNot):
                        # destructor
                        self.expect(Kind.KeySelf)
                        self.expect(Kind.Lbrace)
                        stmts = []
                        while not self.accept(Kind.Rbrace):
                            stmts.append(self.parse_stmt())
                        decls.append(ast.DestructorDecl(stmts))
                    else:
                        # declaration: methods, consts, etc.
                        decls.append(self.parse_decl())
            self.expect(Kind.Rbrace)
            self.inside_struct_decl = old_inside_struct_decl
            return ast.StructDecl(vis, name, decls, pos)
        elif self.inside_struct_decl and self.tok.kind in (
            Kind.KeyMut, Kind.Name
        ):
            # struct fields
            is_mut = self.accept(Kind.KeyMut)
            name = self.parse_name()
            self.expect(Kind.Colon)
            typ = self.parse_type()
            has_def_expr = self.accept(Kind.Assign)
            def_expr = None
            if has_def_expr:
                def_expr = self.parse_expr()
            self.expect(Kind.Semicolon)
            return ast.StructField(
                vis.is_pub(), is_mut, name, typ, def_expr, has_def_expr
            )
        elif self.accept(Kind.KeyEnum):
            pos = self.tok.pos
            if is_unsafe:
                report.error("enums cannot be declared unsafe", pos)
            name = self.parse_name()
            self.expect(Kind.Lbrace)
            variants = []
            while True:
                variants.append(self.parse_name())
                if not self.accept(Kind.Comma):
                    break
            decls = []
            if self.accept(Kind.Semicolon):
                # declarations: methods, consts, etc.
                while self.tok.kind != Kind.Rbrace:
                    decls.append(self.parse_decl())
            self.expect(Kind.Rbrace)
            return ast.EnumDecl(vis, name, variants, decls, pos)
        elif self.accept(Kind.KeyExtend):
            if is_unsafe:
                report.error("`extend`s cannot be unsafe", self.prev_tok.pos)
            typ = self.parse_type()
            decls = []
            self.expect(Kind.Lbrace)
            while not self.accept(Kind.Rbrace):
                decls.append(self.parse_decl())
            return ast.ExtendDecl(typ, decls)
        elif self.accept(Kind.KeyFn):
            return self.parse_fn_decl(doc_comment, attrs, vis, is_unsafe)
        elif self.accept(Kind.KeyTest):
            name = self.tok.lit
            self.expect(Kind.String)
            stmts = []
            self.expect(Kind.Lbrace)
            while not self.accept(Kind.Rbrace):
                stmts.append(self.parse_stmt())
            return ast.TestDecl(name, stmts)
        else:
            report.error(f"expected declaration, found {self.tok}", pos)
            self.next()
        return ast.EmptyDecl()

    def parse_fn_decl(self, doc_comment, attrs, vis, is_unsafe):
        pos = self.tok.pos
        name = self.parse_name()

        args = []
        is_method = False
        self_is_ref = False
        self_is_mut = False
        self.expect(Kind.Lparen)
        if self.tok.kind != Kind.Rparen:
            # receiver (`self`|`&self`|`&mut self`)
            if self.tok.kind == Kind.KeySelf or (
                self.tok.kind == Kind.Amp and self.peek_tok.kind == Kind.KeySelf
            ) or (
                self.tok.kind == Kind.Amp and self.peek_tok.kind == Kind.KeyMut
                and self.peek_token(2).kind == Kind.KeySelf
            ):
                is_method = True
                self_is_ref = self.accept(Kind.Amp)
                self_is_mut = self.accept(Kind.KeyMut)
                self.expect(Kind.KeySelf)
                if self.tok.kind != Kind.Rparen:
                    self.expect(Kind.Comma)
            # arguments
            while self.tok.kind != Kind.Rparen:
                is_mut = self.accept(Kind.KeyMut)
                arg_name = self.parse_name()
                self.expect(Kind.Colon)
                arg_typ = self.parse_type()
                arg_expr = self.empty_expr()
                if self.accept(Kind.Assign):
                    arg_expr = self.parse_expr()
                args.append(
                    sym.Arg(
                        arg_name, is_mut, arg_typ, arg_expr,
                        not isinstance(arg_expr, ast.EmptyExpr)
                    )
                )
                if not self.accept(Kind.Comma):
                    break
        self.expect(Kind.Rparen)

        is_result = self.accept(Kind.Bang)
        ret_typ = self.parse_type()
        if is_result:
            ret_typ = type.Result(ret_typ)

        stmts = []
        has_body = True
        if self.tok.kind == Kind.Semicolon and self.inside_trait:
            has_body = False
            self.expect(Kind.Semicolon)
        else:
            if self.inside_extern:
                if self.tok.kind == Kind.Lbrace:
                    report.error("extern functions cannot have a body", pos)
                has_body = False
            else:
                self.expect(Kind.Lbrace)
                while not self.accept(Kind.Rbrace):
                    stmts.append(self.parse_stmt())

        return ast.FnDecl(
            doc_comment, attrs, vis, is_unsafe, name, args, ret_typ, stmts,
            has_body, is_method, self_is_ref, self_is_mut
        )

    # ---- statements --------------------------
    def parse_stmt(self):
        if self.tok.kind == Kind.Name and self.peek_tok.kind == Kind.Colon:
            pos = self.tok.pos
            label = self.parse_name()
            self.expect(Kind.Colon)
            return ast.LabelStmt(label, pos)
        elif self.tok.kind in (Kind.KeyUnsafe, Kind.Lbrace):
            pos = self.tok.pos
            is_unsafe = self.accept(Kind.KeyUnsafe)
            self.expect(Kind.Lbrace)
            stmts = []
            while not self.accept(Kind.Rbrace):
                stmts.append(self.parse_stmt())
            return ast.Block(is_unsafe, stmts, None, False, pos)
        elif self.accept(Kind.KeyLoop):
            return ast.LoopStmt(self.parse_stmt())
        elif self.accept(Kind.KeyWhile):
            self.expect(Kind.Lparen)
            cond = self.parse_expr()
            self.expect(Kind.Rparen)
            stmt = self.parse_stmt()
            return ast.WhileStmt(cond, stmt)
        elif self.accept(Kind.KeyFor):
            self.expect(Kind.Lparen)
            key = self.parse_name()
            if self.accept(Kind.Comma):
                value = self.parse_name()
            else:
                value = ""
            self.expect(Kind.KeyIn)
            iterable = self.parse_expr()
            self.expect(Kind.Rparen)
            stmt = self.parse_stmt()
            return ast.ForInStmt(key, value, iterable, stmt)
        elif self.accept(Kind.KeyGoto):
            pos = self.tok.pos
            label = self.parse_name()
            self.expect(Kind.Semicolon)
            return ast.GotoStmt(label, pos)
        elif self.tok.kind in (Kind.KeyContinue, Kind.KeyBreak):
            op = self.tok.kind
            pos = self.tok.pos
            self.next()
            self.expect(Kind.Semicolon)
            return ast.BranchStmt(op, pos)
        elif self.accept(Kind.KeyReturn):
            pos = self.prev_tok.pos
            has_expr = self.tok.kind != Kind.Semicolon
            if has_expr:
                expr = self.parse_expr()
            else:
                expr = self.empty_expr()
            self.expect(Kind.Semicolon)
            return ast.ReturnStmt(expr, has_expr, pos)
        elif self.accept(Kind.KeyRaise):
            pos = self.prev_tok.pos
            msg = self.parse_expr()
            self.expect(Kind.Semicolon)
            return ast.RaiseStmt(msg, pos)
        expr = self.parse_expr()
        if not (
            (self.inside_block and self.tok.kind == Kind.Rbrace)
            or expr.__class__ in (ast.IfExpr, ast.MatchExpr)
        ):
            self.expect(Kind.Semicolon)
        return ast.ExprStmt(expr, expr.pos)

    # ---- expressions -------------------------
    def parse_expr(self):
        return self.parse_or_expr()

    def parse_or_expr(self):
        left = self.parse_and_expr()
        while self.accept(Kind.KeyOr):
            right = self.parse_and_expr()
            left = ast.BinaryExpr(left, Kind.KeyOr, right, left.pos)
        return left

    def parse_and_expr(self):
        left = self.parse_equality_expr()
        while self.accept(Kind.KeyAnd):
            right = self.parse_equality_expr()
            left = ast.BinaryExpr(left, Kind.KeyAnd, right, left.pos)
        return left

    def parse_equality_expr(self):
        left = self.parse_relational_expr()
        if self.tok.kind in [Kind.Eq, Kind.Ne]:
            op = self.tok.kind
            self.next()
            right = self.parse_relational_expr()
            left = ast.BinaryExpr(left, op, right, left.pos)
        return left

    def parse_relational_expr(self):
        left = self.parse_shift_expr()
        if self.tok.kind in [
            Kind.Gt,
            Kind.Lt,
            Kind.Ge,
            Kind.Le,
            Kind.KeyIn,
            Kind.KeyNotIn,
        ]:
            op = self.tok.kind
            self.next()
            right = self.parse_shift_expr()
            left = ast.BinaryExpr(left, op, right, right.pos)
        elif self.tok.kind in [Kind.KeyIs, Kind.KeyNotIs]:
            op = self.tok.kind
            self.next()
            pos = self.tok.pos
            right = ast.TypeNode(self.parse_type(), pos)
            left = ast.BinaryExpr(left, op, right, pos)
        return left

    def parse_shift_expr(self):
        left = self.parse_additive_expr()
        if self.tok.kind in [Kind.Lt, Kind.Gt]:
            op = Kind.Lshift if self.tok.kind == Kind.Lt else Kind.Rshift
            if self.tok.pos.pos + 1 == self.peek_tok.pos.pos:
                self.next()
                self.next()
                right = self.parse_additive_expr()
                left = ast.BinaryExpr(left, op, right, left.pos)
        elif self.tok.kind in [Kind.Amp, Kind.Pipe, Kind.Xor]:
            op = self.tok.kind
            self.next()
            right = self.parse_additive_expr()
            left = ast.BinaryExpr(left, op, right, left.pos)
        return left

    def parse_additive_expr(self):
        left = self.parse_multiplicative_expr()
        if self.tok.kind in [Kind.Plus, Kind.Minus]:
            op = self.tok.kind
            self.next()
            right = self.parse_multiplicative_expr()
            left = ast.BinaryExpr(left, op, right, left.pos)
        return left

    def parse_multiplicative_expr(self):
        left = self.parse_unary_expr()
        if self.tok.kind in [Kind.Mult, Kind.Div, Kind.Mod]:
            op = self.tok.kind
            self.next()
            right = self.parse_unary_expr()
            left = ast.BinaryExpr(left, op, right, left.pos)
        return left

    def parse_unary_expr(self):
        expr = self.empty_expr()
        if (
            self.tok.kind in [
                Kind.Amp, Kind.Bang, Kind.BitNot, Kind.Inc, Kind.Dec, Kind.Minus
            ]
        ):
            op = self.tok.kind
            pos = self.tok.pos
            self.next()
            right = self.parse_unary_expr()
            expr = ast.UnaryExpr(right, op, right.pos)
        else:
            expr = self.parse_primary_expr()
        return expr

    def parse_primary_expr(self):
        expr = self.empty_expr()
        if self.tok.kind in [
            Kind.KeyTrue, Kind.KeyFalse, Kind.Char, Kind.Number, Kind.String,
            Kind.KeyNone, Kind.KeySelf, Kind.KeySelfTy
        ]:
            expr = self.parse_literal()
        elif self.accept(Kind.Dollar):
            # comptime expressions
            if self.tok.kind == Kind.KeyIf:
                expr = self.parse_if_expr(True)
            elif self.accept(Kind.KeyMatch):
                expr = self.parse_match_expr(True)
            else:
                expr = self.parse_ident(True)
        elif self.tok.kind == Kind.Dot and self.peek_tok.kind == Kind.Name:
            pos = self.tok.pos
            self.next()
            expr = ast.EnumVariantExpr(self.parse_name(), pos)
        elif self.tok.kind == Kind.KeyIf:
            expr = self.parse_if_expr(False)
        elif self.accept(Kind.KeyMatch):
            expr = self.parse_match_expr(False)
        elif self.tok.kind == Kind.Lparen:
            self.expect(Kind.Lparen)
            e = self.parse_expr()
            if self.accept(Kind.Comma): # tuple
                exprs = [e]
                while True:
                    exprs.append(self.parse_expr())
                    if not self.accept(Kind.Comma):
                        break
                self.expect(Kind.Rparen)
                if len(exprs) > 8:
                    report.error(
                        "tuples can have a maximum of 8 expressions", e.pos
                    )
                expr = ast.TupleLiteral(exprs, e.pos)
            else:
                self.expect(Kind.Rparen)
                expr = ast.ParExpr(e, e.pos)
        elif self.tok.kind in (Kind.KeyUnsafe, Kind.Lbrace):
            # block expression
            pos = self.tok.pos
            is_unsafe = self.accept(Kind.KeyUnsafe)
            self.expect(Kind.Lbrace)
            old_inside_block = self.inside_block
            self.inside_block = True
            stmts = []
            has_expr = False
            while not self.accept(Kind.Rbrace):
                stmt = self.parse_stmt()
                has_expr = isinstance(
                    stmt, ast.ExprStmt
                ) and self.prev_tok.kind != Kind.Semicolon
                stmts.append(stmt)
            if has_expr:
                expr = ast.Block(
                    is_unsafe, stmts[:-1], stmts[-1].expr, True, pos
                )
            else:
                expr = ast.Block(is_unsafe, stmts, None, False, pos)
            self.inside_block = old_inside_block
        elif self.accept(Kind.KeyCast):
            self.expect(Kind.Lparen)
            expr = self.parse_expr()
            self.expect(Kind.Comma)
            typ = self.parse_type()
            self.expect(Kind.Rparen)
            expr = ast.CastExpr(expr, expr.pos, typ)
        elif self.accept(Kind.KeyGo):
            pos = self.prev_tok.pos
            expr = ast.GoExpr(self.parse_expr(), pos)
        elif self.accept(Kind.KeyTry):
            pos = self.prev_tok.pos
            expr = ast.TryExpr(self.parse_expr(), pos)
        elif self.tok.kind == Kind.Lbracket:
            elems = []
            pos = self.tok.pos
            self.next()
            if self.tok.kind != Kind.Rbracket:
                while True:
                    elems.append(self.parse_expr())
                    if not self.accept(Kind.Comma):
                        break
            self.expect(Kind.Rbracket)
            expr = ast.ArrayLiteral(elems, pos)
        elif self.tok.kind == Kind.KeyPkg:
            expr = self.parse_pkg_expr()
        else:
            if self.tok.kind == Kind.Name and self.peek_tok.kind == Kind.Char:
                if self.tok.lit != "b":
                    report.error(
                        "only `b` is recognized as a valid prefix for a character literal",
                        self.tok.pos,
                    )
                else:
                    expr = self.parse_character_literal()
            elif self.tok.kind == Kind.Name and self.peek_tok.kind == Kind.String:
                if self.tok.lit not in ("b", "r"):
                    report.error(
                        "only `b` and `r` are recognized as valid prefixes for a string literal",
                        self.tok.pos,
                    )
                else:
                    expr = self.parse_string_literal()
            elif self.tok.kind == Kind.Name and self.peek_tok.kind == Kind.Bang: # builtin call
                name = self.parse_name()
                self.expect(Kind.Bang)
                self.expect(Kind.Lparen)
                args = []
                if name in ("sizeof", "default"):
                    pos = self.tok.pos
                    args.append(TypeNode(self.parse_type(), pos))
                elif self.tok.kind != Kind.Rparen:
                    while True:
                        args.append(self.parse_expr())
                        if not self.accept(Kind.Comma):
                            break
                self.expect(Kind.Rparen)
                expr = ast.BuiltinCallExpr(name, args, expr.pos)
            else:
                expr = self.parse_ident()
        while True:
            if self.accept(Kind.Lbrace):
                fields = {}
                if self.tok.kind != Kind.Rbrace:
                    while True:
                        key = self.parse_ident()
                        self.expect(Kind.Colon)
                        value = self.parse_expr()
                        fields[key] = value
                        if not self.accept(Kind.Comma):
                            break
                self.expect(Kind.Rbrace)
                expr = ast.StructLiteral(expr, fields, expr.pos)
            elif self.tok.kind in [Kind.Inc, Kind.Dec]:
                op = self.tok.kind
                self.next()
                expr = ast.PostfixExpr(expr, op, expr.pos)
            elif self.accept(Kind.Lparen):
                args = []
                if self.tok.kind != Kind.Rparen:
                    expecting_named_arg = False
                    while True:
                        if (
                            self.tok.kind == Kind.Name
                            and self.peek_tok.kind == Kind.Colon
                        ):
                            # named argument
                            name_p = self.tok.pos
                            name = self.parse_name()
                            self.expect(Kind.Colon)
                            expr2 = self.parse_expr()
                            args.append(ast.CallArg(expr2, name_p, name))
                            expecting_named_arg = True
                        else:
                            if expecting_named_arg:
                                report.error(
                                    "expected named argument, found expression",
                                    self.tok.pos
                                )
                            expr2 = self.parse_expr()
                            args.append(ast.CallArg(expr2, expr2.pos))
                        if not self.accept(Kind.Comma):
                            break
                self.expect(Kind.Rparen)
                varname = ""
                err_expr = None
                if self.accept(Kind.KeyCatch):
                    if self.accept(Kind.Pipe):
                        varname = self.parse_name()
                        self.expect(Kind.Pipe)
                    err_expr = self.parse_expr()
                expr = ast.CallExpr(
                    expr, args, ast.CallErrorHandler(varname, err_expr),
                    expr.pos
                )
            elif self.accept(Kind.Dot):
                if self.accept(Kind.Mult):
                    expr = ast.IndirectExpr(expr, expr.pos)
                elif self.accept(Kind.Question):
                    expr = ast.NoneCheckExpr(expr, expr.pos)
                else:
                    name = self.parse_name()
                    expr = ast.SelectorExpr(expr, name, expr.pos)
            elif self.tok.kind == Kind.DoubleColon:
                expr = self.parse_path_expr(expr)
            elif self.accept(Kind.Lbracket):
                index = self.empty_expr()
                if self.accept(Kind.DotDot):
                    index = self.parse_expr()
                    index = ast.RangeExpr(
                        None, index, False, index.pos, False, True
                    )
                else:
                    index = self.parse_expr()
                    if self.accept(Kind.DotDot):
                        if self.tok.kind != Kind.Rbracket:
                            index2 = self.parse_expr()
                            index = ast.RangeExpr(
                                index, index2, False, index.pos, True, True
                            )
                        else:
                            index = ast.RangeExpr(
                                index, None, False, index.pos, True, False
                            )
                self.expect(Kind.Rbracket)
                expr = ast.IndexExpr(expr, index, expr.pos)
            elif self.tok.kind == Kind.DotDot:
                self.next()
                is_inclusive = self.accept(Kind.Assign)
                end = self.parse_expr()
                expr = ast.RangeExpr(expr, end, is_inclusive, expr.pos)
            else:
                break
        return expr

    def parse_if_expr(self, is_comptime):
        branches = []
        pos = self.tok.pos
        while self.tok.kind in (Kind.KeyIf, Kind.KeyElif, Kind.KeyElse):
            if self.accept(Kind.KeyElse):
                branches.append(
                    ast.IfBranch(
                        is_comptime, self.empty_expr(), self.parse_expr(), True,
                        Kind.KeyElse
                    )
                )
                break
            else:
                op = self.tok.kind
                self.next()
                self.expect(Kind.Lparen)
                cond = self.parse_expr()
                self.expect(Kind.Rparen)
                branches.append(
                    ast.IfBranch(
                        is_comptime, cond, self.parse_expr(), False, op
                    )
                )
                if self.tok.kind not in (
                    Kind.Dollar, Kind.KeyElif, Kind.KeyElse
                ):
                    break
                if is_comptime:
                    self.expect(Kind.Dollar)
        return ast.IfExpr(is_comptime, branches, pos)

    def parse_match_expr(self, is_comptime):
        branches = []
        pos = self.prev_tok.pos
        self.expect(Kind.Lparen)
        expr = self.parse_expr()
        self.expect(Kind.Rparen)
        is_typematch = self.accept(Kind.KeyIs)
        self.expect(Kind.Lbrace)
        while True:
            pats = []
            is_else = self.accept(Kind.KeyElse)
            if not is_else:
                while True:
                    if is_typematch:
                        pats.append(self.parse_type())
                    else:
                        pats.append(self.parse_expr())
                    if not self.accept(Kind.Comma):
                        break
            self.expect(Kind.Arrow)
            branches.append(ast.MatchBranch(pats, self.parse_expr(), is_else))
            if not self.accept(Kind.Comma):
                break
        self.expect(Kind.Rbrace)
        return ast.MatchExpr(is_comptime, expr, branches, is_typematch, pos)

    def parse_path_expr(self, left):
        self.expect(Kind.DoubleColon)
        pos = self.tok.pos
        name = self.parse_name()
        expr = ast.PathExpr(left, name, pos)
        expr.is_last = self.tok.kind != Kind.DoubleColon
        return expr

    def parse_literal(self):
        if self.tok.kind in [Kind.KeyTrue, Kind.KeyFalse]:
            pos = self.tok.pos
            lit = self.tok.kind == Kind.KeyTrue
            self.next()
            return ast.BoolLiteral(lit, pos)
        elif self.tok.kind == Kind.Char:
            return self.parse_character_literal()
        elif self.tok.kind == Kind.Number:
            return self.parse_integer_literal()
        elif self.tok.kind == Kind.String:
            return self.parse_string_literal()
        elif self.accept(Kind.KeySelf):
            return ast.SelfExpr(self.scope, self.prev_tok.pos)
        elif self.accept(Kind.KeySelfTy):
            return ast.SelfTyExpr(self.scope, self.prev_tok.pos)
        elif self.accept(Kind.KeyNone):
            return ast.NoneLiteral(self.prev_tok.pos)
        else:
            report.error(f"expected literal, found {self.tok}", self.tok.pos)
        return self.empty_expr()

    def parse_integer_literal(self):
        pos = self.tok.pos
        lit = self.tok.lit
        is_float = "." in lit or "e" in lit or "E" in lit
        self.next()
        return (
            ast.FloatLiteral(lit, pos)
            if is_float else ast.IntegerLiteral(lit, pos)
        )

    def parse_character_literal(self):
        is_byte = False
        if self.tok.kind == Kind.Name:
            is_byte = self.tok.lit == "b"
            self.expect(Kind.Name)
        lit = self.tok.lit
        pos = self.tok.pos
        self.expect(Kind.Char)
        return ast.CharLiteral(lit, pos, is_byte)

    def parse_string_literal(self):
        is_bytestr = False
        is_raw = False
        if self.tok.kind == Kind.Name:
            is_raw = self.tok.lit == "r"
            is_bytestr = self.tok.lit == "b"
            self.expect(Kind.Name)
        lit = self.tok.lit
        pos = self.tok.pos
        self.expect(Kind.String)
        while self.accept(Kind.String):
            lit += self.prev_tok.lit
        return ast.StringLiteral(lit, is_raw, is_bytestr, pos)

    def parse_ident(self, is_comptime=False):
        pos = self.tok.pos
        name = self.parse_name()
        return ast.Ident(name, pos, self.scope, is_comptime)

    def parse_pkg_expr(self):
        pos = self.tok.pos
        self.next()
        return ast.PkgExpr(pos)

    def empty_expr(self):
        return ast.EmptyExpr(self.tok.pos)

    # ---- types -------------------------------
    def parse_type(self):
        pos = self.tok.pos
        if self.accept(Kind.Amp):
            # references
            typ = self.parse_type()
            if self.inside_extern:
                report.error(
                    "cannot use references inside `extern` blocks", pos
                )
                report.help(f"use pointers instead: `*{typ}`")
            elif isinstance(typ, type.Ref):
                report.error("multi-level references are not allowed", pos)
            elif isinstance(typ, type.Ptr):
                report.error("cannot use references with pointers", pos)
            return type.Ref(typ)
        elif self.accept(Kind.Mult):
            # pointers
            typ = self.parse_type()
            if isinstance(typ, type.Ref):
                report.error("cannot use pointers with references", pos)
            return type.Ptr(typ)
        elif self.accept(Kind.Lbracket):
            # arrays or slices
            typ = self.parse_type()
            if self.accept(Kind.Semicolon):
                size = self.parse_expr()
                self.expect(Kind.Rbracket)
                return type.Array(typ, size)
            self.expect(Kind.Rbracket)
            return type.Slice(typ)
        elif self.accept(Kind.Lparen):
            # tuples
            types = []
            while True:
                types.append(self.parse_type())
                if not self.accept(Kind.Comma):
                    break
            if len(types) > 8:
                report.error("tuples can have a maximum of 8 types", pos)
                report.help("you can use a struct instead")
            self.expect(Kind.Rparen)
            return type.Tuple(types)
        elif self.accept(Kind.Question):
            # optional
            typ = self.parse_type()
            if isinstance(typ, type.Ptr):
                report.error("pointers cannot be optional", pos)
                report.note("by default pointers can contain the value `none`")
            elif isinstance(typ, type.Optional):
                report.error("optional multi-level types are not allowed", pos)
            return type.Optional(typ)
        elif self.accept(Kind.KeySelfTy):
            return type.UnknownType(ast.SelfExpr(self.scope, self.prev_tok.pos))
        elif self.tok.kind in (Kind.KeyPkg, Kind.Name):
            # normal type
            if self.peek_tok.kind == Kind.DoubleColon:
                path_expr = self.parse_path_expr(
                    self.parse_pkg_expr() if self.tok.kind ==
                    Kind.KeyPkg else self.parse_ident()
                )
                if self.tok.kind == Kind.DoubleColon:
                    while True:
                        path_expr = self.parse_path_expr(path_expr)
                        if self.tok.kind != Kind.DoubleColon:
                            break
                return type.UnknownType(path_expr)
            elif self.tok.kind == Kind.Name:
                expr = self.parse_ident()
                lit = expr.name
                if lit == "c_void":
                    if not self.inside_extern:
                        self.error(
                            "`c_void` can only be used inside `extern` declarations",
                            pos
                        )
                    return self.comp.c_void_t
                elif lit == "void":
                    return self.comp.void_t
                elif lit == "ptr":
                    return self.comp.ptr_t
                elif lit == "bool":
                    return self.comp.bool_t
                elif lit == "rune":
                    return self.comp.rune_t
                elif lit == "i8":
                    return self.comp.int8_t
                elif lit == "i16":
                    return self.comp.int16_t
                elif lit == "i32":
                    return self.comp.int32_t
                elif lit == "i64":
                    return self.comp.int64_t
                elif lit == "isize":
                    return self.comp.isize_t
                elif lit == "u8":
                    return self.comp.uint8_t
                elif lit == "u16":
                    return self.comp.uint16_t
                elif lit == "u32":
                    return self.comp.uint32_t
                elif lit == "u64":
                    return self.comp.uint64_t
                elif lit == "usize":
                    return self.comp.usize_t
                elif lit == "f32":
                    return self.comp.float32_t
                elif lit == "f64":
                    return self.comp.float64_t
                elif lit == "str":
                    return self.comp.str_t
                else:
                    return type.UnknownType(expr)
            else:
                report.error(f"expected type, found keyword `pkg`", pos)
                self.next()
        else:
            report.error(f"expected type, found {self.tok}", pos)
            self.next()
        return type.UnknownType(self.empty_expr())
