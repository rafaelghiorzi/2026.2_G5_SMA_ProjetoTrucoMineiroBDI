"""Estados da máquina de estados da mesa."""

from spade.behaviour import FSMBehaviour, State


class FluxoMesa(FSMBehaviour):
    pass


class InicioMao(State):
    """Embaralha e distribui 3 cartas por jogador."""

    async def run(self) -> None:
        raise NotImplementedError


class VezDoJogador(State):
    """Espera o comando de quem tem a vez (jogar carta ou pedir)."""

    async def run(self) -> None:
        raise NotImplementedError


class NegociacaoAposta(State):
    """Declarações públicas e resposta ao pedido."""

    async def run(self) -> None:
        raise NotImplementedError


class FimRodada(State):
    async def run(self) -> None:
        raise NotImplementedError


class FimMao(State):
    async def run(self) -> None:
        raise NotImplementedError


class FimPartida(State):
    async def run(self) -> None:
        raise NotImplementedError
