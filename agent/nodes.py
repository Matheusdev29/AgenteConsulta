"""
Nós do grafo do agente.

Divisão de responsabilidades:
  - LLM  -> só interpreta a mensagem (intenção + campos extraídos).
  - Código Python -> valida e decide tudo o que importa (passado, expediente, vaga).
"""
from __future__ import annotations

import os
from datetime import date, datetime, time
from typing import Literal, Optional, TypedDict
from zoneinfo import ZoneInfo

from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from services import db_services

# --------------------------------------------------------------------------
# Regras de negócio da clínica (ajuste aqui)
# --------------------------------------------------------------------------
TZ = ZoneInfo("America/Sao_Paulo")
HORA_ABERTURA = time(8, 0)
HORA_FECHAMENTO = time(18, 0)   # último horário possível: 17:30
INTERVALO_MIN = 30              # consultas de 30 em 30 minutos
DIAS_UTEIS = {0, 1, 2, 3, 4}    # segunda a sexta (0 = segunda)

DIAS_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
           "sexta-feira", "sábado", "domingo"]


# --------------------------------------------------------------------------
# Estado do agente (persistido por telefone via checkpointer)
# --------------------------------------------------------------------------
class AgentState(TypedDict, total=False):
    telefone: str
    mensagem: str
    intencao: Optional[str]   # marcar | editar | cancelar | None
    nome: Optional[str]
    data: Optional[str]       # YYYY-MM-DD
    hora: Optional[str]       # HH:MM
    resposta: Optional[str]   # se preenchida, o grafo encerra o turno com ela


# --------------------------------------------------------------------------
# Saída estruturada do LLM
# --------------------------------------------------------------------------
class Interpretacao(BaseModel):
    intencao: Literal["marcar", "editar", "cancelar", "outro"] = Field(
        description="Intenção do usuário."
    )
    nome: Optional[str] = Field(None, description="Nome do paciente, se informado.")
    data: Optional[str] = Field(None, description="Data desejada em YYYY-MM-DD, se informada.")
    hora: Optional[str] = Field(None, description="Hora desejada em HH:MM (24h), se informada.")


PROMPT_SISTEMA = """Você interpreta mensagens de pacientes de uma clínica no WhatsApp.
Sua única tarefa é extrair a intenção e os campos da mensagem. NÃO confirme nada.

Agora é: {agora} (fuso America/Sao_Paulo).
Use isso para converter expressões como "amanhã", "sexta", "dia 20", "daqui a 2 dias"
em datas absolutas YYYY-MM-DD. "Sexta" significa a PRÓXIMA sexta futura.

Intenções:
- marcar: quer agendar uma consulta nova.
- editar: quer remarcar/alterar uma consulta existente (data e hora informadas são as NOVAS).
- cancelar: quer cancelar a consulta.
- outro: qualquer outra coisa (saudação, dúvida etc.).

Contexto da conversa:
- Intenção pendente: {pendente}
- Dados já coletados: nome={nome} data={data} hora={hora}

Se há uma intenção pendente e a mensagem apenas fornece dados que faltavam
(ex.: "às 15h", "meu nome é Ana"), MANTENHA a intenção pendente.
Preencha apenas os campos que aparecem na mensagem; deixe null nos demais."""


_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            temperature=0,
        ).with_structured_output(Interpretacao)
    return _llm


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def _agora() -> datetime:
    return datetime.now(TZ)


def _fmt(data: str, hora: str) -> str:
    d = date.fromisoformat(data)
    return f"{DIAS_PT[d.weekday()]}, {d.strftime('%d/%m/%Y')} às {hora}"


def _rejeitar(msg: str) -> dict:
    """Encerra o turno com uma mensagem e descarta data/hora inválidas."""
    return {"resposta": msg, "data": None, "hora": None}


def _limpar(msg: str) -> dict:
    """Encerra o turno com sucesso e zera o estado da conversa."""
    return {"resposta": msg, "intencao": None, "nome": None, "data": None, "hora": None}


# --------------------------------------------------------------------------
# Nós
# --------------------------------------------------------------------------
def interpretar(state: AgentState) -> dict:
    """LLM: extrai intenção e campos, mesclando com o que já foi coletado."""
    agora = _agora()
    prompt = PROMPT_SISTEMA.format(
        agora=f"{DIAS_PT[agora.weekday()]}, {agora.strftime('%d/%m/%Y %H:%M')}",
        pendente=state.get("intencao") or "nenhuma",
        nome=state.get("nome"),
        data=state.get("data"),
        hora=state.get("hora"),
    )
    r: Interpretacao = _get_llm().invoke([("system", prompt), ("human", state["mensagem"])])

    intencao = r.intencao
    # Rede de segurança: mensagem só com dados + intenção pendente = continua a pendente.
    if intencao == "outro" and state.get("intencao") and (r.nome or r.data or r.hora):
        intencao = state["intencao"]

    return {
        "intencao": None if intencao == "outro" else intencao,
        "nome": r.nome or state.get("nome"),
        "data": r.data or state.get("data"),
        "hora": r.hora or state.get("hora"),
        "resposta": None,  # reseta o turno anterior
    }


def responder_outro(state: AgentState) -> dict:
    return {
        "resposta": (
            "Olá! Posso te ajudar a *marcar*, *editar* ou *cancelar* uma consulta. "
            "O que você gostaria de fazer?"
        )
    }


def verificar_dados(state: AgentState) -> dict:
    """Garante que temos tudo que a intenção exige; senão, pergunta o que falta."""
    intencao = state["intencao"]

    if intencao in ("editar", "cancelar"):
        if not db_services.buscar_consulta_ativa(state["telefone"]):
            return {**_limpar("Não encontrei nenhuma consulta agendada para o seu número."),}

    obrigatorios = {
        "marcar": ["nome", "data", "hora"],
        "editar": ["data", "hora"],
        "cancelar": [],
    }[intencao]

    rotulos = {"nome": "seu nome", "data": "a data", "hora": "o horário"}
    faltando = [rotulos[c] for c in obrigatorios if not state.get(c)]
    if not faltando:
        return {}

    pedido = " e ".join(faltando)
    verbo = {"marcar": "marcar a consulta", "editar": "remarcar a consulta"}[intencao]
    return {"resposta": f"Para {verbo}, preciso de {pedido}."}


def validar_temporal(state: AgentState) -> dict:
    """Guardrail determinístico: formato, passado, dia útil, expediente."""
    try:
        d = date.fromisoformat(state["data"])
        h = time.fromisoformat(state["hora"])
    except (ValueError, TypeError):
        return _rejeitar("Não consegui entender a data ou o horário. Pode informar de novo?")

    if datetime.combine(d, h, tzinfo=TZ) <= _agora():
        return _rejeitar("Esse horário já passou. Por favor, escolha uma data e hora futuras.")

    if d.weekday() not in DIAS_UTEIS:
        return _rejeitar("Atendemos de segunda a sexta. Qual outro dia fica bom para você?")

    if not (HORA_ABERTURA <= h < HORA_FECHAMENTO) or h.minute % INTERVALO_MIN or h.second:
        return _rejeitar(
            f"Atendemos das {HORA_ABERTURA:%H:%M} às {HORA_FECHAMENTO:%H:%M}, "
            f"em horários de {INTERVALO_MIN} em {INTERVALO_MIN} minutos. "
            "Qual horário você prefere?"
        )
    return {}


def validar_disponibilidade(state: AgentState) -> dict:
    """Consulta a agenda (leitura). A garantia final contra conflito é a escrita atômica."""
    if db_services.horario_disponivel(state["data"], state["hora"]):
        return {}

    alternativas = db_services.proximos_horarios_livres(state["data"], limite=3)
    msg = "Esse horário não está disponível."
    if alternativas:
        msg += " Neste dia ainda tenho: " + ", ".join(alternativas) + "."
    else:
        msg += " Esse dia está lotado, pode escolher outra data?"
    return _rejeitar(msg)


def executar_marcar(state: AgentState) -> dict:
    ok = db_services.criar_consulta(
        state["telefone"], state["nome"], state["data"], state["hora"]
    )
    if not ok:
        # Perdeu a corrida: outra pessoa pegou o horário entre a validação e a escrita.
        return _rejeitar("Esse horário acabou de ser ocupado por outra pessoa. Quer escolher outro?")
    return _limpar(f"✅ Consulta marcada para {_fmt(state['data'], state['hora'])}, {state['nome']}.")


def executar_editar(state: AgentState) -> dict:
    ok = db_services.remarcar_consulta(state["telefone"], state["data"], state["hora"])
    if not ok:
        return _rejeitar("Esse horário acabou de ser ocupado. Quer escolher outro?")
    return _limpar(f"✅ Sua consulta foi remarcada para {_fmt(state['data'], state['hora'])}.")


def executar_cancelar(state: AgentState) -> dict:
    db_services.cancelar_consulta(state["telefone"])
    return _limpar("Sua consulta foi cancelada. Se quiser, posso marcar uma nova.")