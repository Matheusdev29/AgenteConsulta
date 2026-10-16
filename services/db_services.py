"""
STUB EM MEMÓRIA — só para testar o agente.
Na próxima etapa isto vira SQLite com transações atômicas.
A assinatura das funções é o contrato que o agente usa; mantenha-a.
"""
import threading

_lock = threading.Lock()
_consultas: dict[str, dict] = {}   # telefone -> {nome, data, hora}

_SLOTS = [f"{h:02d}:{m:02d}" for h in range(8, 18) for m in (0, 30)]


def _ocupado(data: str, hora: str, ignorar_telefone: str | None = None) -> bool:
    return any(
        c["data"] == data and c["hora"] == hora and tel != ignorar_telefone
        for tel, c in _consultas.items()
    )


def horario_disponivel(data: str, hora: str) -> bool:
    with _lock:
        return not _ocupado(data, hora)


def proximos_horarios_livres(data: str, limite: int = 3) -> list[str]:
    with _lock:
        return [s for s in _SLOTS if not _ocupado(data, s)][:limite]


def buscar_consulta_ativa(telefone: str) -> dict | None:
    with _lock:
        return _consultas.get(telefone)


def criar_consulta(telefone: str, nome: str, data: str, hora: str) -> bool:
    """Checagem + escrita sob o mesmo lock = atômico. Retorna False se o horário já é de outro."""
    with _lock:
        if _ocupado(data, hora):
            return False
        _consultas[telefone] = {"nome": nome, "data": data, "hora": hora}
        return True


def remarcar_consulta(telefone: str, data: str, hora: str) -> bool:
    with _lock:
        if telefone not in _consultas or _ocupado(data, hora, ignorar_telefone=telefone):
            return False
        _consultas[telefone].update(data=data, hora=hora)
        return True


def cancelar_consulta(telefone: str) -> bool:
    with _lock:
        return _consultas.pop(telefone, None) is not None