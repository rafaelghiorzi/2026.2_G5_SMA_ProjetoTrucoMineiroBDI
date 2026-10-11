"""Mensagens FIPA-ACL do jogo (Especificação, Seção 6).

O vocabulário (eventos, performativas, ontologia) fica em truco.config.
"""

import json

from spade.message import Message
from spade.template import Template

from truco.config import ONTOLOGIA, Evento, Performativa


def criar_mensagem(destinatario: str, performativa: Performativa, conteudo: dict) -> Message:
    """Monta a Message do SPADE. O remetente o SPADE preenche sozinho no envio.

    `conteudo` é um dicionário com a chave "evento" e os dados. O evento vai nos
    metadados (para Templates poderem filtrar por ele); o resto viaja como JSON
    no corpo, que no SPADE só aceita texto.
    """
    dados = dict(conteudo)  # cópia: não mexer no dicionário de quem chamou
    evento = Evento(dados.pop("evento"))
    return Message(
        to=destinatario,
        body=json.dumps(dados),
        metadata={
            "performative": performativa.value,
            "ontology": ONTOLOGIA,
            "evento": evento.value,
        },
    )


def ler_mensagem(msg: Message) -> tuple[Evento, dict]:
    """Transforma a mensagem ACL em (Evento, dados). O inverso de criar_mensagem."""
    evento = Evento(msg.get_metadata("evento"))
    dados = json.loads(msg.body) if msg.body else {}
    return evento, dados


def template_do_jogo() -> Template:
    """Só deixa passar mensagens do truco, para behaviours não pegarem mensagens alheias."""
    return Template(metadata={"ontology": ONTOLOGIA})
