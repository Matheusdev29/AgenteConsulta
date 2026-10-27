"""
Desenho do fluxo (LangGraph).

START -> interpretar -+-> responder_outro -> END
                      |
                      +-> verificar_dados -+-> END (falta dado / sem consulta)
                                           +-> executar_cancelar -> END
                                           +-> validar_temporal -+-> END (rejeitou)
                                                                 +-> validar_disponibilidade -+-> END (rejeitou)
                                                                                              +-> executar_marcar -> END
                                                                                              +-> executar_editar -> END
Regra: se o estado tem `resposta`, o turno termina e ela é enviada ao usuário.
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent import nodes
from agent.nodes import AgentState


def _rota_apos_interpretar(state: AgentState) -> str:
    return "verificar_dados" if state.get("intencao") else "responder_outro"


def _rota_apos_verificar(state: AgentState) -> str:
    if state.get("resposta"):
        return END
    return "executar_cancelar" if state["intencao"] == "cancelar" else "validar_temporal"


def _rota_apos_temporal(state: AgentState) -> str:
    return END if state.get("resposta") else "validar_disponibilidade"


def _rota_apos_disponibilidade(state: AgentState) -> str:
    if state.get("resposta"):
        return END
    return "executar_marcar" if state["intencao"] == "marcar" else "executar_editar"


def criar_agente(checkpointer=None):
    """Compila o grafo. O checkpointer guarda o estado por thread_id (= telefone)."""
    g = StateGraph(AgentState)

    g.add_node("interpretar", nodes.interpretar)
    g.add_node("responder_outro", nodes.responder_outro)
    g.add_node("verificar_dados", nodes.verificar_dados)
    g.add_node("validar_temporal", nodes.validar_temporal)
    g.add_node("validar_disponibilidade", nodes.validar_disponibilidade)
    g.add_node("executar_marcar", nodes.executar_marcar)
    g.add_node("executar_editar", nodes.executar_editar)
    g.add_node("executar_cancelar", nodes.executar_cancelar)

    g.add_edge(START, "interpretar")
    g.add_conditional_edges("interpretar", _rota_apos_interpretar,
                            ["verificar_dados", "responder_outro"])
    g.add_conditional_edges("verificar_dados", _rota_apos_verificar,
                            ["executar_cancelar", "validar_temporal", END])
    g.add_conditional_edges("validar_temporal", _rota_apos_temporal,
                            ["validar_disponibilidade", END])
    g.add_conditional_edges("validar_disponibilidade", _rota_apos_disponibilidade,
                            ["executar_marcar", "executar_editar", END])

    for no in ("responder_outro", "executar_marcar", "executar_editar", "executar_cancelar"):
        g.add_edge(no, END)

    return g.compile(checkpointer=checkpointer or MemorySaver())


def responder_completo(agente, telefone: str, mensagem: str) -> dict:
    """Devolve o texto e as opções (botões) do turno."""
    resultado = agente.invoke(
        {"telefone": telefone, "mensagem": mensagem},
        config={"configurable": {"thread_id": telefone}},
    )
    return {"texto": resultado["resposta"], "opcoes": resultado.get("opcoes")}


def responder(agente, telefone: str, mensagem: str) -> str:
    """Versão só texto. Mantém o test_agente.py funcionando sem alterações."""
    return responder_completo(agente, telefone, mensagem)["texto"]