"""Única porta de acesso aos dados do condomínio (SQLite).

A exclusividade "uma reserva ativa por área e data" vive no banco, num índice
único parcial: vale no instante do INSERT, mesmo com gravações simultâneas.
"""
import json
import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS reservas (
    seq INTEGER NOT NULL UNIQUE,
    codigo TEXT PRIMARY KEY,
    apartamento TEXT NOT NULL,
    area TEXT NOT NULL,
    data TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ativa'
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_reserva_ativa
    ON reservas(area, data) WHERE status = 'ativa';
CREATE TABLE IF NOT EXISTS visitantes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    apartamento TEXT NOT NULL,
    nome TEXT NOT NULL,
    data TEXT NOT NULL
);
"""


@contextmanager
def _conexao():
    config.ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_CONDOMINIO, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    try:
        yield con
    finally:
        con.close()


def _json(nome: str):
    return json.loads((config.DADOS_DIR / nome).read_text(encoding="utf-8"))


def inicializar() -> None:
    """Cria o schema e, na primeira subida, carrega os dados iniciais."""
    with _conexao() as con:
        con.executescript(SCHEMA)
        con.execute("BEGIN IMMEDIATE")
        vazio = con.execute("SELECT COUNT(*) FROM reservas").fetchone()[0] == 0
        if vazio and con.execute("SELECT COUNT(*) FROM visitantes").fetchone()[0] == 0:
            for i, r in enumerate(_json("reservas.json"), start=1):
                con.execute(
                    "INSERT INTO reservas(seq, codigo, apartamento, area, data) VALUES (?,?,?,?,?)",
                    (i, r["codigo"], r["apartamento"], r["area"], r["data"]),
                )
            for v in _json("visitantes.json"):
                con.execute(
                    "INSERT INTO visitantes(apartamento, nome, data) VALUES (?,?,?)",
                    (v["apartamento"], v["nome"], v["data"]),
                )
        con.execute("COMMIT")


def areas() -> dict[str, dict]:
    return {a["id"]: a for a in _json("areas.json")}


def apartamentos() -> set[str]:
    return {a["numero"] for a in _json("apartamentos.json")}


def data_ocupada(area: str, data: str) -> bool:
    with _conexao() as con:
        row = con.execute(
            "SELECT 1 FROM reservas WHERE area=? AND data=? AND status='ativa'", (area, data)
        ).fetchone()
    return row is not None


def reservas_do_apartamento(apartamento: str) -> list[dict]:
    with _conexao() as con:
        rows = con.execute(
            "SELECT codigo, area, data FROM reservas "
            "WHERE apartamento=? AND status='ativa' ORDER BY data, seq",
            (apartamento,),
        ).fetchall()
    return [dict(r) for r in rows]


def criar_reserva(apartamento: str, area: str, data: str) -> dict | None:
    """Grava a reserva. Devolve None se a data já estiver ocupada."""
    with _conexao() as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            # Reservas canceladas continuam na tabela: o seq (e o código) nunca se repete.
            seq = con.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM reservas").fetchone()[0]
            codigo = f"RSV-{10000 + seq}"
            con.execute(
                "INSERT INTO reservas(seq, codigo, apartamento, area, data) VALUES (?,?,?,?,?)",
                (seq, codigo, apartamento, area, data),
            )
            con.execute("COMMIT")
        except sqlite3.IntegrityError:
            con.execute("ROLLBACK")
            return None
    return {"codigo": codigo, "area": area, "data": data}


def cancelar_reserva(apartamento: str, codigo: str = "", area: str = "", data: str = "") -> dict | None:
    """Cancela uma reserva ativa DO APARTAMENTO informado. None se não existir."""
    with _conexao() as con:
        con.execute("BEGIN IMMEDIATE")
        if codigo:
            row = con.execute(
                "SELECT codigo, area, data FROM reservas WHERE apartamento=? AND codigo=? AND status='ativa'",
                (apartamento, codigo),
            ).fetchone()
        else:
            row = con.execute(
                "SELECT codigo, area, data FROM reservas WHERE apartamento=? AND area=? AND data=? AND status='ativa'",
                (apartamento, area, data),
            ).fetchone()
        if row:
            con.execute("UPDATE reservas SET status='cancelada' WHERE codigo=?", (row["codigo"],))
        con.execute("COMMIT")
    return dict(row) if row else None


def visitantes_do_apartamento(apartamento: str) -> list[dict]:
    with _conexao() as con:
        rows = con.execute(
            "SELECT nome, data FROM visitantes WHERE apartamento=? ORDER BY id", (apartamento,)
        ).fetchall()
    return [dict(r) for r in rows]


def autorizar_visitante(apartamento: str, nome: str, data: str) -> dict:
    with _conexao() as con:
        con.execute(
            "INSERT INTO visitantes(apartamento, nome, data) VALUES (?,?,?)",
            (apartamento, nome, data),
        )
    return {"nome": nome, "data": data}
