import re

import sqlglot
from sqlglot import exp

MAX_ROWS = 200

DISALLOWED_FUNCS = {"load_extension"}

FORBIDDEN_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Pragma,
    exp.Command,
    exp.Alter,
)

_PLACEHOLDER_RE = re.compile(r"%\((\w+)\)s")


class ValidationError(Exception):
    pass


def _normalize_placeholders(sql_text: str) -> str:
    return _PLACEHOLDER_RE.sub(r":\1", sql_text)


def validate_sql(sql: str, allowed_tables, dialect: str = "sqlite", max_rows: int = MAX_ROWS) -> str:
    statement = (sql or "").strip().rstrip(";")
    if not statement:
        raise ValidationError("empty query")

    try:
        statements = [s for s in sqlglot.parse(statement, read=dialect) if s is not None]
    except Exception as err:
        raise ValidationError(f"could not parse sql: {err}") from err

    if len(statements) != 1:
        raise ValidationError("only a single SELECT or WITH statement is allowed")

    root = statements[0]
    if not isinstance(root, (exp.Select, exp.Union)):
        raise ValidationError("only a single SELECT or WITH statement is allowed")

    for node in root.walk():
        n = node[0] if isinstance(node, tuple) else node
        if isinstance(n, FORBIDDEN_TYPES):
            raise ValidationError("only read-only SELECT or WITH statements are allowed")
        if isinstance(n, exp.Anonymous) and str(n.this).lower() in DISALLOWED_FUNCS:
            raise ValidationError(f"function not allowed: {n.this}")

    allowed_lower = {t.lower() for t in allowed_tables}
    cte_names = {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}
    tables = {t.name.lower() for t in root.find_all(exp.Table)}
    disallowed = tables - allowed_lower - cte_names
    if disallowed:
        raise ValidationError(f"table not allowed: {', '.join(sorted(disallowed))}")

    existing_limit = root.args.get("limit")
    if existing_limit is None:
        root = root.limit(max_rows)
    else:
        try:
            current = int(existing_limit.expression.this)
        except (AttributeError, TypeError, ValueError):
            current = None
        if current is None or current > max_rows:
            root = root.limit(max_rows)

    return _normalize_placeholders(root.sql(dialect=dialect))
