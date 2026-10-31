from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from google.genai.errors import APIError
from google.adk.apps import App
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types
from pydantic import BaseModel

from . import config, repositorio
from .agentes import root_agent

CONFIRMACAO = "adk_request_confirmation"


class NovaSessao(BaseModel):
    apartamento: str


class NovaMensagem(BaseModel):
    texto: str


class RespostaConfirmacao(BaseModel):
    id: str
    confirmado: bool


@asynccontextmanager
async def lifespan(app: FastAPI):
    repositorio.inicializar()
    config.ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    app.state.sessoes = DatabaseSessionService(f"sqlite+aiosqlite:///{config.DB_SESSOES}")
    app.state.runner = Runner(
        app=App(name=config.APP_NAME, root_agent=root_agent),
        session_service=app.state.sessoes,
    )
    yield


app = FastAPI(title="Assistente Aurora", lifespan=lifespan)


@app.exception_handler(Exception)
async def erro_do_modelo(request: Request, exc: Exception):
    """Falha do Gemini (cota, sobrecarga) vira 503 legível; o resto segue como 500."""
    causa = exc if isinstance(exc, APIError) else exc.__cause__
    if isinstance(causa, APIError) or type(exc).__name__ == "_ResourceExhaustedError":
        return JSONResponse({"detail": "Modelo indisponível no momento, tente novamente."}, status_code=503)
    return JSONResponse({"detail": "Erro interno"}, status_code=500)


def _user_id(apartamento: str) -> str:
    return f"morador-{apartamento}"


async def _sessao(session_id: str):
    """Busca a sessão (qualquer user_id) ou responde 404."""
    # O user_id depende do apartamento, que só a sessão conhece: varremos os moradores.
    for numero in repositorio.apartamentos():
        sessao = await app.state.sessoes.get_session(
            app_name=config.APP_NAME, user_id=_user_id(numero), session_id=session_id
        )
        if sessao:
            return sessao
    raise HTTPException(404, "Sessão não encontrada")


def _pendentes(sessao) -> list[dict]:
    """Confirmações pedidas e ainda sem resposta, derivadas dos eventos persistidos."""
    respondidas = {
        fr.id for ev in sessao.events for fr in ev.get_function_responses() if fr.name == CONFIRMACAO
    }
    pendentes = []
    for ev in sessao.events:
        for fc in ev.get_function_calls():
            if fc.name != CONFIRMACAO or fc.id in respondidas:
                continue
            original = (fc.args or {}).get("originalFunctionCall", {})
            pendentes.append(
                {"id": fc.id, "acao": original.get("name", ""), "detalhes": original.get("args", {})}
            )
    return pendentes


async def _executar(sessao, conteudo: types.Content) -> dict:
    textos = []
    async for ev in app.state.runner.run_async(
        user_id=sessao.user_id, session_id=sessao.id, new_message=conteudo
    ):
        if ev.is_final_response() and ev.content and ev.content.parts:
            textos += [p.text for p in ev.content.parts if p.text]
    atual = await _sessao(sessao.id)
    return {"resposta": "\n".join(textos), "confirmacoes_pendentes": _pendentes(atual)}


@app.post("/sessoes", status_code=201)
async def criar_sessao(corpo: NovaSessao):
    sessao = await app.state.sessoes.create_session(
        app_name=config.APP_NAME,
        user_id=_user_id(corpo.apartamento),
        state={"apartamento": corpo.apartamento},
    )
    return {"session_id": sessao.id}


@app.post("/sessoes/{session_id}/mensagens")
async def enviar_mensagem(session_id: str, corpo: NovaMensagem):
    sessao = await _sessao(session_id)
    conteudo = types.Content(role="user", parts=[types.Part(text=corpo.texto)])
    return await _executar(sessao, conteudo)


@app.post("/sessoes/{session_id}/confirmacoes")
async def responder_confirmacao(session_id: str, corpo: RespostaConfirmacao):
    sessao = await _sessao(session_id)
    if corpo.id not in {p["id"] for p in _pendentes(sessao)}:
        raise HTTPException(409, "Não há confirmação pendente com esse id nesta sessão")
    conteudo = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=corpo.id, name=CONFIRMACAO, response={"confirmed": corpo.confirmado}
                )
            )
        ],
    )
    return await _executar(sessao, conteudo)


@app.get("/sessoes/{session_id}/eventos")
async def eventos(session_id: str):
    sessao = await _sessao(session_id)
    return [ev.model_dump(mode="json", exclude_none=True) for ev in sessao.events]


@app.get("/apartamentos/{numero}/reservas")
async def reservas(numero: str):
    return repositorio.reservas_do_apartamento(numero)


@app.get("/apartamentos/{numero}/visitantes")
async def visitantes(numero: str):
    return repositorio.visitantes_do_apartamento(numero)
