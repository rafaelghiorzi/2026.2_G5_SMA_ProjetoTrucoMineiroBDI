"""Mensagens FIPA-ACL do jogo (Especificação, Seção 6)."""

import json
from enum import StrEnum

from spade.message import Message
from spade.template import Template

ONTOLOGIA = "truco-mineiro"


class Evento(StrEnum):
    """O que a mesa avisa aos jogadores. Os que pedem resposta estão marcados."""

    NOVO_PONTO = "novo-ponto"
    SUA_VEZ = "sua-vez"  # pede: pedir? + carta
    CARTA_JOGADA = "carta-jogada"
    PEDIDO = "pedido"  # pede resposta, se for para mim
    PEDE_DECLARACAO = "pede-declaracao"  # pede: categoria da mão
    DECLARACAO = "declaracao"
    RESPOSTA = "resposta"  # alguém correu, aceitou ou aumentou
    JANELA_CONVERSA = "janela-conversa"  # pede: ação de conversa
    FIM_RODADA = "fim-rodada"
    FIM_PONTO = "fim-ponto"
    FIM_PARTIDA = "fim-partida"


class Resposta(StrEnum):
    CORRER = "correr"
    ACEITAR = "aceitar"
    AUMENTAR = "aumentar"


class AcaoConversa(StrEnum):
    ENVIAR = "enviar"
    RECEBER = "receber"
    ESPIONAR = "espionar"
    BLEFAR = "blefar"
    NADA = "nada"


def criar_mensagem(destinatario: str, performativa: str, conteudo: dict) -> Message:
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
            "performative": performativa,
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
