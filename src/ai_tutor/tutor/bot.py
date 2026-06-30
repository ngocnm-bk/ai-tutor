from __future__ import annotations

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters,
)

from ai_tutor.config import Config
from ai_tutor.tutor.students import register_student
from ai_tutor.tutor.tutor_service import answer_question


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Chào con! Đây là gia sư AI. Hãy đăng ký lớp trước: /dangky 3 hoặc /dangky 6. "
        "Sau đó con cứ nhắn câu hỏi về bài học nhé."
    )


async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or args[0] not in ("3", "6"):
        await update.message.reply_text("Cú pháp: /dangky 3  hoặc  /dangky 6")
        return
    user = update.effective_user
    register_student(context.bot_data["conn"], user.id, user.first_name, int(args[0]))
    await update.message.reply_text(f"Đã đăng ký {user.first_name} lớp {args[0]}. Con hỏi bài được rồi nhé!")


async def question_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    answer = answer_question(
        context.bot_data["conn"], context.bot_data["cfg"], context.bot_data["claude"],
        user.id, user.first_name, update.message.text,
    )
    await update.message.reply_text(answer)


def build_application(cfg: Config, conn, claude) -> Application:
    app = Application.builder().token(cfg.telegram_bot_token).build()
    app.bot_data["cfg"] = cfg
    app.bot_data["conn"] = conn
    app.bot_data["claude"] = claude
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("dangky", register_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, question_handler))
    return app
