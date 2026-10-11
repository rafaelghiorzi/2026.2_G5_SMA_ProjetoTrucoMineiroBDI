"""Configuração do projeto."""
from typing import Literal

# Servidor XMPP embutido do SPADE
XMPP_DOMAIN = "localhost"
AGENT_PASSWORD = "truco"

POSICAO_MANILHA = 8  # 7O, AE, 7C e 4P
TIME = Literal["A", "B"]
NIVEIS_APOSTA = [1, 3, 6, 9, 12]
CARTAS = Literal["Q", "J", "K", "A", "2", "3", "CR", "7O", "AE", "7C", "4P"]

# Faixas de força da mão
LIMITE_FRACA = 0.35
LIMITE_FORTE = 0.60

POSICOES: dict[str, int] = {
    "Q" : 1,
    "J" : 2,
    "K" : 3,
    "A" : 4,
    "2" : 5,
    "3" : 6,
    "CR" : 7,    # Curinga
    "7O" : 8,    # 7 de Ouros
    "AE" : 9,    # A de Espadas
    "7C" : 10,   # 7 de Copas
    "4P" : 11    # 4 de Paus (Zap!)
}

QUANTIDADES: dict[CARTAS, int] = {
    "Q" : 4,
    "J" : 4,
    "K" : 4,
    "A" : 3,
    "2" : 4,
    "3" : 4,
    "CR" : 2,    # Curinga
    "7O" : 1,    # 7 de Ouros
    "AE" : 1,    # A de Espadas
    "7C" : 1,   # 7 de Copas
    "4P" : 1    # 4 de Paus (Zap!)
}