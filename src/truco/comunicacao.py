"""Mensagens FIPA-ACL do jogo (Especificação, Seção 6)."""

from enum import StrEnum

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


class Categoria(StrEnum):
    """Categoria anunciada da mão (Como os Agentes Decidem 3.2)."""

    FRACA = "fraca"
    MEDIA = "media"
    FORTE = "forte"


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


def criar_mensagem(remetente, destinatario, performativa, conteudo):
    raise NotImplementedError


def ler_mensagem(msg):
    """Transforma a mensagem ACL em (Evento, dados)."""
    raise NotImplementedError
