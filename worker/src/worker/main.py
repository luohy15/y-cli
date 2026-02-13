"""Worker: polls DynamoDB cache for pending chats and executes them (local dev)."""

import asyncio
import os

from dotenv import load_dotenv
from loguru import logger

from storage.cache import claim_pending_chat
from worker.runner import run_chat

load_dotenv()


POLL_INTERVAL = int(os.environ.get("WORKER_POLL_INTERVAL", "2"))


async def poll_loop():
    logger.info("Polling for chats every {}s", POLL_INTERVAL)
    while True:
        chat = claim_pending_chat()
        if chat:
            chat_id = chat["id"]
            logger.info("Claimed chat {}", chat_id)
            try:
                await run_chat(chat)
                logger.info("Finished chat {}", chat_id)
            except Exception as e:
                logger.exception("Chat {} failed: {}", chat_id, e)
        else:
            await asyncio.sleep(POLL_INTERVAL)


def main():
    asyncio.run(poll_loop())


if __name__ == "__main__":
    main()
