"""Long-polling Telegram bot service."""

from __future__ import annotations

from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

from ._processor import TelegramMessageProcessor


class TelegramBot:
    """Telegram long-polling adapter that runs a configured agent."""

    def __init__(self, token: str, processor: TelegramMessageProcessor) -> None:
        self._application: Application = (  # type: ignore[type-arg]
            Application.builder().token(token).build()
        )
        self._application.add_handler(
            MessageHandler(filters.TEXT | filters.PHOTO, processor.process_message)
        )
        self._application.add_handler(
            CallbackQueryHandler(
                processor.process_callback,
                pattern=r"^(approve|reject|revise|confirm|cancel):(.+)$",
            )
        )

    def start(self) -> None:
        """Start the long-polling loop and block until shutdown."""
        self._application.run_polling()

    async def stop(self) -> None:
        """Stop the polling loop gracefully."""
        await self._application.stop()
