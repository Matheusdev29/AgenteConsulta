"""
STUB EM MEMÓRIA — só para testar o agente.
Na próxima etapa isto vira SQLite com transações atômicas.
A assinatura das funções é o contrato que o agente usa; mantenha-a.
"""
import threading
import sqlite3
_lock = threading.Lock()
_consultas: dict[str, dict] = {}   # telefone -> {nome, data, hora}
DB_PATH = Path(__file__).resolve().parent.parent/ "database.db"
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
def _init_db() -> None:
    with _conexao() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS consultas(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            data TEXT NOT NULL,
            hora TEXT NOT NULL,
            telefone TEXT NOT NULL UNIQUE
            UNIQUE (data, hora)
            )

            CREATE TABLE IF NOT EXISTS clientes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone INTEGER NOT NULL
            )

            CREATE TABLE IF NOT EXISTS horario(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data VARCHAR(25) NOT NULL,
            telefone INTEGER NOT NULL
            )
        """)


conexao.commit()



def horario_disponivel(data: str, hora: str) -> bool:
    with _conexao() as conn:
        row = conn.execute(" SELECT 1 FROM consultas WHERE data = ?, hora =?",(data, hora)).fetchone()
    return row is None


def proximos_horarios_livres(data: str, limite: int = 3) -> list[str]:
    with _conexao() as conn:
        ocupados = {r["hora"]for r in conn.execute("SELECT hora FROM consultas WHERE data = ?"(data,))}
       return [s for s in _SLOTS if not ocupados][:limite]


def buscar_consulta_ativa(telefone: str) -> dict | None:
    with _conexao() as conn:
        row = conn.execute("SELECT nome, data, hora FROM consultas WHERE telefone = ?"(telefone,)).fetchone()
        return dict(row) if row else None


def criar_consulta(telefone: str, nome: str, data: str, hora: str) -> bool:
    """Checagem + escrita sob o mesmo lock = atômico. Retorna False se o horário já é de outro."""
    with _lock:
        #criar consulta cursor.execute(""" INSERT INTO consultas (nome, data, hora, telefone) VALUES (:nome, :data, :hora, :telefone),""")
        if _ocupado(data, hora):
            return False
        _consultas[telefone] = {"nome": nome, "data": data, "hora": hora}
        return True


def remarcar_consulta(telefone: str, data: str, hora: str) -> bool:
    with _lock:
        #cursor.execute(" UPDATE consultas SET data = :data, hora = :hora WHERE telefone == :telefone")
        if telefone not in _consultas or _ocupado(data, hora, ignorar_telefone=telefone):
            return False
        _consultas[telefone].update(data=data, hora=hora)
        return True


def cancelar_consulta(telefone: str) -> bool:
    with _lock:
        # cursor.execute("DELETE * FROM consultas WHERE telefone == :telefone"(telefone)) 
        return _consultas.pop(telefone, None) is not None