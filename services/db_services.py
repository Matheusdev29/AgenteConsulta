"""
STUB EM MEMÓRIA — só para testar o agente.
Na próxima etapa isto vira SQLite com transações atômicas.
A assinatura das funções é o contrato que o agente usa; mantenha-a.
"""
import threading
import sqlite3
from contextlib import contextmanager
from pathlib import Path

_consultas: dict[str, dict] = {}   # telefone -> {nome, data, hora}
DB_PATH = Path(__file__).resolve().parent.parent/ "database"
_SLOTS = [f"{h:02d}:{m:02d}" for h in range(8, 18) for m in (0, 30)]

@contextmanager
def _conexao():
    conn = sqlite3.connect(DB_PATH, timeout=10)  # espera se o banco estiver ocupado
    conn.row_factory = sqlite3.Row               # acessa colunas por nome
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# --------------------------------------------------------------------------
# Conectando com o sqlite
# --------------------------------------------------------------------------
def init_db() -> None:
    with _conexao() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS consultas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            data TEXT NOT NULL,
            hora TEXT NOT NULL,
            telefone TEXT NOT NULL UNIQUE,
            UNIQUE (data, hora)
        );
    """)




def horario_disponivel(data: str, hora: str) -> bool:
    with _conexao() as conn:
        row = conn.execute(" SELECT 1 FROM consultas WHERE data = ? AND hora = ?",(data, hora)).fetchone()
    return row is None


def proximos_horarios_livres(data: str, limite: int = 3) -> list[str]:
    with _conexao() as conn:
        ocupados = {r["hora"]for r in conn.execute("SELECT hora FROM consultas WHERE data = ?",(data,))}
    return [s for s in _SLOTS if not ocupados][:limite]


def buscar_consulta_ativa(telefone: str) -> dict | None:
    with _conexao() as conn:
        row = conn.execute("SELECT nome, data, hora FROM consultas WHERE telefone = ?",(telefone,)).fetchone()
        return dict(row) if row else None


def criar_consulta(telefone: str, nome: str, data: str, hora: str) -> bool:
    try:
        with _conexao() as conn:
            conn.execute("INSERT INTO consultas (nome, data, hora, telefone) VALUES ( ?, ?, ?, ?)",(nome, data, hora, telefone),)    
        return True
    except sqlite3.IntegrityError:
        return False


def remarcar_consulta(telefone: str, data: str, hora: str) -> bool:
    try:
        with _conexao() as conn:
            cur = conn.execute(" UPDATE consultas SET data = ?, hora = ? WHERE telefone = ?", (data, hora, telefone),)
            return cur.rowcount > 0
    except sqlite3.IntegrityError:
        return False

def cancelar_consulta(telefone: str) -> bool:
    with _conexao() as conn:
        cur = conn.execute("DELETE FROM consultas WHERE telefone = ?",(telefone,))
    return cur.rowcount > 0