"""Comportamento base de TODOS os jogadores (BDI e de controle).

Aqui fica só o protocolo com a mesa: receber avisos, perceber, e quando a mesa
pede uma ação, perguntar à subclasse o que fazer e responder. As decisões em si
são abstratas: JogadorBDI as implementa com a receita da personalidade, Medroso
e Maluco com regras fixas.
"""

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour

from truco.comunicacao import AcaoConversa, Evento, Resposta
from truco.jogo import Carta, Categoria, Mao


class OuvirMesa(CyclicBehaviour):
    """Laço perceber -> (se for a minha vez de agir) decidir -> agir.

    Implementa a "reconsideração por evento" (Especificação 4.3): o agente só
    delibera quando chega uma mensagem que pede ação.
    """

    agent: "Jogador"

    async def run(self) -> None:
        # TODO:
        # 1. msg = await self.receive(timeout=...)
        # 2. evento, dados = ler_mensagem(msg)
        # 3. self.agent.perceber(evento, dados)   (todo aviso atualiza o estado)
        # 4. se o evento pede ação, despachar para o método certo:
        #      SUA_VEZ          -> await self.agir_na_vez()
        #      PEDIDO (p/ mim)  -> responder_pedido
        #      PEDE_DECLARACAO  -> declarar
        #      JANELA_CONVERSA  -> conversar
        #      FIM_PARTIDA      -> self.kill()
        raise NotImplementedError

    async def agir_na_vez(self) -> None:
        """Pedir antes de jogar (se quiser) e depois jogar a carta.

        Se pedir, a jogada só acontece depois que a mesa avisar que o pedido
        foi aceito (Especificação 2.4, regra 8) — ou seja, este método talvez
        precise esperar a resposta ou ser dividido em dois eventos.
        """
        raise NotImplementedError


class Jogador(Agent):
    """Base comum. Sabe quem é a mesa, o parceiro e os adversários."""

    def __init__(self, jid: str, password: str, mesa: str, parceiro: str, adversarios: list[str]):
        super().__init__(jid, password)
        self.mesa = mesa
        self.parceiro = parceiro
        self.adversarios = adversarios
        self.mao = Mao()

    async def setup(self) -> None:
        # TODO: add_behaviour(OuvirMesa(), template) filtrando pela ONTOLOGIA.
        # A conversa entre parceiros não passa pela mesa: decidir se vira
        # outro behaviour ou se entra no mesmo despacho.
        raise NotImplementedError

    # --- Percepção. Padrão: só mantém a própria mão. BDI sobrescreve. ---

    def perceber(self, evento: Evento, dados) -> None:
        raise NotImplementedError

    # --- Decisões (Especificação 4.4). Cada tipo de jogador implementa. ---

    def deve_pedir(self) -> bool:
        raise NotImplementedError

    def responder_pedido(self, valor_pedido: int) -> Resposta:
        raise NotImplementedError

    def escolher_carta(self) -> Carta:
        raise NotImplementedError

    def declarar(self) -> Categoria | None:
        """None = não participa (jogadores de controle)."""
        return None

    def conversar(self) -> AcaoConversa:
        return AcaoConversa.NADA
