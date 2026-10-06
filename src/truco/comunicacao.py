"""Mensagens FIPA-ACL do jogo (Especificação, Seção 6)."""

ONTOLOGIA = "truco-mineiro"


def criar_mensagem(remetente, destinatario, performativa, conteudo):
    raise NotImplementedError


def ler_mensagem(msg):
    raise NotImplementedError
