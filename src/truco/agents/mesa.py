"""Mesa: árbitro e ambiente (Especificação, Seção 3). Reativa, máquina de estados.

As regras moram em truco.jogo; a mesa só guarda o quadro, conversa com os
jogadores e chama as regras na hora certa.

Fluxo sem truco (passos 1 a 3):

    INICIO_PONTO -> VEZ -> (4 cartas?) -> FIM_RODADA -> (ponto acabou?) -> FIM_PONTO
                     ^                        |                                |
                     +------- não ------------+          (alguém fez 12?) não -+-> INICIO_PONTO
                                                                       sim -> FIM_PARTIDA
"""

import random

from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message

from truco.comunicacao import Evento, criar_mensagem, ler_mensagem, template_do_jogo
from truco.jogo import Aposta, Baralho, Carta, CartasNaMesa, Mao, Ponto, TIME

INICIO_PONTO = "INICIO_PONTO"
VEZ = "VEZ"
FIM_RODADA = "FIM_RODADA"
FIM_PONTO = "FIM_PONTO"
FIM_PARTIDA = "FIM_PARTIDA"

PONTOS_PARA_VENCER = 12
TEMPO_DE_JOGADA = 30  # segundos esperando uma jogada antes de pedir de novo


class EstadoMesa(State):
    """Base dos estados: só dá ao editor o tipo certo de self.agent."""

    agent: "MesaAgent"

    async def avisar_todos(self, conteudo: dict) -> None:
        """Manda o mesmo aviso aos 4 jogadores."""
        for jogador in self.agent.jogadores:
            await self.send(criar_mensagem(jogador, "inform", conteudo))


class InicioPonto(EstadoMesa):
    """Começa um ponto: cartas novas, aposta valendo 1, e cada jogador recebe a sua mão."""

    async def run(self) -> None:
        mesa = self.agent  # o quadro: tudo que os estados leem e escrevem mora no agente

        # 1. Baralho novo a cada ponto: as 29 cartas voltam e são embaralhadas.
        baralho = Baralho(mesa.rng)
        baralho.embaralhar()
        mesa.maos = baralho.distribuir(mesa.jogadores)

        # 2. Ponto e Aposta novos: nenhuma rodada jogada, ponto valendo 1.
        mesa.ponto = Ponto(mesa.jogadores)
        mesa.aposta = Aposta(mesa.jogadores)
        mesa.cartas_na_mesa = []

        # 3. Cada jogador recebe SÓ as próprias cartas. É isso que garante a visão
        #    parcial (Especificação 3): a mão dos outros nunca chega até ele.
        for jogador, mao in mesa.maos.items():
            conteudo = {
                "evento": Evento.NOVO_PONTO,
                "cartas": [carta.valor for carta in mao],  # Carta não vira JSON; o valor sim
                "abridor": mesa.abridor,
                "placar": mesa.placar,
            }
            await self.send(criar_mensagem(jogador, "inform", conteudo))

        # 4. Quem abre a 1ª rodada deste ponto. A partir daqui, o estado Vez assume.
        mesa.vez = mesa.abridor
        self.set_next_state(VEZ)


class Vez(EstadoMesa):
    """Pede a jogada a quem está com a vez e espera a carta.

    Cada execução cuida de UMA carta. Se nada válido chegar, o estado aponta
    para ele mesmo (VEZ -> VEZ) e pede de novo ao mesmo jogador.
    Passo 4 (truco): aqui também pode chegar um PROPOSE em vez de uma carta.
    """

    async def run(self) -> None:
        mesa = self.agent

        # 1. Pedir a jogada a quem está com a vez.
        await self.send(criar_mensagem(mesa.vez, "request", {"evento": Evento.SUA_VEZ}))

        # 2. Esperar a resposta. Sem resposta a tempo, pede de novo.
        msg = await self.receive(timeout=TEMPO_DE_JOGADA)
        if msg is None:
            print(f"[mesa] {mesa.vez} não jogou a tempo, pedindo de novo")
            self.set_next_state(VEZ)
            return

        # 3. Validar. Jogada inválida é ignorada e a vez continua com o mesmo jogador.
        carta = self.carta_valida(msg)
        if carta is None:
            print(f"[mesa] jogada inválida de {msg.sender.bare}: {msg.body}")
            self.set_next_state(VEZ)
            return

        # 4. Aplicar no quadro e avisar os 4 (inclusive quem jogou: é a confirmação).
        mesa.maos[mesa.vez].remover(carta)
        mesa.cartas_na_mesa.append((mesa.vez, carta))
        await self.avisar_todos({
            "evento": Evento.CARTA_JOGADA,
            "jogador": mesa.vez,
            "carta": carta.valor,
        })

        # 5. Rodada completa vai para FIM_RODADA; senão, a vez passa adiante.
        if len(mesa.cartas_na_mesa) == len(mesa.jogadores):
            self.set_next_state(FIM_RODADA)
        else:
            mesa.vez = mesa.proximo(mesa.vez)
            self.set_next_state(VEZ)

    def carta_valida(self, msg: Message) -> Carta | None:
        """A carta jogada, se a jogada for válida (Especificação 3, item 2). Senão, None."""
        mesa = self.agent
        evento, dados = ler_mensagem(msg)
        if evento != Evento.CARTA_JOGADA:
            return None
        if str(msg.sender.bare) != mesa.vez:  # bare: sem o sufixo de conexão (/recurso)
            return None
        carta = Carta(dados.get("carta"))
        if carta not in mesa.maos[mesa.vez]:
            return None
        return carta


class FimRodada(EstadoMesa):
    async def run(self) -> None:
        # TODO:
        # 1. ponto.registrar_rodada(cartas_na_mesa) e avisar os 4 (FIM_RODADA)
        # 2. ponto.encerrada -> FIM_PONTO
        # 3. senão: vez = ponto.quem_comeca(...), limpar a mesa -> VEZ
        raise NotImplementedError


class FimPonto(EstadoMesa):
    async def run(self) -> None:
        # TODO:
        # 1. vencedor_ponto() leva aposta.valor pontos (None = ninguém pontua)
        # 2. avisar os 4 (FIM_PONTO) com o placar
        # 3. alguém >= PONTOS_PARA_VENCER -> FIM_PARTIDA
        # 4. senão: abridor anda um assento -> INICIO_PONTO
        raise NotImplementedError


class FimPartida(EstadoMesa):
    """Estado final: sem transição de saída, o FSM para aqui."""

    async def run(self) -> None:
        # TODO: avisar os 4 (FIM_PARTIDA) e parar a mesa
        raise NotImplementedError


class MesaAgent(Agent):
    def __init__(self, jid: str, password: str, jogadores: list[str], semente: int | None = None):
        super().__init__(jid, password)
        # O quadro (Especificação 3): tudo que a mesa sabe fica aqui, e os estados leem/escrevem
        self.jogadores = jogadores  # ordem dos assentos: A, B, A, B
        self.rng = random.Random(semente)
        self.placar: dict[TIME, int] = {"A": 0, "B": 0}
        self.abridor = jogadores[0]  # J1 abre o primeiro ponto
        self.vez = self.abridor
        self.maos: dict[str, Mao] = {}
        self.cartas_na_mesa: CartasNaMesa = []
        self.ponto = Ponto(jogadores)
        self.aposta = Aposta(jogadores)

    def proximo(self, jogador: str) -> str:
        """Próximo assento na ordem de jogo."""
        i = self.jogadores.index(jogador)
        return self.jogadores[(i + 1) % len(self.jogadores)]

    async def setup(self) -> None:
        fluxo = FSMBehaviour()
        fluxo.add_state(INICIO_PONTO, InicioPonto(), initial=True)
        fluxo.add_state(VEZ, Vez())
        fluxo.add_state(FIM_RODADA, FimRodada())
        fluxo.add_state(FIM_PONTO, FimPonto())
        fluxo.add_state(FIM_PARTIDA, FimPartida())

        fluxo.add_transition(INICIO_PONTO, VEZ)
        fluxo.add_transition(VEZ, VEZ)
        fluxo.add_transition(VEZ, FIM_RODADA)
        fluxo.add_transition(FIM_RODADA, VEZ)
        fluxo.add_transition(FIM_RODADA, FIM_PONTO)
        fluxo.add_transition(FIM_PONTO, INICIO_PONTO)
        fluxo.add_transition(FIM_PONTO, FIM_PARTIDA)

        self.add_behaviour(fluxo, template_do_jogo())
