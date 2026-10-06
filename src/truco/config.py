"""Configuração global do projeto: XMPP e constantes do jogo."""

# --- XMPP -------------------------------------------------------------------
# Servidor embutido do SPADE (spade.run(..., embedded_xmpp_server=True)).
XMPP_DOMAIN = "localhost"
AGENT_PASSWORD = "truco"


def jid(nome: str) -> str:
    """Monta o JID de um agente no domínio local."""
    return f"{nome}@{XMPP_DOMAIN}"


MESA_JID = jid("mesa")
JOGADORES_JID = [jid(f"j{i}") for i in range(1, 5)]  # J1..J4, na ordem dos assentos

# --- Jogo ---------------------------------------------------------------------
PONTOS_PARTIDA = 12
CARTAS_POR_JOGADOR = 3
TIMES = {"A": (0, 2), "B": (1, 3)}  # índices de assento: J1/J3 e J2/J4
