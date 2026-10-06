"""Jogador BDI de Truco Mineiro.

Ciclo por evento (Seção 4.3 da especificação): o agente só delibera quando algo
relevante acontece. Cada mensagem recebida passa por

    perceber (revisar crenças) -> deliberar (se o evento pede decisão) -> agir

As decisões em si (chance de vencer, barras, escolha de carta, conversa) ficam
nos módulos de ``truco.bdi``; aqui só há a ligação com o SPADE.
"""

import logging
from typing import Any

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.template import Template

from truco.bdi.beliefs import Crencas
from truco.bdi.intentions import AcaoConversa, Resposta
from truco.bdi.personalidades import Personalidade
from truco.core.carta import Carta
from truco.protocol import mensagens
from truco.protocol.performatives import (
    ONTOLOGIA,
    Categoria,
    Comando,
    Evento,
    Performativa,
)

logger = logging.getLogger(__name__)


class PlayerAgent(Agent):
    def __init__(
        self,
        jid: str,
        password: str,
        time: str,
        personalidade: Personalidade,
        mesa: str,
        parceiro: str,
        adversarios: tuple[str, str],
    ):
        super().__init__(jid, password)
        self.time = time
        self.personalidade = personalidade
        self.mesa = mesa
        self.parceiro = parceiro
        self.adversarios = adversarios
        self.crencas = Crencas(eu=jid, parceiro=parceiro, adversarios=adversarios)
        self.acao_conversa: AcaoConversa = AcaoConversa.NADA  # escolhida na janela atual

    async def setup(self) -> None:
        logger.info("%s (%s) pronto, time %s", self.jid, self.personalidade.nome, self.time)

        da_mesa = Template(sender=self.mesa, metadata={"ontology": ONTOLOGIA})
        self.add_behaviour(self.CicloBDI(), da_mesa)

        sinais = Template(metadata={"ontology": ONTOLOGIA, "tipo": Comando.SINAL})
        self.add_behaviour(self.OuvirConversa(), sinais)

    # ------------------------------------------------------------------ #
    # Revisão de crenças (placeholders)                                  #
    # ------------------------------------------------------------------ #

    def perceber(self, tipo: str, conteudo: dict[str, Any]) -> None:
        """Atualiza as crenças a partir de um aviso da mesa."""
        match tipo:
            case Evento.INICIO_MAO:
                cartas = [mensagens.carta_de_dict(c) for c in conteudo.get("cartas", [])]
                self.crencas.nova_mao(cartas)
            case Evento.CARTA_JOGADA:
                pass  # TODO: registrar carta em cartas_jogadas / mesa_rodada
            case Evento.PEDIDO_APOSTA:
                pass  # TODO: pedido conta como anúncio "média" de quem pediu
            case Evento.DECLARACAO:
                pass  # TODO: registrar anúncio público
            case Evento.RESPOSTA_PEDIDO:
                pass  # TODO: atualizar valor da aposta e histórico de fuga
            case Evento.FIM_RODADA:
                pass  # TODO: registrar vencedor da rodada, limpar mesa_rodada
            case Evento.FIM_MAO:
                pass  # TODO: atualizar placar

    def ouvir_sinal(self, remetente: str, categoria: Categoria, espionado: bool) -> None:
        """Registra um sinal do parceiro ou um sinal interceptado do adversário."""
        # TODO: confiança x0,7 se não escolheu RECEBER; regras do Grinder
        pass

    # ------------------------------------------------------------------ #
    # Deliberação (placeholders)                                         #
    # ------------------------------------------------------------------ #

    def chance_de_vencer(self, com_bonus_fuga: bool = False) -> float:
        """Chance de vencer a mão (Seção 3.4 de "Como os Agentes Decidem")."""
        # TODO: forca_time, ameaca, vantagem, saldo de rodadas, bônus de fuga
        return 0.5

    def deve_pedir(self, pode_pedir: bool) -> bool:
        """Na minha vez: pedir truco (ou aumentar) antes de jogar?"""
        # TODO: chance(com bônus) > barra_aumentar
        return False

    def decidir_resposta(self, pode_aumentar: bool) -> Resposta:
        """Recebi um pedido: correr, aceitar ou aumentar."""
        # TODO: chance(sem bônus) < barra_correr -> correr; > barra_aumentar -> aumentar
        return Resposta.ACEITAR

    def escolher_carta(self) -> Carta:
        """Qual carta jogar (Seção 3.6)."""
        # TODO: regra de resposta igual para todos; abertura por personalidade
        return min(self.crencas.minhas_cartas, key=lambda c: c.rho())

    def categoria_da_mao(self) -> Categoria:
        """Categoria verdadeira da mão (para sinal e declaração)."""
        # TODO: força < 0,35 fraca; < 0,60 média; senão forte
        return Categoria.MEDIA

    def escolher_acao_conversa(self) -> AcaoConversa:
        """Sorteia a ação da janela de conversa com a tabela da personalidade."""
        # TODO: regras de bom senso + sorteio ponderado
        return AcaoConversa.NADA

    # ------------------------------------------------------------------ #
    # Behaviours                                                         #
    # ------------------------------------------------------------------ #

    class CicloBDI(CyclicBehaviour):
        """Recebe avisos da mesa, revisa crenças e age quando o evento pede decisão."""

        async def run(self) -> None:
            msg = await self.receive(timeout=10)
            if msg is None:
                return
            _, tipo, conteudo = mensagens.ler(msg)
            self.agent.perceber(tipo, conteudo)

            match tipo:
                case Evento.SUA_VEZ:
                    await self.minha_vez(conteudo)
                case Evento.RESPONDER_PEDIDO:
                    await self.responder_pedido(conteudo)
                case Evento.PEDIR_DECLARACAO:
                    await self.declarar()
                case Evento.JANELA_CONVERSA:
                    await self.conversar()
                case Evento.FIM_PARTIDA:
                    await self.agent.stop()

        async def para_mesa(
            self, performativa: Performativa, tipo: Comando, conteudo: dict | None = None
        ) -> None:
            ag = self.agent
            await self.send(mensagens.criar(str(ag.jid), ag.mesa, performativa, tipo, conteudo))

        async def minha_vez(self, conteudo: dict[str, Any]) -> None:
            if self.agent.deve_pedir(conteudo.get("pode_pedir", False)):
                await self.para_mesa(Performativa.PROPOSE, Comando.PEDIR)
                return  # a mesa manda SUA_VEZ de novo depois da resposta (regra 8)
            carta = self.agent.escolher_carta()
            await self.para_mesa(
                Performativa.INFORM, Comando.JOGAR_CARTA, mensagens.carta_para_dict(carta)
            )

        async def responder_pedido(self, conteudo: dict[str, Any]) -> None:
            resposta = self.agent.decidir_resposta(conteudo.get("pode_aumentar", False))
            performativa = {
                Resposta.ACEITAR: Performativa.ACCEPT_PROPOSAL,
                Resposta.CORRER: Performativa.REJECT_PROPOSAL,
                Resposta.AUMENTAR: Performativa.PROPOSE,
            }[resposta]
            await self.para_mesa(performativa, Comando.RESPOSTA)

        async def declarar(self) -> None:
            categoria = self.agent.categoria_da_mao()
            await self.para_mesa(Performativa.INFORM, Comando.DECLARACAO, {"categoria": categoria})

        async def conversar(self) -> None:
            ag = self.agent
            ag.acao_conversa = ag.escolher_acao_conversa()
            match ag.acao_conversa:
                case AcaoConversa.ENVIAR:
                    msg = mensagens.criar(
                        str(ag.jid), ag.parceiro, Performativa.INFORM, Comando.SINAL,
                        {"categoria": ag.categoria_da_mao()},
                    )
                    await self.send(msg)
                    ag.crencas.ja_enviei_sinal = True
                case AcaoConversa.BLEFAR:
                    pass  # TODO: blefe-fantasma "forte" (depende do mecanismo de espionagem)
                case AcaoConversa.ESPIONAR:
                    pass  # TODO: tentar interceptar (depende do mecanismo de espionagem)

    class OuvirConversa(CyclicBehaviour):
        """Recebe sinais ponto a ponto (parceiro ou interceptados)."""

        async def run(self) -> None:
            msg = await self.receive(timeout=10)
            if msg is None:
                return
            _, _, conteudo = mensagens.ler(msg)
            remetente = str(msg.sender.bare())
            espionado = remetente != self.agent.parceiro
            self.agent.ouvir_sinal(remetente, Categoria(conteudo["categoria"]), espionado)
