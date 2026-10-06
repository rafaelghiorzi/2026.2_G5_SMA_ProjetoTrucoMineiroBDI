"""Construção e leitura de mensagens FIPA-ACL do jogo."""

from typing import Any

from spade.fipa_message import FIPAMessageBuilder, FIPAMessageParser
from spade.message import Message

from truco.core.carta import Carta
from truco.protocol.performatives import ONTOLOGIA, Comando, Evento, Performativa


def criar(
    remetente: str,
    destinatario: str,
    performativa: Performativa,
    tipo: Evento | Comando,
    conteudo: dict[str, Any] | None = None,
) -> Message:
    """Monta uma mensagem FIPA-ACL com corpo JSON e o metadado ``tipo``."""
    builder = (
        FIPAMessageBuilder(sender=remetente, receiver=destinatario)
        .set_performative(performativa)
        .set_ontology(ONTOLOGIA)
        .set_custom_metadata("tipo", tipo)
        .set_body(conteudo or {})
    )
    msg = builder.build()
    # SPADE 4.1.4: build() faz ``msg.metadata = ...``, mas Message guarda os
    # metadados em ``_metadata``; sem esta cópia eles não são enviados.
    for chave, valor in builder.metadata.items():
        if valor is not None:
            msg.set_metadata(chave, str(valor))
    return msg


def ler(msg: Message) -> tuple[str, str, dict[str, Any]]:
    """Retorna ``(performativa, tipo, conteudo)`` de uma mensagem recebida."""
    parser = FIPAMessageParser(msg)
    conteudo = parser.parse_body()
    if not isinstance(conteudo, dict):
        conteudo = {}
    return parser.get_performative(), msg.get_metadata("tipo"), conteudo


def carta_para_dict(carta: Carta) -> dict[str, str | None]:
    return {"valor": carta.valor, "naipe": carta.naipe}


def carta_de_dict(dados: dict[str, str | None]) -> Carta:
    return Carta(dados["valor"], dados.get("naipe"))
