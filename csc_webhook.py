"""Tracks the Waterloo CSC office status.

Instructions:

- Change the url at the end to point at the desired webhook.

Dependencies:

- dhooks: 1.1.4
- apscheduler: 3.9

"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from dhooks import Embed, Webhook

# codey emojis pulled from discord
CODEY_SAD = "https://cdn.discordapp.com/emojis/848375346126651422.webp?size=160&quality=lossless"
CODEY_HAPPY = "https://cdn.discordapp.com/emojis/825056099786817617.webp?size=160&quality=lossless"
CODEY_STRESSED = "https://cdn.discordapp.com/emojis/825056100738924644.webp?size=160&quality=lossless"

OFFICE_CLOSED_COLOR = 0xFF2002
OFFICE_OPEN_COLOR = 0x4B90FF
OFFICE_BROKE_COLOR = 0xFFCC00

STATUS_URL = "https://csclub.uwaterloo.ca/~n3parikh/office-status.json"


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

    @classmethod
    def from_int(cls, int_val: int) -> Status:
        """Convenience method to generate Status from a boolean.

        Only works for OPEN/CLOSED since BROKE means no bool was received.
        """
        match int_val:
            case 1:
                return cls.OPEN
            case 0:
                return cls.CLOSED
            case -1:
                return cls.BROKE
            case _:
                # this should never happen
                return cls.BROKE


def fetch_status() -> dict[str, int] | None:
    """Fetches the status of the office from STATUS_URL.

    Returns
    --------
    dict[str, int]
        None if anything goes wrong, means the sensor is down and we
        should trigger a warning. Or, the desired dict.
    """

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
        minute=f"*/5",
    )

    scheduler.start()


def post_embed(embed: Embed):
    """Sends the embed to the desired channel."""
    webhook_obj.send(embed=embed)


def main_func(status: dict[str, int] | None = None):
    """Governs whether ot not an embed is posted.

    Checks the status of the office, then sees if it's
    different from the current status, or is broken.

    If so, post an embed to alert users about changes

    Parameters
    ----------

    status
        Not meant to be used in prod. Makes testing a bit more convenient.

    """
    if status is None:
        status = fetch_status()  # can return None

    maybe = office_status.update_from_status(status)

    if maybe is not None:
        post_embed(maybe)


@dataclass
class OfficeStatus:
    open_since: datetime = datetime.fromtimestamp(1000)
    office_stat: Status = Status.CLOSED

    def update_from_status(self, dict_val: dict[str, int] | None) -> Embed | None:
        """Receives a status and posts an embed if the status has changed, or gone wrong.

        Parameters
        ----------
        dict_val: dict[str, int] | None
            A dict if a valid status has been received, otherwise, will send out a "Things Aren't working"message.

        Returns
        -------
        Embed | None
            Sends out an embed if the status has changed, otherwise, do nothing. (Even in the case of non-operational status)
        """
        changed: bool = False

        if dict_val is None and self.office_stat!= Status.BROKE:
            self.office_stat = Status.BROKE
            changed = True
        else:
            of_status:int = dict_val["status"]
            if (ret_stat := Status.from_int(of_status)) != self.office_stat:
                self.office_stat = ret_stat
                changed = True

        if changed:
            embed = self.create_embed()
            return embed

    def create_embed(self):
        """Creates an embed according to discord.py (now defunct) semantics.

        refer to https://cog-creators.github.io/discord-embed-sandbox/
        to create your own.
        """

        match self.office_stat:
            case Status.OPEN:
                description = f"""
Office is open 🥳!
Open since: **{self.open_since.strftime('%H:%M')}**
"""
                color = OFFICE_OPEN_COLOR
                logo_link = CODEY_HAPPY

            case Status.CLOSED:
                description = f"""
Office has closed 😭!
Closed since: **{self.open_since.strftime('%H:%M')}**
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

        return embed


# time values are arbitrary

def test_open():
    status = {"status": 1, "time": 13123123412}
    main_func(status)


def test_closed():
    status = {"status": 0, "time": 3123123412}
    main_func(status)


def test_broke():
    """Sends two embeds out."""
    status = None
    main_func(status)

    status = {"status": -1, "time": 3123123412}
    main_func(status)


if __name__ == "__main__":
    url = "https://discord.com/api/webhooks/941854767280439387/Ru0ClUiqJ8DhaA7lcnds4zl8QFuTx-j1aksKEdPXCNTbzeAsermQkcqSYrl3fvk-oFtD"

    webhook_obj = Webhook(url)
    scheduler = BlockingScheduler()
    office_status = OfficeStatus()

    # terrible tests but yolo

    # test_open()
    # test_closed()
    # test_broke()

    run(scheduler)
