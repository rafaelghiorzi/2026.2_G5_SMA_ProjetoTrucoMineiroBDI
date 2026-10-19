"""FIPA-ACL messages of the game (Specification, Section 6).

The vocabulary (events, performatives, ontology) lives in truco.config.
"""

import json

from slixmpp import JID
from spade.message import Message
from spade.template import Template

from truco.config import ONTOLOGY, Event, Performative


def create_message(recipient: JID, performative: Performative, content: dict) -> Message:
    """Builds the SPADE Message. SPADE fills in the sender on its own when sending.

    `content` is a dictionary with the "event" key plus the data. The event goes in
    the metadata (so Templates can filter by it); the rest travels as JSON in the
    body, which in SPADE only accepts text. JID values travel as text and whoever reads
    them turns them back with JID(...). JSON keys must already be text: use str(jid)
    when a JID is a dictionary key.
    """
    data = dict(content)  # copy: do not touch the caller's dictionary
    event = Event(data.pop("event"))
    return Message(
        to=recipient,
        body=json.dumps(data, default=str),
        metadata={
            "performative": performative.value,
            "ontology": ONTOLOGY,
            "event": event.value,
        },
    )


def read_message(msg: Message) -> tuple[Event, dict]:
    """Turns the ACL message into (Event, data). The inverse of create_message."""
    event = Event(msg.get_metadata("event"))
    data = json.loads(msg.body) if msg.body else {}
    return event, data


def sender_of(msg: Message) -> JID:
    """Who sent the message, without the connection suffix (/resource)."""
    return JID(msg.sender.bare)


def game_template() -> Template:
    """Only lets truco messages through, so behaviours don't pick up unrelated messages."""
    return Template(metadata={"ontology": ONTOLOGY})
