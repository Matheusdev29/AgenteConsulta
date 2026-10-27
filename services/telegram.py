"""
Canal Telegram: só sabe criar o bot, montar botões e enviar mensagens.
Não tem nenhuma lógica de agendamento (isso fica no agent/).
Este arquivo faz o papel que o whatsapp.py terá depois.
"""
import logging
import os

import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

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


def montar_teclado(opcoes: list[dict] | None) -> InlineKeyboardMarkup | None:
    """
    Converte as opções do agente em botões do Telegram.
    Formato de cada opção: {"rotulo": "texto do botão", "valor": "id_da_acao"}
    O 'valor' vira o callback_data (máx. 64 bytes), devolvido quando o botão é tocado.
    """
    if not opcoes:
        return None
    teclado = InlineKeyboardMarkup(row_width=1)   # um botão por linha
    teclado.add(*[
        InlineKeyboardButton(text=o["rotulo"], callback_data=o["valor"])
        for o in opcoes
    ])
    return teclado


def mostrar_digitando(chat_id: int | str) -> None:
    """Mostra 'digitando...' enquanto o LLM pensa. Falhar aqui não pode derrubar nada."""
    try:
        get_bot().send_chat_action(chat_id, "typing")
    except Exception:
        log.warning("Não foi possível enviar o status 'digitando'.", exc_info=True)


def enviar_mensagem(chat_id: int | str, texto: str, opcoes: list[dict] | None = None) -> None:
    """Envia texto puro, com botões se houver opções. Erros são registrados, não propagados."""
    try:
        get_bot().send_message(chat_id, texto, reply_markup=montar_teclado(opcoes))
    except Exception:
        log.exception("Falha ao enviar mensagem para o chat %s", chat_id)


def confirmar_clique(callback_id: str) -> None:
    """Obrigatório após um clique: senão o botão fica com o 'relógio' girando no app."""
    try:
        get_bot().answer_callback_query(callback_id)
    except Exception:
        log.warning("Não foi possível confirmar o clique.", exc_info=True)


def remover_botoes(chat_id: int | str, message_id: int) -> None:
    """Tira os botões da mensagem já usada, para não clicarem de novo em menu antigo."""
    try:
        get_bot().edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
    except Exception:
        log.warning("Não foi possível remover os botões.", exc_info=True)