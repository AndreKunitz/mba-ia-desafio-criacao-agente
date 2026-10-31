"""Tools do assistente.

Nenhuma tool recebe `apartamento`: ele vem sempre do state da sessão, gravado
uma única vez na criação da sessão. O modelo não tem como escolher outro.
"""
from datetime import date

from google.adk.tools import ToolContext

from . import regulamento, repositorio


def _apartamento(tool_context: ToolContext) -> str:
    return tool_context.state["apartamento"]


def _data_valida(data: str) -> bool:
    try:
        date.fromisoformat(data)
        return len(data) == 10
    except ValueError:
        return False


def _erro_entrada(area: str, data: str) -> dict | None:
    if area not in repositorio.areas():
        return {"status": "erro", "mensagem": f"Área inválida. Áreas: {', '.join(repositorio.areas())}."}
    if not _data_valida(data):
        return {"status": "erro", "mensagem": "Data inválida. Use o formato AAAA-MM-DD."}
    return None


# --- reservas -------------------------------------------------------------

def consultar_agenda(area: str, data: str) -> dict:
    """Diz se uma área está livre ou ocupada numa data. Não revela de quem é a reserva.

    Args:
        area: id da área (salao-de-festas, churrasqueira ou quadra).
        data: data no formato AAAA-MM-DD.
    """
    if erro := _erro_entrada(area, data):
        return erro
    return {"area": area, "data": data, "disponivel": not repositorio.data_ocupada(area, data)}


def minhas_reservas(tool_context: ToolContext) -> dict:
    """Lista as reservas ativas do apartamento do morador desta conversa."""
    return {"reservas": repositorio.reservas_do_apartamento(_apartamento(tool_context))}


def _reserva_exige_confirmacao(area: str, data: str, tool_context: ToolContext) -> bool:
    """Garantia 1: reserva de área com taxa gera cobrança, então exige confirmação.

    Data já ocupada não gera cobrança: a tool só recusa, sem pedir confirmação.
    """
    taxa = repositorio.areas().get(area, {}).get("taxa", 0)
    return taxa > 0 and not repositorio.data_ocupada(area, data)


def reservar(area: str, data: str, tool_context: ToolContext) -> dict:
    """Reserva uma área comum para o apartamento do morador desta conversa.

    Args:
        area: id da área (salao-de-festas, churrasqueira ou quadra).
        data: data no formato AAAA-MM-DD.
    """
    if erro := _erro_entrada(area, data):
        return erro
    taxa = repositorio.areas()[area]["taxa"]
    confirmacao = tool_context.tool_confirmation
    if taxa > 0 and not (confirmacao and confirmacao.confirmed):
        # Defesa extra: sem confirmação aprovada, área com taxa nunca é gravada
        # (cobre a data que estava ocupada na checagem e ficou livre depois).
        return {"status": "indisponivel", "mensagem": "Essa área já está reservada nessa data."}
    reserva = repositorio.criar_reserva(_apartamento(tool_context), area, data)
    if reserva is None:
        return {"status": "indisponivel", "mensagem": "Essa área já está reservada nessa data."}
    return {"status": "reservado", **reserva, "taxa_cobrada": taxa}


def cancelar_reserva(tool_context: ToolContext, codigo: str = "", area: str = "", data: str = "") -> dict:
    """Cancela uma reserva do apartamento do morador, sem confirmação.

    Informe o código da reserva OU a área e a data.

    Args:
        codigo: código da reserva (ex.: RSV-1377).
        area: id da área.
        data: data no formato AAAA-MM-DD.
    """
    if not codigo and (erro := _erro_entrada(area, data)):
        return erro
    cancelada = repositorio.cancelar_reserva(_apartamento(tool_context), codigo, area, data)
    if cancelada is None:
        return {"status": "nao_encontrada", "mensagem": "Você não tem uma reserva ativa com esses dados."}
    return {"status": "cancelada", **cancelada}


# --- visitantes -----------------------------------------------------------

def meus_visitantes(tool_context: ToolContext) -> dict:
    """Lista os visitantes autorizados pelo apartamento do morador desta conversa."""
    return {"visitantes": repositorio.visitantes_do_apartamento(_apartamento(tool_context))}


def autorizar_visitante(nome: str, data: str, tool_context: ToolContext) -> dict:
    """Autoriza a entrada de um visitante no prédio numa data (libera acesso).

    Args:
        nome: nome completo do visitante.
        data: data da visita no formato AAAA-MM-DD.
    """
    if not nome.strip():
        return {"status": "erro", "mensagem": "Informe o nome do visitante."}
    if not _data_valida(data):
        return {"status": "erro", "mensagem": "Data inválida. Use o formato AAAA-MM-DD."}
    visitante = repositorio.autorizar_visitante(_apartamento(tool_context), nome.strip(), data)
    return {"status": "autorizado", **visitante}


# --- regulamento ----------------------------------------------------------

def listar_capitulos() -> dict:
    """Lista os capítulos do regulamento interno (número e título)."""
    return {"capitulos": regulamento.listar_capitulos()}


def ler_capitulo(numero: int) -> dict:
    """Lê o texto de UM capítulo do regulamento.

    Args:
        numero: número do capítulo, conforme listar_capitulos.
    """
    return {"texto": regulamento.ler_capitulo(numero)}
