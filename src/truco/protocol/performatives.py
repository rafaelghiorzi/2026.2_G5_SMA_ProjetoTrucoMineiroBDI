"""Vocabulário do protocolo: performativas FIPA-ACL e tipos de mensagem do jogo.

Toda mensagem carrega a ontologia ``ONTOLOGIA`` e um metadado ``tipo`` (um
``Evento`` ou ``Comando``), o que permite rotear mensagens com Templates do SPADE.
"""

from enum import StrEnum

ONTOLOGIA = "truco-mineiro"


class Performativa(StrEnum):
    """Atos de fala FIPA-ACL usados no jogo (Seção 6.1 da especificação)."""

    INFORM = "inform"
    PROPOSE = "propose"
    ACCEPT_PROPOSAL = "accept-proposal"
    REJECT_PROPOSAL = "reject-proposal"
    FAILURE = "failure"  # mesa rejeita um comando inválido


class Evento(StrEnum):
    """Avisos da mesa para os jogadores (INFORM)."""

    INICIO_MAO = "inicio_mao"  # cartas do jogador, quem abre, placar
    SUA_VEZ = "sua_vez"  # jogador deve jogar (e pode pedir)
    CARTA_JOGADA = "carta_jogada"
    PEDIDO_APOSTA = "pedido_aposta"  # alguém pediu truco/aumentou (público)
    PEDIR_DECLARACAO = "pedir_declaracao"  # mesa pede a declaração pública
    DECLARACAO = "declaracao"  # declaração de alguém (pública)
    RESPONDER_PEDIDO = "responder_pedido"  # jogador deve aceitar/correr/aumentar
    RESPOSTA_PEDIDO = "resposta_pedido"  # resposta de alguém (pública)
    JANELA_CONVERSA = "janela_conversa"  # abre a janela de conversa da rodada
    FIM_RODADA = "fim_rodada"
    FIM_MAO = "fim_mao"
    FIM_PARTIDA = "fim_partida"


class Comando(StrEnum):
    """Mensagens enviadas pelos jogadores."""

    JOGAR_CARTA = "jogar_carta"  # INFORM -> mesa
    PEDIR = "pedir"  # PROPOSE -> mesa
    RESPOSTA = "resposta"  # ACCEPT/REJECT/PROPOSE (aumentar) -> mesa
    DECLARACAO = "declaracao"  # INFORM -> mesa
    SINAL = "sinal"  # INFORM -> parceiro (ou ninguém, no blefe)


class Categoria(StrEnum):
    """Categoria de mão anunciada em sinais e declarações."""

    FRACA = "fraca"
    MEDIA = "media"
    FORTE = "forte"
