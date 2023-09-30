from aiohttp import ClientSession
from aiohttp_socks import ProxyConnector
from loguru import logger
from asyncio import sleep

import re
import aioimaplib


import email
from typing import AnyStr, Optional

from aioimaplib import aioimaplib


class _EmailContextManager():

    def __init__(self, host: str, email: str, password: str, mailbox: str = 'INBOX'):
        self.host = host
        self.email = email
        self.password = password

        self.mailbox = mailbox

    async def __aenter__(self) -> aioimaplib.IMAP4_SSL:
        self._client = aioimaplib.IMAP4_SSL(host=self.host)

        await self._client.wait_hello_from_server()
        await self._client.login(self.email, self.password)

        await self._client.select(self.mailbox)

        return self._client

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._client.logout()


def decode_value(value: AnyStr, encoding: Optional[str] = None) -> str:
    """Converts value to utf-8 encoding"""
    if isinstance(encoding, str):
        encoding = encoding.lower()
    if isinstance(value, bytes):
        try:
            return value.decode(encoding or 'utf-8', 'ignore')
        except LookupError:  # unknown encoding
            return value.decode('utf-8', 'ignore')
    return value


class PirateEmail:

    def __init__(self, host: str, email: str, password: str):
        self.host = host
        self.email = email
        self.password = password

    async def get_verify_link(self) -> str:
        async with _EmailContextManager(self.host, self.email, self.password) as client:

            _, data = await client.search('(HEADER Subject "Verify Email Address - Pirate Nation - Free to Play")')

            _, data = await client.fetch(data[0].decode("US-ASCII").split()[0], "(RFC822)")

            text = ""

            message = email.message_from_bytes(data[1])
            for part in message.walk():
                if part.get_content_maintype() == "multipart" or part.get_filename():
                    continue
                if part.get_content_type() == "text/html":
                    text = decode_value(part.get_payload(
                        decode=True), part.get_content_charset())
                    break

        urls = re.findall(r"(https?://\S*verify\S*)<", text)

        if urls:
            return urls[0]

        raise Exception("Verify link not found")


class PirateNation:
    def __init__(
        self, email: str, imbox: PirateEmail, proxy: str = None, ref: str = None
    ) -> None:
        self.__http = ClientSession(
            connector=ProxyConnector.from_url(proxy) if proxy else None
        )
        self.ref = ref

        if "@" not in email:
            raise Exception(
                "Email is not contains mail host with @ symbol: foo@gmail.com"
            )

        self.email = email
        self.imbox = imbox

    async def __aenter__(self):
        await self.__http.__aenter__()

        return self

    async def __aexit__(self, *args):
        await self.__http.__aexit__(*args)

    async def verify_email(self) -> bool:
        logger.info("[{}] Waiting for a message in email", self.email)

        for _ in range(60):
            try:
                link = await self.imbox.get_verify_link()
                break
            except Exception:
                logger.warning(
                    "[{}] Message not found, waiting 1 second", self.email)
            finally:
                await sleep(1)
        else:
            return False

        verify_text = await (await self.__http.get(link)).text()

        return (
            "You&#039;re on the stowaway list!"
            in verify_text
        )

    async def get_launch_list(self):
        url = "https://getlaunchlist.com/s/Hdh76v"

        if self.ref:
            url += "?ref=" + self.ref

        logger.info(
            "[{}] Sending POST request to getlaunchlist.com.", self.email)

        data = await self.__http.post(
            url,
            json={"email": self.email},
            headers={
                "content-type": "application/json",
                "referer": "https://piratenation.game/",
                "origin": "https://piratenation.game",
                "accept": "application/json",
            },
        )

        logger.success("[{}] Request is success", self.email)

        return (await data.json()).get("ok", False)
