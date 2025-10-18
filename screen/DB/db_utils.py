# -*- coding: utf-8 -*-
"""
Helper utilities for Oracle database access used by Insert/Update screens.
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import inspect
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from screen.DB import cmd_sql_plus

_Driver = Any

SYSTEM_SCHEMAS: set[str] = {
    "SYS",
    "SYSTEM",
    "XDB",
    "MDSYS",
    "ORDDATA",
    "ORDSYS",
    "OUTLN",
    "CTXSYS",
    "WMSYS",
    "SI_INFORMTN_SCHEMA",
    "SYSMAN",
    "DBSNMP",
    "APPQOSSYS",
    "GSMADMIN_INTERNAL",
    "AUDSYS",
}

NUMERIC_TYPES = {
    "NUMBER",
    "FLOAT",
    "BINARY_FLOAT",
    "BINARY_DOUBLE",
    "INTEGER",
    "INT",
    "SMALLINT",
    "REAL",
    "DECIMAL",
    "NUMERIC",
}

DATE_TYPES = {"DATE"}
TIME_TYPES = {"TIMESTAMP", "TIMESTAMP WITH LOCAL TIME ZONE", "TIMESTAMP WITH TIME ZONE"}

COMMON_DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%d/%m/%Y",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M:%S.%f",
    "%Y/%m/%d",
    "%Y/%m/%d %H:%M:%S",
    "%d-%m-%Y",
    "%d-%m-%Y %H:%M:%S",
    "%Y%m%d",
    "%Y%m%d%H%M%S",
]


class OracleDriverNotAvailable(RuntimeError):
    """Raised when oracledb / cx_Oracle driver cannot be imported."""


def _supports_encoding_kwarg(driver: _Driver) -> bool:
    """
    Return True if the driver.connect callable accepts an 'encoding' keyword.
    """
    if getattr(driver, "__name__", "") == "cx_Oracle":
        return True
    connect = getattr(driver, "connect", None)
    if connect is None:
        return False
    try:
        sig = inspect.signature(connect)
    except (TypeError, ValueError):
        return False
    return "encoding" in sig.parameters


def load_driver() -> _Driver:
    """
    Return an Oracle driver module (oracledb preferred, fallback cx_Oracle).
    Raises OracleDriverNotAvailable if neither can be imported.
    """
    try:
        import oracledb  # type: ignore

        return oracledb
    except Exception:
        try:
            import cx_Oracle  # type: ignore

            return cx_Oracle
        except Exception as exc:
            raise OracleDriverNotAvailable(
                "Không tìm thấy driver Oracle (cần cài 'oracledb' hoặc 'cx_Oracle')."
            ) from exc


def build_dsn(host: str, port: str, alias_or_service: str, use_host_port: bool) -> str:
    return cmd_sql_plus.build_dsn(host, port, alias_or_service, use_host_port)


def connect_oracle(
    user: str,
    password: str,
    host: str,
    port: str,
    alias_or_service: str,
    use_host_port: bool,
    encoding: str = "UTF-8",
):
    """
    Establish an Oracle connection using provided credentials.
    """
    driver = load_driver()
    dsn = build_dsn(host, port, alias_or_service, use_host_port)
    connect_kwargs = {"user": user, "password": password, "dsn": dsn}
    if _supports_encoding_kwarg(driver):
        connect_kwargs["encoding"] = encoding
    try:
        return driver.connect(**connect_kwargs)
    except TypeError as exc:
        # python-oracledb in thin mode rejects the encoding kwarg, so retry without it.
        if "encoding" in connect_kwargs and "encoding" in str(exc):
            connect_kwargs.pop("encoding", None)
            return driver.connect(**connect_kwargs)
        raise


def _split_owner_table(raw_name: str, default_owner: str) -> tuple[str, str]:
    if "." in raw_name:
        owner, table = raw_name.split(".", 1)
        return owner.strip().upper(), table.strip().upper()
    return default_owner.upper(), raw_name.strip().upper()


def split_owner_table(raw_name: str, default_owner: str) -> tuple[str, str]:
    """
    Public wrapper so UI layers can consistently resolve owner/table pairs.
    """
    return _split_owner_table(raw_name, default_owner)


def fetch_accessible_tables(
    conn,
    *,
    include_owner: bool = True,
    exclude_system: bool = True,
    limit: int | None = None,
) -> List[str]:
    """
    Return list of accessible tables for the current user.
    Format: OWNER.TABLE when include_owner=True, else just table name.
    """
    user = getattr(conn, "username", None)
    owner = str(user or "").upper()
    tables: List[str] = []

    queries = [
        ("SELECT table_name FROM user_tables ORDER BY table_name", ()),
        (
            "SELECT owner, table_name FROM all_tables WHERE owner = :owner ORDER BY table_name",
            {"owner": owner},
        ),
        (
            "SELECT owner, table_name FROM all_tab_privs WHERE grantee = USER "
            "AND privilege IN ('SELECT','INSERT','UPDATE')",
            {},
        ),
    ]

    seen: set[str] = set()
    with contextlib.closing(conn.cursor()) as cur:
        for sql, params in queries:
            try:
                cur.execute(sql, params)
            except Exception:
                continue
            for row in cur:
                if len(row) == 1:
                    tbl_owner = owner
                    tbl_name = row[0]
                else:
                    tbl_owner, tbl_name = row[0], row[1]
                if not tbl_name:
                    continue
                ow = str(tbl_owner or owner).upper()
                tb = str(tbl_name).upper()
                if exclude_system and ow in SYSTEM_SCHEMAS:
                    continue
                key = f"{ow}.{tb}"
                if key in seen:
                    continue
                seen.add(key)
                tables.append(key if include_owner else tb)
                if limit and len(tables) >= limit:
                    return tables
    tables.sort()
    return tables


def fetch_table_columns(conn, table_name: str, default_owner: str) -> List[Dict[str, Any]]:
    owner, table = _split_owner_table(table_name, default_owner)
    sql = (
        "SELECT column_name, data_type, data_length, data_precision, data_scale, nullable, column_id "
        "FROM all_tab_columns WHERE owner = :owner AND table_name = :tbl ORDER BY column_id"
    )
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(sql, {"owner": owner, "tbl": table})
        return [
            {
                "column_name": str(row[0]),
                "data_type": str(row[1]),
                "data_length": row[2],
                "data_precision": row[3],
                "data_scale": row[4],
                "nullable": (str(row[5]).upper() != "N"),
                "column_id": row[6],
            }
            for row in cur
        ]


def fetch_primary_keys(conn, table_name: str, default_owner: str) -> List[str]:
    owner, table = _split_owner_table(table_name, default_owner)
    sql = (
        "SELECT acc.column_name FROM all_constraints ac "
        "JOIN all_cons_columns acc "
        "ON ac.owner = acc.owner AND ac.constraint_name = acc.constraint_name "
        "WHERE ac.constraint_type = 'P' AND ac.owner = :owner AND ac.table_name = :tbl "
        "ORDER BY acc.position"
    )
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(sql, {"owner": owner, "tbl": table})
        return [str(row[0]) for row in cur]


def format_sql_literal(value: Any, column_meta: Optional[Dict[str, Any]] = None) -> str:
    """
    Format python value to Oracle SQL literal based on column metadata.
    """
    if value is None:
        return "NULL"
    if isinstance(value, str):
        v = value.strip()
        if v == "":
            return "NULL"
        data_type = (column_meta or {}).get("data_type", "").upper()
        if data_type in NUMERIC_TYPES:
            if re.fullmatch(r"[+-]?\d+(\.\d+)?", v):
                return v
            if re.fullmatch(r"[+-]?\d+", v):
                return v
        if data_type in DATE_TYPES:
            parsed, oracle_fmt, str_fmt = _try_parse_datetime(v, prefer_date=True)
            if parsed:
                return f"TO_DATE('{parsed.strftime(str_fmt)}','{oracle_fmt}')"
        if data_type in TIME_TYPES:
            parsed, oracle_fmt, str_fmt = _try_parse_datetime(v, prefer_date=False)
            if parsed:
                return f"TO_TIMESTAMP('{parsed.strftime(str_fmt)}','{oracle_fmt}')"
        escaped = v.replace("'", "''")
        return f"'{escaped}'"
    if isinstance(value, (_dt.datetime, _dt.date)):
        fmt = "YYYY-MM-DD HH24:MI:SS" if isinstance(value, _dt.datetime) else "YYYY-MM-DD"
        iso = value.strftime("%Y-%m-%d %H:%M:%S") if isinstance(value, _dt.datetime) else value.strftime("%Y-%m-%d")
        func = "TO_TIMESTAMP" if isinstance(value, _dt.datetime) else "TO_DATE"
        return f"{func}('{iso}','{fmt}')"
    return str(value)


def _try_parse_datetime(value: str, prefer_date: bool) -> Tuple[Optional[_dt.datetime], str, str]:
    value = value.strip()
    for fmt in COMMON_DATE_FORMATS:
        try:
            parsed = _dt.datetime.strptime(value, fmt)
            if prefer_date and fmt.count("%H") == 0:
                return parsed, "YYYY-MM-DD", "%Y-%m-%d"
            fmt_tok = fmt.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD").replace("%H", "HH24").replace(
                "%M", "MI"
            ).replace("%S", "SS")
            if "%f" in fmt:
                fmt_tok = fmt_tok.replace("%f", "FF")
            return parsed, fmt_tok, fmt
        except ValueError:
            continue
    return None, "", ""


def fetch_rows_by_pk(
    conn,
    table_name: str,
    default_owner: str,
    pk_columns: Sequence[str],
    keys: Iterable[Sequence[Any]],
) -> Dict[Tuple[Any, ...], Dict[str, Any]]:
    """
    Fetch rows identified by PK combinations.
    Returns mapping from PK tuple to {column: value}.
    """
    owner, table = _split_owner_table(table_name, default_owner)
    pk_columns = [col.upper() for col in pk_columns]
    key_list = list(keys)
    if not key_list:
        return {}

    col_list = ", ".join(pk_columns)
    all_cols_sql = "SELECT * FROM {}.{} WHERE ".format(owner, table)
    result: Dict[Tuple[Any, ...], Dict[str, Any]] = {}

    with contextlib.closing(conn.cursor()) as cur:
        for key in key_list:
            where_parts = []
            bind_params = {}
            for idx, col in enumerate(pk_columns):
                bind_name = f"v{idx}"
                where_parts.append(f"{col} = :{bind_name}")
                bind_params[bind_name] = key[idx]
            sql = all_cols_sql + " AND ".join(where_parts)
            try:
                cur.execute(sql, bind_params)
            except Exception:
                continue
            row = cur.fetchone()
            if not row:
                continue
            columns = [d[0] for d in cur.description]
            record = {columns[i]: row[i] for i in range(len(columns))}
            result[tuple(key)] = record
    return result


def delete_by_pk(
    conn,
    table_name: str,
    default_owner: str,
    pk_columns: Sequence[str],
    keys: Iterable[Sequence[Any]],
):
    """
    Delete rows identified by PK combinations.
    """
    owner, table = _split_owner_table(table_name, default_owner)
    pk_columns = [col.upper() for col in pk_columns]
    key_list = list(keys)
    if not key_list:
        return
    with contextlib.closing(conn.cursor()) as cur:
        for key in key_list:
            where_parts = []
            bind_params = {}
            for idx, col in enumerate(pk_columns):
                bind_name = f"v{idx}"
                where_parts.append(f"{col} = :{bind_name}")
                bind_params[bind_name] = key[idx]
            sql = f"DELETE FROM {owner}.{table} WHERE " + " AND ".join(where_parts)
            cur.execute(sql, bind_params)
    conn.commit()


def insert_rows(
    conn,
    table_name: str,
    default_owner: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
):
    owner, table = _split_owner_table(table_name, default_owner)
    columns = [c.upper() for c in columns]
    col_expr = ", ".join(columns)
    bind_names = [f":{i+1}" for i in range(len(columns))]
    sql = f"INSERT INTO {owner}.{table} ({col_expr}) VALUES ({', '.join(bind_names)})"
    with contextlib.closing(conn.cursor()) as cur:
        cur.executemany(sql, rows)
    conn.commit()


def update_rows(
    conn,
    table_name: str,
    default_owner: str,
    update_columns: Sequence[str],
    pk_columns: Sequence[str],
    data_rows: Iterable[Dict[str, Any]],
    extra_where: Optional[str] = None,
):
    owner, table = _split_owner_table(table_name, default_owner)
    update_columns = [c.upper() for c in update_columns]
    pk_columns = [c.upper() for c in pk_columns]
    set_clause = ", ".join(f"{col} = :{col}" for col in update_columns)

    where_parts = [f"{pk} = :PK_{pk}" for pk in pk_columns]
    extra_where_clause = ""
    if extra_where:
        extra_where_clause = f" AND ({extra_where})"

    sql = f"UPDATE {owner}.{table} SET {set_clause} WHERE " + " AND ".join(where_parts) + extra_where_clause

    with contextlib.closing(conn.cursor()) as cur:
        for row in data_rows:
            binds: Dict[str, Any] = {}
            for col in update_columns:
                binds[col] = row.get(col)
            for pk in pk_columns:
                binds[f"PK_{pk}"] = row.get(pk)
            cur.execute(sql, binds)
    conn.commit()
