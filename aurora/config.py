import os
from pathlib import Path

from google.adk.models import Gemini
from google.genai import types

DADOS_DIR = Path(os.getenv("DADOS_DIR", "dados"))
ESTADO_DIR = Path(os.getenv("ESTADO_DIR", "estado"))
NOME_MODELO = os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite"

# O plano gratuito limita requisições por minuto (429): esperamos e tentamos de novo.
MODELO = Gemini(
    model=NOME_MODELO,
    retry_options=types.HttpRetryOptions(attempts=6, initial_delay=4, max_delay=40, exp_base=2),
)

APP_NAME = "aurora"
DB_CONDOMINIO = ESTADO_DIR / "condominio.db"
DB_SESSOES = ESTADO_DIR / "sessoes.db"
