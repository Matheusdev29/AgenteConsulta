"""
Ponto de entrada para testar o agente pelo Telegram (long polling).
Uso: python main_telegram.py
"""
import logging

from dotenv import load_dotenv

load_dotenv()  # precisa vir antes dos imports que leem variáveis de ambiente

from agent.graph import criar_agente, responder_completo
from agent.nodes import TEXTO_DA_ACAO         # noqa: E402
from services.db_services import init_db                 # noqa: E402
from services.telegram import (enviar_mensagem, get_bot, mostrar_digitando, remover_botoes, confirmar_clique,  # noqa: E402
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main_telegram")

# --------------------------------------------------------------------------
# Inicialização (roda uma vez)
# --------------------------------------------------------------------------
init_db()
agente = criar_agente()   # UM agente só, para manter a memória das conversas
bot = get_bot()

MSG_ERRO = "Desculpe, tive um problema aqui. Pode tentar de novo em instantes?"
MSG_NAO_TEXTO = "Por enquanto só consigo ler mensagens de texto. Pode escrever o que precisa?"


# --------------------------------------------------------------------------
# Handlers (o Telegram chama a função certa conforme o tipo da mensagem)
# --------------------------------------------------------------------------

def processar(chat_id: int, texto: str) -> None:
    """Caminho único: tanto texto digitado quanto clique de botão passam por aqui."""
    mostrar_digitando(chat_id)
    try:
        # str(chat_id): o agente e o banco tratam o "telefone" como texto.
        r = responder_completo(agente, str(chat_id), texto)
        enviar_mensagem(chat_id, r["texto"], r["opcoes"])
    except Exception:
        log.exception("Erro ao processar a mensagem do chat %s", chat_id)
        enviar_mensagem(chat_id, MSG_ERRO)
 
 
# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------
@bot.message_handler(content_types=["text"])
def tratar_texto(message):
    texto = (message.text or "").strip()
    if not texto:
        return
    log.info("Mensagem de %s: %s", message.chat.id, texto)
    processar(message.chat.id, texto)
 
 
@bot.callback_query_handler(func=lambda call: call.data in TEXTO_DA_ACAO)
def tratar_botao(call):
    chat_id = call.message.chat.id
    log.info("Botão '%s' tocado por %s", call.data, chat_id)
 
    confirmar_clique(call.id)                            # para o relógio do botão
    remover_botoes(chat_id, call.message.message_id)     # evita cliques em menu antigo
    processar(chat_id, TEXTO_DA_ACAO[call.data])         # o clique vira uma frase para o agente
 


@bot.message_handler(
    content_types=["photo", "voice", "audio", "video", "video_note",
                   "sticker", "document", "location", "contact"]
)
def tratar_outros(message):
    enviar_mensagem(message.chat.id, MSG_NAO_TEXTO)


# --------------------------------------------------------------------------
# Execução
# --------------------------------------------------------------------------
if __name__ == "__main__":
    bot.remove_webhook()   # evita o erro 409 se o token já teve um webhook
    log.info("Bot iniciado. Pressione Ctrl+C para parar.")
    # skip_pending: ignora mensagens enviadas enquanto o bot estava desligado
    bot.infinity_polling(skip_pending=True)