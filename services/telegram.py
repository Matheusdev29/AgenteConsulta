"""
Canal Telegram: só sabe criar o bot e enviar mensagens.
Não tem nenhuma lógica de agendamento (isso fica no agent/).
Este arquivo faz o papel que o whatsapp.py terá depois.
"""
import logging
import os

import telebot

log = logging.getLogger(__name__)

_bot: telebot.TeleBot | None = None


def get_bot() -> telebot.TeleBot:
    """Cria o bot na primeira chamada e reutiliza nas seguintes."""
    global _bot
    if _bot is None:
        token = os.getenv("TELEGRAM_TOKEN")
        if not token:
            raise RuntimeError("TELEGRAM_TOKEN não encontrado. Confira o seu arquivo .env.")
        # threaded=False: uma mensagem por vez. Mais simples e evita que duas
        # mensagens rápidas do mesmo usuário rodem o agente ao mesmo tempo.
        _bot = telebot.TeleBot(token, threaded=False)
    return _bot


def mostrar_digitando(chat_id: int | str) -> None:
    """Mostra 'digitando...' enquanto o LLM pensa. Falhar aqui não pode derrubar nada."""
    try:
        get_bot().send_chat_action(chat_id, "typing")
    except Exception:
        log.warning("Não foi possível enviar o status 'digitando'.", exc_info=True)


def enviar_mensagem(chat_id: int | str, texto: str) -> None:
    """Envia texto puro. Se o Telegram recusar, registra o erro em vez de quebrar o bot."""
    try:
        get_bot().send_message(chat_id, texto)
    except Exception:
        log.exception("Falha ao enviar mensagem para o chat %s", chat_id)