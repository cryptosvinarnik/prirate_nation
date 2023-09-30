import asyncio

from loguru import logger

from . import PirateEmail, PirateNation


async def worker(queue: asyncio.Queue):
    while True:
        pn: PirateNation = await queue.get()

        try:
            await pn.__aenter__()
        except Exception as e:
            logger.error("[{}] Failed to open session {}", pn.email, e)
            continue

        try:
            assert (await pn.get_launch_list()) == True, "Failed to register account"
            logger.success("[{}] Registered successfully", pn.email)

            assert (await pn.verify_email()) == True, "Failed to verify email"
            logger.success("[{}] Verified successfully", pn.email)
        except Exception as e:
            logger.error("[{}] Failed to register account: {}", pn.email, e)
        finally:
            await pn.__aexit__(None, None, None)

        if queue.empty():
            break

        await asyncio.sleep(1)


async def main():
    with open("./assets/proxies.txt") as file:
        proxies = [line.strip() for line in file.read().splitlines()]

    logger.success("{} proxies are loaded successfully", len(proxies))

    with open("./assets/mails.txt") as file:
        mails = [line.strip().split(":") for line in file.read().splitlines()]

    logger.success("{} mails are loaded successfully", len(proxies))

    ref_code = input("Input ref code(or press enter for empty): ")

    queue = asyncio.Queue()

    workers = [asyncio.create_task(worker(queue)) for _ in range(5)]

    if ref_code == "":
        ref_code = None

    logger.info("Ref code is not provided, using none.")

    for mail, proxy in zip(mails, proxies):
        try:
            queue.put_nowait(
                PirateNation(
                    mail[0],
                    PirateEmail(mail[2], mail[0].split("@")[0], mail[1]),
                    proxy,
                    ref_code,
                )
            )

        except Exception as e:
            logger.error(e)

    await asyncio.gather(*workers, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        logger.error(e)
