import re
import sqlite3
from pathlib import Path

try:
    import tree_sitter_python as tspython
    import tree_sitter_r as tsr
    from tree_sitter import Language, Parser
    _PY_PARSER = Parser(Language(tspython.language()))
    _R_PARSER = Parser(Language(tsr.language()))
    TREE_SITTER_AVAILABLE = True
except Exception:
    TREE_SITTER_AVAILABLE = False

_PY_IMPORT = re.compile(r'^\s*import\s+([\w.]+)')
_PY_FROM = re.compile(r'^\s*from\s+([\w.]+)\s+import')
_R_LIB = re.compile(r'^\s*(?:library|require)\s*\(\s*["\']?([\w.]+)["\']?\s*\)')

_WRITE_FUNCS = frozenset({
    "to_csv", "to_tsv", "to_excel", "to_parquet", "to_json", "to_pickle",
    "write_h5ad", "write", "save", "savetxt", "dump", "write_csv",
    "write_tsv", "saveRDS", "writelines",
})
_READ_FUNCS = frozenset({
    "read_csv", "read_table", "read_tsv", "read_excel", "read_parquet",
    "read_json", "read_pickle", "read_h5ad", "read", "load", "loadtxt",
    "readRDS", "open",
})
_IO_PATH_KWARGS = frozenset({"path", "file", "filename", "filepath", "path_or_buf", "f"})

# Regex fallback for when Tree-Sitter is not installed.
# Matches IO calls that contain a quoted filename (with an extension) anywhere in the arg list,
# including inside Path concatenation like `DATA / "file.tsv"`.
_PY_FILE_WRITE = re.compile(
    r'\.(?:to_csv|to_tsv|to_excel|to_parquet|to_json|to_pickle|'
    r'write_h5ad|savetxt|write_csv|write_tsv)\s*\([^)]*["\']([^"\']*\.[a-zA-Z0-9]{2,6})["\']',
    re.IGNORECASE,
)
_PY_FILE_READ = re.compile(
    r'(?:read_csv|read_table|read_tsv|read_excel|read_parquet|'
    r'read_json|read_pickle|read_h5ad|read_h5)\s*\([^)]*["\']([^"\']*\.[a-zA-Z0-9]{2,6})["\']',
    re.IGNORECASE,
)
_FILELIKE_EXT = re.compile(r'\.[a-zA-Z0-9]{2,6}$')


def _strip_string(raw: str) -> str:
    for q in ('"""', "'''", '"', "'"):
        if raw.startswith(q) and raw.endswith(q) and len(raw) > 2 * len(q):
            return raw[len(q):-len(q)]
    return raw.strip("\"'")


class RepoIndexer:
    """Parses a multi-file repo into a SQLite symbol table."""

    def __init__(self):
        self._db = sqlite3.connect(":memory:")
        self._db.executescript("""
            CREATE TABLE imports (
                file TEXT NOT NULL,
                module TEXT NOT NULL
            );
            CREATE TABLE assignments (
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                var_name TEXT NOT NULL,
                rhs_func TEXT,
                rhs_var  TEXT,
                snippet  TEXT
            );
            CREATE TABLE call_args (
                file     TEXT NOT NULL,
                line     INTEGER NOT NULL,
                func_name TEXT NOT NULL,
                arg_name  TEXT NOT NULL,
                snippet   TEXT
            );
            CREATE TABLE file_io (
                file     TEXT NOT NULL,
                line     INTEGER NOT NULL,
                op       TEXT NOT NULL,
                path_arg TEXT NOT NULL,
                snippet  TEXT
            );
            CREATE INDEX idx_assign_var   ON assignments(var_name);
            CREATE INDEX idx_assign_func  ON assignments(rhs_func);
            CREATE INDEX idx_callarg_arg  ON call_args(arg_name);
            CREATE INDEX idx_callarg_func ON call_args(func_name);
            CREATE INDEX idx_import_mod   ON imports(module);
            CREATE INDEX idx_fileio_path  ON file_io(path_arg);
        """)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index(self, files: dict[str, str]) -> None:
        for fname, content in files.items():
            ext = Path(fname).suffix.lower()
            if ext == ".py":
                self._index_python(fname, content)
            elif ext in (".r", ".rmd", ".qmd"):
                self._index_r(fname, content)
        self._db.commit()

    def get_imports(self) -> set[str]:
        rows = self._db.execute("SELECT DISTINCT module FROM imports").fetchall()
        return {r[0] for r in rows}

    def get_produced_by(self, func_name: str) -> list[dict]:
        rows = self._db.execute(
            "SELECT file, line, var_name, snippet FROM assignments WHERE rhs_func = ?",
            (func_name,),
        ).fetchall()
        return [{"file": r[0], "line": r[1], "var_name": r[2], "snippet": r[3]} for r in rows]

    def get_var_assignments(self, var_name: str) -> list[dict]:
        rows = self._db.execute(
            "SELECT file, line, rhs_func, rhs_var, snippet FROM assignments WHERE var_name = ?",
            (var_name,),
        ).fetchall()
        return [
            {"file": r[0], "line": r[1], "rhs_func": r[2], "rhs_var": r[3], "snippet": r[4]}
            for r in rows
        ]

    def get_var_usages(self, var_name: str) -> list[dict]:
        rows = self._db.execute(
            "SELECT file, line, func_name, snippet FROM call_args WHERE arg_name = ?",
            (var_name,),
        ).fetchall()
        return [{"file": r[0], "line": r[1], "func_name": r[2], "snippet": r[3]} for r in rows]

    def get_aliases(self, var_name: str) -> list[str]:
        rows = self._db.execute(
            "SELECT var_name FROM assignments WHERE rhs_var = ?",
            (var_name,),
        ).fetchall()
        return [r[0] for r in rows]

    def get_file_writes(self) -> list[dict]:
        rows = self._db.execute(
            "SELECT file, line, path_arg, snippet FROM file_io WHERE op = 'write'"
        ).fetchall()
        return [{"file": r[0], "line": r[1], "path_arg": r[2], "snippet": r[3]} for r in rows]

    def get_file_reads(self) -> list[dict]:
        rows = self._db.execute(
            "SELECT file, line, path_arg, snippet FROM file_io WHERE op = 'read'"
        ).fetchall()
        return [{"file": r[0], "line": r[1], "path_arg": r[2], "snippet": r[3]} for r in rows]

    # ------------------------------------------------------------------
    # Python indexing
    # ------------------------------------------------------------------

    def _index_python(self, fname: str, content: str) -> None:
        lines = content.splitlines()
        for line in lines:
            m = _PY_IMPORT.match(line)
            if m:
                self._add_import(fname, m.group(1).split(".")[0])
            m = _PY_FROM.match(line)
            if m:
                self._add_import(fname, m.group(1).split(".")[0])

        if not TREE_SITTER_AVAILABLE:
            self._index_python_io_regex(fname, lines)
            return
        tree = _PY_PARSER.parse(content.encode())
        self._walk_python(tree.root_node, fname, lines)

    def _index_python_io_regex(self, fname: str, lines: list[str]) -> None:
        """Regex fallback for file-I/O detection when Tree-Sitter is unavailable."""
        for i, line in enumerate(lines):
            m = _PY_FILE_WRITE.search(line)
            if m:
                self._add_file_io(fname, i + 1, "write", m.group(1), line.strip())
            m = _PY_FILE_READ.search(line)
            if m:
                self._add_file_io(fname, i + 1, "read", m.group(1), line.strip())

    def _walk_python(self, node, fname: str, lines: list[str]) -> None:
        if node.type == "assignment":
            self._handle_py_assignment(node, fname, lines)
        elif node.type == "expression_statement":
            for child in node.children:
                if child.type == "call":
                    self._handle_py_call(child, fname, lines)
        for child in node.children:
            self._walk_python(child, fname, lines)

    def _handle_py_assignment(self, node, fname: str, lines: list[str]) -> None:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if not left or not right:
            return
        if left.type != "identifier":
            return

        var_name = left.text.decode()
        line = node.start_point[0] + 1
        snippet = lines[line - 1].strip() if line <= len(lines) else ""

        if right.type == "call":
            func_node = right.child_by_field_name("function")
            func_name = func_node.text.decode().split(".")[-1] if func_node else None
            self._add_assignment(fname, line, var_name, rhs_func=func_name, snippet=snippet)
            self._handle_py_call(right, fname, lines)
        elif right.type == "identifier":
            self._add_assignment(fname, line, var_name, rhs_var=right.text.decode(), snippet=snippet)
        else:
            self._add_assignment(fname, line, var_name, snippet=snippet)

    def _handle_py_call(self, node, fname: str, lines: list[str]) -> None:
        func_node = node.child_by_field_name("function")
        args_node = node.child_by_field_name("arguments")
        if not func_node or not args_node:
            return
        func_name = func_node.text.decode().split(".")[-1]
        line = node.start_point[0] + 1
        snippet = lines[line - 1].strip() if line <= len(lines) else ""
        for arg in args_node.children:
            if arg.type == "identifier":
                self._add_call_arg(fname, line, func_name, arg.text.decode(), snippet)
            elif arg.type == "keyword_argument":
                val = arg.child_by_field_name("value")
                if val and val.type == "identifier":
                    self._add_call_arg(fname, line, func_name, val.text.decode(), snippet)

        # File I/O detection
        op: str | None = None
        if func_name in _WRITE_FUNCS:
            op = "write"
        elif func_name in _READ_FUNCS:
            op = "read"
        if op:
            path = self._extract_path_string(args_node)
            if path:
                self._add_file_io(fname, line, op, path, snippet)

    def _extract_path_string(self, args_node) -> str | None:
        """Return a filename string from call args, searching recursively for Path/'str' patterns."""
        for arg in args_node.children:
            if arg.type in (",", "(", ")"):
                continue
            if arg.type == "keyword_argument":
                key = arg.child_by_field_name("name")
                val = arg.child_by_field_name("value")
                if key and val and key.text.decode() in _IO_PATH_KWARGS:
                    found = self._find_filelike_string(val)
                    if found:
                        return found
            else:
                found = self._find_filelike_string(arg)
                if found:
                    return found
        return None

    def _find_filelike_string(self, node) -> str | None:
        """Recursively search a node for a string literal that looks like a filename."""
        if node.type == "string":
            raw = node.text.decode()
            if raw.startswith(("f'", 'f"', "f'''", 'f"""')):
                return None
            stripped = _strip_string(raw)
            basename = stripped.split("/")[-1].split("\\")[-1]
            if stripped and _FILELIKE_EXT.search(basename):
                return stripped
        for child in node.children:
            result = self._find_filelike_string(child)
            if result:
                return result
        return None

    # ------------------------------------------------------------------
    # R indexing
    # ------------------------------------------------------------------

    def _index_r(self, fname: str, content: str) -> None:
        lines = content.splitlines()
        for line in lines:
            m = _R_LIB.match(line)
            if m:
                self._add_import(fname, m.group(1))

        if not TREE_SITTER_AVAILABLE:
            return
        tree = _R_PARSER.parse(content.encode())
        self._walk_r(tree.root_node, fname, lines)

    def _walk_r(self, node, fname: str, lines: list[str]) -> None:
        if node.type in ("left_assignment", "equals_assignment", "super_assignment"):
            self._handle_r_assignment(node, fname, lines)
        for child in node.children:
            self._walk_r(child, fname, lines)

    def _handle_r_assignment(self, node, fname: str, lines: list[str]) -> None:
        left = node.child_by_field_name("lhs")
        right = node.child_by_field_name("rhs")
        # fall back to positional if grammar has no named fields
        if left is None or right is None:
            kids = [c for c in node.children if c.type not in ("<-", "=", "<<-", "->")]
            if len(kids) < 2:
                return
            left, right = kids[0], kids[-1]

        if left.type != "identifier":
            return

        var_name = left.text.decode()
        line = node.start_point[0] + 1
        snippet = lines[line - 1].strip() if line <= len(lines) else ""

        if right.type == "call":
            func_node = right.child_by_field_name("function")
            func_name = func_node.text.decode() if func_node else None
            self._add_assignment(fname, line, var_name, rhs_func=func_name, snippet=snippet)
            args = right.child_by_field_name("arguments")
            if args and func_name:
                for arg in args.children:
                    if arg.type == "identifier":
                        self._add_call_arg(fname, line, func_name, arg.text.decode(), snippet)
        elif right.type == "identifier":
            self._add_assignment(fname, line, var_name, rhs_var=right.text.decode(), snippet=snippet)
        else:
            self._add_assignment(fname, line, var_name, snippet=snippet)

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _add_import(self, file: str, module: str) -> None:
        self._db.execute("INSERT INTO imports VALUES (?, ?)", (file, module.lower()))

    def _add_assignment(
        self,
        file: str,
        line: int,
        var_name: str,
        rhs_func: str | None = None,
        rhs_var: str | None = None,
        snippet: str = "",
    ) -> None:
        self._db.execute(
            "INSERT INTO assignments VALUES (?, ?, ?, ?, ?, ?)",
            (file, line, var_name, rhs_func, rhs_var, snippet),
        )

    def _add_call_arg(
        self, file: str, line: int, func_name: str, arg_name: str, snippet: str = ""
    ) -> None:
        self._db.execute(
            "INSERT INTO call_args VALUES (?, ?, ?, ?, ?)",
            (file, line, func_name, arg_name, snippet),
        )

    def _add_file_io(
        self, file: str, line: int, op: str, path_arg: str, snippet: str = ""
    ) -> None:
        self._db.execute(
            "INSERT INTO file_io VALUES (?, ?, ?, ?, ?)",
            (file, line, op, path_arg, snippet),
        )
