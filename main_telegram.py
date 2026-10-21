"""
Ponto de entrada para testar o agente pelo Telegram (long polling).
Uso: python main_telegram.py
"""
import logging

from dotenv import load_dotenv

load_dotenv()  # precisa vir antes dos imports que leem variáveis de ambiente

from agent.graph import criar_agente, responder          # noqa: E402
from services.db_services import init_db                 # noqa: E402
from services.telegram import enviar_mensagem, get_bot, mostrar_digitando  # noqa: E402

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
@bot.message_handler(content_types=["text"])
def tratar_texto(message):
    chat_id = message.chat.id
    texto = (message.text or "").strip()
    if not texto:
        return

    log.info("Mensagem de %s: %s", chat_id, texto)
    mostrar_digitando(chat_id)

    try:
        # str(chat_id): o agente e o banco tratam o "telefone" como texto.
        resposta = responder(agente, str(chat_id), texto)
    except Exception:
        log.exception("Erro ao processar a mensagem do chat %s", chat_id)
        resposta = MSG_ERRO

    enviar_mensagem(chat_id, resposta)


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