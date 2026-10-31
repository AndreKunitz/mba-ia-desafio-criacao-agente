"""Restaura reservas e visitantes ao estado de dados/*.json e apaga as sessões.

Rode com a API parada:  docker compose run --rm api python -m aurora.restaurar
"""
from . import config, repositorio


def main() -> None:
    config.ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    for base in (config.DB_CONDOMINIO, config.DB_SESSOES):
        for sufixo in ("", "-wal", "-shm"):
            base.with_name(base.name + sufixo).unlink(missing_ok=True)
    repositorio.inicializar()
    print("Dados restaurados ao estado inicial; sessões apagadas.")


if __name__ == "__main__":
    main()
