"""Tracks the Waterloo CSC office status.

Updates a single message in the webhook channel as to not flood the feed.

Instructions:

- Change the url at the end to point at the desired webhook.

Dependencies:

- dhooks: 1.1.4
- apscheduler: 3.9

"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from dhooks import Embed, Webhook

logging.basicConfig(format="%(asctime)s %(message)s : ", level=logging.INFO)

# codey emojis pulled from discord
CODEY_SAD = "https://cdn.discordapp.com/emojis/848375346126651422.webp?size=160&quality=lossless"
CODEY_HAPPY = "https://cdn.discordapp.com/emojis/825056099786817617.webp?size=160&quality=lossless"
CODEY_STRESSED = "https://cdn.discordapp.com/emojis/825056100738924644.webp?size=160&quality=lossless"

OFFICE_CLOSED_COLOR = 0xFF2002
OFFICE_OPEN_COLOR = 0x4B90FF
OFFICE_BROKE_COLOR = 0xFFCC00

STATUS_URL = "https://csclub.uwaterloo.ca/~n3parikh/office-status.json"


def fetch_status() -> dict[str, int] | None:
    """Fetches the status of the office from STATUS_URL.

    Returns
    --------
    dict[str, int]
        None if anything goes wrong, means the sensor is down and we
        should trigger a warning. Or, the desired dict.
    """

    # blank except since we don't care what went wrong, just that it did.
    try:
        ret = requests.get(STATUS_URL).json()
        # will error if "time" DNE
        if ret["time"]:
            return ret
    except:
        return None


def run(scheduler: BlockingScheduler):
    """Sets up the cron job to run the main job every 5 minutes."""
    # https://apscheduler.readthedocs.io/en/3.x/modules/triggers/cron.html?highlight=cron#module-apscheduler.triggers.cron
    scheduler.add_job(
        main_func,
        "cron",
        minute=f"*",  # update every minute since that's how often the sensor checks
    )

    scheduler.start()


def gen_message() -> int:
    """Generates a dummy message for the sole purpose of getting its message id.

    To be updated via `update_message`.
    """
    result = requests.post(
        f"https://discord.com/api/webhooks/{webhook_obj.id}/{webhook_obj.token}",
        json={"content": "temp"},
        params={"wait": True},
    )

    return result.json()["id"]


def update_message(embed: Embed):
    """Updates the message at office_status.message_id.

    If the message is not updated cleanly, we assume the message we want to update has
    been deleted so we send a dummy message then update.

    Parameters
    ----------
    embed: Embed
        The embed used to replace the exisiting message

    """
    result = requests.patch(
        f"https://discord.com/api/webhooks/{webhook_obj.id}/{webhook_obj.token}/messages/{office_status.message_id}",
        json={"embeds": [embed.to_dict()]},
    )

    if result.status_code != 200:
        office_status.message_id = gen_message()
        logging.warning(
            f"Message has been deleted. New message id: {office_status.message_id}"
        )
        requests.patch(
            f"https://discord.com/api/webhooks/{webhook_obj.id}/{webhook_obj.token}/messages/{office_status.message_id}",
            json={"embeds": [embed.to_dict()]},
        )

    logging.info(f"Updated message")


def main_func(status: dict[str, int] | None = None):
    """Governs whether ot not an embed is posted.

    Checks the status of the office, then sees if it's
    different from the current status, or is broken.

    If so, post an embed to alert users about changes.

    Parameters
    ----------
    status: dict[str, int] | None
        Not meant to be used in prod. Makes testing a bit more convenient.

    """
    if status is None:
        status = fetch_status()  # can return None

    maybe = office_status.update_from_status(status)

    if maybe is not None:
        update_message(embed=maybe)


class Status(Enum):
    """Represents the possible states of the office.

    Parameters
    ----------
    OPEN
        The office is open and good to go.
    CLOSED
        The office is closed.
    BROKE
        Something has gone wrong with the sensor, unaware of office status.
    """

    OPEN = 1
    CLOSED = 2
    BROKE = 3

    def to_str(self) -> str:
        """Returns a human readable representation of the Enum."""
        match self:
            case Status.OPEN:
                return "Open"
            case Status.CLOSED:
                return "Closed"
            case Status.BROKE:
                return "Unavailable"

    @classmethod
    def from_int(cls, status_val: int) -> Status:
        """Convenience method to generate Status from an integer.

        Status value is received from `fetch_status`. Possible values are:
        `0`,`1`,`-1`
        """
        match status_val:
            case 1:
                return cls.OPEN
            case 0:
                return cls.CLOSED
            case -1:
                return cls.BROKE
            case _:
                # this should never happen
                # but if it does...
                return cls.BROKE


@dataclass
class OfficeStatus:
    """Class representing the status of the CSC Office.

    Parameters
    ----------
    message_id: int
        The id of the message that will be continually updated. Must be provided.
        If it suddenly becomes unavailable then it will be regenerated.
    last_status_change: datetime
        The last time the office changed its status. Provided as a time from epoch from
        the `fetch_status` function.
    office_stat: Status
        The current actual office status, represented by a `Status` Enum that can
        hold three possible statuses.
    """

    message_id: int
    last_status_change: datetime = datetime.fromtimestamp(1000)
    office_stat: Status = Status.CLOSED

    def update_from_status(self, dict_val: dict[str, int] | None) -> Embed | None:
        """Receives a status and posts an embed if the status has changed, or gone wrong.

        Parameters
        ----------
        dict_val: dict[str, int] | None
            A dict if a valid status has been received, otherwise,
            will send out a "Things Aren't working" message.

        Returns
        -------
        Embed | None
            Sends out an embed if the status has changed, otherwise, do nothing.
            (Even in the case of non-operational status)
        """
        changed: bool = False

        if dict_val is None:
            if self.office_stat != Status.BROKE:
                self.office_stat = Status.BROKE
                self.last_status_change = datetime.now()
                changed = True
        else:
            self.last_status_change = datetime.fromtimestamp(dict_val["time"])
            of_status: int = dict_val["status"]

            if (ret_stat := Status.from_int(of_status)) != self.office_stat:
                self.office_stat = ret_stat
                changed = True

        if changed:
            embed = self.create_embed()
            return embed

        logging.debug("No changes detected in update_from_status")

    def create_embed(
        self, office_stat: Status | None = None, office_time: datetime | None = None
    ):
        """Creates an embed according to discord.py (now defunct) semantics.

        Parameters
        ----------
        office_stat: Status | None
            Optional param used if creating own embed. Influences the colour of the embed and the
            declared status of the office.
        office_time: datetime | None
            Optional param used if creating own embed. Represents the time that
            the message will contain

        Note
        ----
        Refer to

        https://cog-creators.github.io/discord-embed-sandbox/

        to design your own embed.
        """

        office_stat = self.office_stat if office_stat is None else office_stat
        office_time = self.last_status_change if office_time is None else office_time

        match office_stat:
            case Status.OPEN:
                description = f"""
The office is open 🥳!
"""
                color = OFFICE_OPEN_COLOR
                logo_link = CODEY_HAPPY

            case Status.CLOSED:
                description = f"""
The office is closed 😭!
"""
                color = OFFICE_CLOSED_COLOR
                logo_link = CODEY_SAD

            case Status.BROKE:
                description = f"""
Something went wrong!
Please wait until detection goes back online.
"""
                color = OFFICE_BROKE_COLOR
                logo_link = CODEY_STRESSED

        embed = Embed(
            title="Office Status",
            # url=self.link,
            color=color,
            description=description,
        )

        embed.set_thumbnail(url=logo_link)
        embed.set_footer(text=f"Source: {STATUS_URL}")
        embed.add_field(
            name=f"{office_stat.to_str()} since:",
            value=f"{office_time.strftime('%A, %I:%M%p')}",
            inline=False,
        )

        return embed


# tests
# time values are arbitrary


def test_open():
    status = {"status": 1, "time": 13123123412}
    main_func(status)


def test_closed():
    status = {"status": 0, "time": 3123123412}
    main_func(status)


def test_broke():
    status = {"status": -1, "time": 3123123412}
    main_func(status)


if __name__ == "__main__":
    url = "https://discord.com/api/webhooks/993612639211098222/zsEB8qBWPN8ITFVhcAuW9p2VxMkTqI9yztegWyLMy4nrW4VGniByybYXTu5n0e47mBY6"

    webhook_obj = Webhook(url)
    scheduler = BlockingScheduler()
    office_status = OfficeStatus(message_id=gen_message())

    # update message in channel from test message
    curr_status = fetch_status()
    curr_status = (
        Status.BROKE if curr_status is None else Status.from_int(curr_status["status"])
    )
    update_message(
        office_status.create_embed(office_stat=curr_status, office_time=datetime.now())
    )

    # terrible tests but yolo

    # test_open()
    # test_closed()
    # test_broke()

    run(scheduler)
