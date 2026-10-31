"""Regulamento consultado por capítulo: nada é carregado de uma vez."""
import re
from functools import cache

from . import config


@cache
def _capitulos() -> list[tuple[str, str]]:
    texto = (config.DADOS_DIR / "regulamento.md").read_text(encoding="utf-8")
    partes = re.split(r"(?m)^(?=## Capítulo )", texto)
    return [(p.splitlines()[0].removeprefix("## ").strip(), p.strip()) for p in partes if p.startswith("## Capítulo")]


def listar_capitulos() -> list[dict]:
    """Índice do regulamento: número e título de cada capítulo."""
    return [{"numero": i, "titulo": titulo} for i, (titulo, _) in enumerate(_capitulos(), start=1)]


def ler_capitulo(numero: int) -> str:
    """Texto de um único capítulo, ou aviso se o número for inválido."""
    caps = _capitulos()
    if not 1 <= numero <= len(caps):
        return f"Capítulo inexistente. Use um número de 1 a {len(caps)}."
    return caps[numero - 1][1]
