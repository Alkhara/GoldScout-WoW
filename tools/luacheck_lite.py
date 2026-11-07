#!/usr/bin/env python3
"""Lua 5.1 syntax checker with a global-variable report, for WoW addon code.

Usage: python luacheck_lite.py file1.lua [file2.lua ...]

Parses each file with a recursive-descent parser that follows Lua 5.1's
grammar (lparser.c), including 5.1-only rules: no empty ';' statements,
'return'/'break' must end a block, and a '(' call on a new line is an
"ambiguous syntax" error. Prints syntax errors with line numbers, then the
global names each file reads and writes, so typos in API names stand out.
"""
import re
import sys
from collections import defaultdict

KEYWORDS = {
    "and", "break", "do", "else", "elseif", "end", "false", "for", "function",
    "if", "in", "local", "nil", "not", "or", "repeat", "return", "then",
    "true", "until", "while",
}
NUMBER_RE = re.compile(r"0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
MULTI_OPS = ("...", "..", "==", "~=", "<=", ">=")
SINGLE_OPS = set("+-*/%^#<>=(){}[];:,.")


class LuaSyntaxError(Exception):
    def __init__(self, message, line):
        super().__init__("line %d: %s" % (line, message))
        self.line = line


def tokenize(src):
    tokens = []
    i, n, line = 0, len(src), 1

    def long_bracket_level(pos):
        j = pos + 1
        while j < n and src[j] == "=":
            j += 1
        if j < n and src[j] == "[":
            return j - pos - 1
        return -1

    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r\f\v":
            i += 1
            continue
        if src.startswith("--", i):
            i += 2
            if i < n and src[i] == "[":
                level = long_bracket_level(i)
                if level >= 0:
                    close = "]" + "=" * level + "]"
                    end = src.find(close, i)
                    if end < 0:
                        raise LuaSyntaxError("unfinished long comment", line)
                    line += src.count("\n", i, end)
                    i = end + len(close)
                    continue
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "[":
            level = long_bracket_level(i)
            if level >= 0:
                close = "]" + "=" * level + "]"
                end = src.find(close, i)
                if end < 0:
                    raise LuaSyntaxError("unfinished long string", line)
                tokens.append(("string", src[i:end + len(close)], line))
                line += src.count("\n", i, end)
                i = end + len(close)
                continue
        if c in "\"'":
            j, start_line = i + 1, line
            while True:
                if j >= n:
                    raise LuaSyntaxError("unfinished string", start_line)
                ch = src[j]
                if ch == "\\":
                    if j + 1 < n and src[j + 1] == "\n":
                        line += 1
                    j += 2
                    continue
                if ch == "\n":
                    raise LuaSyntaxError("unfinished string", start_line)
                if ch == c:
                    break
                j += 1
            tokens.append(("string", src[i:j + 1], start_line))
            i = j + 1
            continue
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            m = NUMBER_RE.match(src, i)
            tokens.append(("number", m.group(0), line))
            i = m.end()
            if i < n and (src[i].isalnum() or src[i] == "_"):
                raise LuaSyntaxError("malformed number", line)
            continue
        if c.isalpha() or c == "_":
            m = NAME_RE.match(src, i)
            word = m.group(0)
            tokens.append(("keyword" if word in KEYWORDS else "name", word, line))
            i = m.end()
            continue
        for op in MULTI_OPS:
            if src.startswith(op, i):
                tokens.append(("op", op, line))
                i += len(op)
                break
        else:
            if c in SINGLE_OPS:
                tokens.append(("op", c, line))
                i += 1
            else:
                raise LuaSyntaxError("unexpected character %r" % c, line)
    tokens.append(("eof", "<eof>", line))
    return tokens


BINARY = {
    "+": (6, 6), "-": (6, 6), "*": (7, 7), "/": (7, 7), "%": (7, 7),
    "^": (10, 9), "..": (5, 4),
    "==": (3, 3), "~=": (3, 3), "<": (3, 3), "<=": (3, 3), ">": (3, 3), ">=": (3, 3),
    "and": (2, 2), "or": (1, 1),
}
UNARY_PRIORITY = 8


class Parser:
    def __init__(self, tokens):
        self.t = tokens
        self.p = 0
        self.scopes = [set()]
        self.vararg = [True]  # the main chunk is a vararg function
        self.reads = defaultdict(list)
        self.writes = defaultdict(list)

    # -- token helpers -----------------------------------------------------
    def peek(self, k=0):
        return self.t[min(self.p + k, len(self.t) - 1)]

    def check(self, kind, value=None):
        tk = self.t[self.p]
        return tk[0] == kind and (value is None or tk[1] == value)

    def op(self, value):
        return self.check("op", value)

    def kw(self, value):
        return self.check("keyword", value)

    def advance(self):
        tk = self.t[self.p]
        self.p += 1
        return tk

    def expect(self, kind, value=None, what=None):
        if not self.check(kind, value):
            tk = self.t[self.p]
            raise LuaSyntaxError("%s expected near %r" % (what or repr(value or kind), tk[1]), tk[2])
        return self.advance()

    def name(self):
        return self.expect("name", what="<name>")

    # -- scopes -----------------------------------------------------------
    def open_scope(self):
        self.scopes.append(set())

    def close_scope(self):
        self.scopes.pop()

    def declare(self, name):
        self.scopes[-1].add(name)

    def is_local(self, name):
        return any(name in scope for scope in self.scopes)

    def note_read(self, tk):
        if not self.is_local(tk[1]):
            self.reads[tk[1]].append(tk[2])

    # -- blocks and statements ---------------------------------------------
    def block_follow(self):
        tk = self.t[self.p]
        return tk[0] == "eof" or (tk[0] == "keyword" and tk[1] in ("else", "elseif", "end", "until"))

    def chunk(self):
        while not self.block_follow():
            if self.kw("return") or self.kw("break"):
                self.last_statement()
                if not self.block_follow():
                    tk = self.peek()
                    raise LuaSyntaxError("'end' expected (return/break must be the last statement) near %r" % tk[1], tk[2])
                return
            self.statement()
            if self.op(";"):
                self.advance()

    def last_statement(self):
        if self.kw("break"):
            self.advance()
        else:
            self.advance()
            if not self.block_follow() and not self.op(";"):
                self.explist()
        if self.op(";"):
            self.advance()

    def block(self):
        self.open_scope()
        self.chunk()
        self.close_scope()

    def statement(self):
        tk = self.peek()
        if tk[0] == "op" and tk[1] == ";":
            raise LuaSyntaxError("unexpected symbol near ';' (empty statement is not valid in Lua 5.1)", tk[2])
        if tk[0] == "keyword":
            word = tk[1]
            if word == "if":
                self.advance()
                self.expr()
                self.expect("keyword", "then")
                self.block()
                while self.kw("elseif"):
                    self.advance()
                    self.expr()
                    self.expect("keyword", "then")
                    self.block()
                if self.kw("else"):
                    self.advance()
                    self.block()
                self.expect("keyword", "end")
                return
            if word == "while":
                self.advance()
                self.expr()
                self.expect("keyword", "do")
                self.block()
                self.expect("keyword", "end")
                return
            if word == "do":
                self.advance()
                self.block()
                self.expect("keyword", "end")
                return
            if word == "for":
                self.for_statement()
                return
            if word == "repeat":
                self.advance()
                self.open_scope()
                self.chunk()
                self.expect("keyword", "until")
                self.expr()
                self.close_scope()
                return
            if word == "function":
                self.function_statement()
                return
            if word == "local":
                self.advance()
                if self.kw("function"):
                    self.advance()
                    self.declare(self.name()[1])
                    self.funcbody(False)
                    return
                names = [self.name()[1]]
                while self.op(","):
                    self.advance()
                    names.append(self.name()[1])
                if self.op("="):
                    self.advance()
                    self.explist()
                for local_name in names:
                    self.declare(local_name)
                return
        self.expression_statement()

    def for_statement(self):
        self.advance()
        first = self.name()[1]
        if self.op("="):
            self.advance()
            self.expr()
            self.expect("op", ",")
            self.expr()
            if self.op(","):
                self.advance()
                self.expr()
            self.expect("keyword", "do")
            self.open_scope()
            self.declare(first)
            self.block()
            self.close_scope()
            self.expect("keyword", "end")
        elif self.op(",") or self.kw("in"):
            names = [first]
            while self.op(","):
                self.advance()
                names.append(self.name()[1])
            self.expect("keyword", "in")
            self.explist()
            self.expect("keyword", "do")
            self.open_scope()
            for loop_name in names:
                self.declare(loop_name)
            self.block()
            self.close_scope()
            self.expect("keyword", "end")
        else:
            tk = self.peek()
            raise LuaSyntaxError("'=' or 'in' expected near %r" % tk[1], tk[2])

    def function_statement(self):
        self.advance()
        tk = self.name()
        dotted, method = False, False
        while self.op("."):
            self.advance()
            self.name()
            dotted = True
        if self.op(":"):
            self.advance()
            self.name()
            dotted, method = True, True
        if not self.is_local(tk[1]):
            (self.reads if dotted else self.writes)[tk[1]].append(tk[2])
        self.funcbody(method)

    def funcbody(self, method):
        self.open_scope()
        if method:
            self.declare("self")
        self.expect("op", "(")
        is_vararg = False
        if not self.op(")"):
            while True:
                if self.op("..."):
                    self.advance()
                    is_vararg = True
                    break
                self.declare(self.name()[1])
                if self.op(","):
                    self.advance()
                    continue
                break
        self.expect("op", ")")
        self.vararg.append(is_vararg)
        self.chunk()
        self.vararg.pop()
        self.expect("keyword", "end")
        self.close_scope()

    def expression_statement(self):
        kind, bare, line = self.suffixed_expression()
        if self.op("=") or self.op(","):
            targets = [(kind, bare, line)]
            while self.op(","):
                self.advance()
                targets.append(self.suffixed_expression())
            for target_kind, _, target_line in targets:
                if target_kind not in ("name", "index"):
                    raise LuaSyntaxError("syntax error: cannot assign to this expression", target_line)
            self.expect("op", "=")
            self.explist()
            for target_kind, target_bare, _ in targets:
                if target_kind == "name" and not self.is_local(target_bare[1]):
                    self.writes[target_bare[1]].append(target_bare[2])
        elif kind != "call":
            raise LuaSyntaxError("syntax error: statement is not a call or an assignment", line)

    # -- expressions -------------------------------------------------------
    def primary_expression(self):
        tk = self.peek()
        if tk[0] == "name":
            self.advance()
            return "name", tk
        if tk[0] == "op" and tk[1] == "(":
            self.advance()
            self.expr()
            self.expect("op", ")")
            return "paren", tk
        raise LuaSyntaxError("unexpected symbol near %r" % tk[1], tk[2])

    def suffixed_expression(self):
        kind, tk = self.primary_expression()
        base = tk if kind == "name" else None
        suffixed = False
        while True:
            if self.op("."):
                self.advance()
                self.name()
                kind = "index"
            elif self.op("["):
                self.advance()
                self.expr()
                self.expect("op", "]")
                kind = "index"
            elif self.op(":"):
                self.advance()
                self.name()
                self.call_arguments()
                kind = "call"
            elif self.op("(") or self.op("{") or self.check("string"):
                if self.op("(") and self.peek()[2] != self.t[self.p - 1][2]:
                    raise LuaSyntaxError("ambiguous syntax (function call x new statement)", self.peek()[2])
                self.call_arguments()
                kind = "call"
            else:
                break
            suffixed = True
        if base is not None and suffixed:
            self.note_read(base)
        bare = base if (base is not None and not suffixed) else None
        return kind, bare, tk[2]

    def call_arguments(self):
        if self.check("string"):
            self.advance()
            return
        if self.op("{"):
            self.constructor()
            return
        self.expect("op", "(")
        if not self.op(")"):
            self.explist()
        self.expect("op", ")")

    def constructor(self):
        self.expect("op", "{")
        while not self.op("}"):
            if self.op("["):
                self.advance()
                self.expr()
                self.expect("op", "]")
                self.expect("op", "=")
                self.expr()
            elif self.check("name") and self.peek(1)[0] == "op" and self.peek(1)[1] == "=":
                self.advance()
                self.advance()
                self.expr()
            else:
                self.expr()
            if self.op(",") or self.op(";"):
                self.advance()
            else:
                break
        self.expect("op", "}")

    def binary_operator(self):
        tk = self.peek()
        if (tk[0] == "op" or (tk[0] == "keyword" and tk[1] in ("and", "or"))) and tk[1] in BINARY:
            return tk[1]
        return None

    def expr(self, limit=0):
        tk = self.peek()
        if (tk[0] == "keyword" and tk[1] == "not") or (tk[0] == "op" and tk[1] in ("-", "#")):
            self.advance()
            self.expr(UNARY_PRIORITY)
        else:
            self.simple_expression()
        operator = self.binary_operator()
        while operator and BINARY[operator][0] > limit:
            self.advance()
            self.expr(BINARY[operator][1])
            operator = self.binary_operator()

    def simple_expression(self):
        tk = self.peek()
        if tk[0] in ("number", "string"):
            self.advance()
            return
        if tk[0] == "keyword" and tk[1] in ("nil", "true", "false"):
            self.advance()
            return
        if tk[0] == "op" and tk[1] == "...":
            if not self.vararg[-1]:
                raise LuaSyntaxError("cannot use '...' outside a vararg function", tk[2])
            self.advance()
            return
        if tk[0] == "op" and tk[1] == "{":
            self.constructor()
            return
        if tk[0] == "keyword" and tk[1] == "function":
            self.advance()
            self.funcbody(False)
            return
        _, bare, _ = self.suffixed_expression()
        if bare is not None:
            self.note_read(bare)

    def explist(self):
        self.expr()
        while self.op(","):
            self.advance()
            self.expr()

    def parse(self):
        self.chunk()
        if not self.check("eof"):
            tk = self.peek()
            raise LuaSyntaxError("'<eof>' expected near %r" % tk[1], tk[2])


def check_file(path):
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    parser = Parser(tokenize(source))
    parser.parse()
    return parser


def main(paths):
    failures = 0
    all_reads, all_writes = defaultdict(set), defaultdict(set)
    for path in paths:
        try:
            parser = check_file(path)
        except LuaSyntaxError as error:
            failures += 1
            print("FAIL %s: %s" % (path, error))
            continue
        print("OK   %s" % path)
        short = path.replace("\\", "/").split("/")[-1]
        for name in parser.reads:
            all_reads[name].add(short)
        for name in parser.writes:
            all_writes[name].add(short)
    print("\nGlobals written:")
    for name in sorted(all_writes):
        print("  %-36s %s" % (name, ", ".join(sorted(all_writes[name]))))
    print("\nGlobals read:")
    for name in sorted(all_reads):
        print("  %-36s %s" % (name, ", ".join(sorted(all_reads[name]))))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
