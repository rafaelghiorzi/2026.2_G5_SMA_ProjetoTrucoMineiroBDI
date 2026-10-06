"""Botões de cada personalidade (Seção 4 de "Como os Agentes Decidem")."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Personalidade:
    nome: str

    # Crença
    vies_adversarios: float = 0.0
    vies_adversarios_por_vantagem: float = 0.0  # Loose Cannon: -0,20 x vantagem
    vies_parceiro: float = 0.0
    confianca: float = 0.7
    # Grinder: com adversários só acredita em ameaça ("forte" ou pedido de truco).
    # None = usa ``confianca`` para todos os anúncios.
    confianca_ameaca_adversario: float | None = None
    confianca_outros_adversario: float | None = None

    # Chance de vencer
    peso_placar: float = 0.0  # p
    bonus_fuga: bool = False  # Maverick

    # Aposta
    cautela: float = 0.0
    base_aumentar: float = 0.68

    # Abertura da rodada: pesos (forte, média, fraca). None = regra do Rational Shark.
    abertura_3_cartas: tuple[float, float, float] | None = None
    abertura_2_cartas: tuple[float, float] | None = None  # (forte, fraca)

    # Conversa: pesos de cada ação e sucesso ao espionar
    conversa: dict[str, float] = field(default_factory=dict)
    sucesso_espionar: float = 0.5


RATIONAL_SHARK = Personalidade(
    nome="Rational Shark",
    confianca=0.70,
    base_aumentar=0.68,
    conversa={"enviar": 30, "receber": 30, "espionar": 20, "blefar": 5, "nada": 15},
    sucesso_espionar=0.50,
)

MAVERICK_BLUFFER = Personalidade(
    nome="Maverick Bluffer",
    confianca=0.40,
    bonus_fuga=True,
    base_aumentar=0.62,
    abertura_3_cartas=(70, 20, 10),
    abertura_2_cartas=(85, 15),
    conversa={"enviar": 20, "receber": 10, "espionar": 25, "blefar": 35, "nada": 10},
    sucesso_espionar=0.70,
)

LOOSE_CANNON = Personalidade(
    nome="Loose Cannon",
    vies_adversarios_por_vantagem=-0.20,
    confianca=0.85,
    peso_placar=0.4,
    cautela=-0.05,
    base_aumentar=0.58,
    abertura_3_cartas=(33, 34, 33),
    abertura_2_cartas=(50, 50),
    conversa={"enviar": 30, "receber": 20, "espionar": 25, "blefar": 15, "nada": 10},
    sucesso_espionar=0.45,
)

GRINDER = Personalidade(
    nome="Grinder",
    vies_adversarios=0.15,
    vies_parceiro=-0.10,
    confianca=0.80,
    confianca_ameaca_adversario=0.65,
    confianca_outros_adversario=0.0,
    cautela=0.10,
    base_aumentar=0.75,
    abertura_3_cartas=(10, 25, 65),
    abertura_2_cartas=(15, 85),
    conversa={"enviar": 20, "receber": 40, "espionar": 10, "blefar": 5, "nada": 25},
    sucesso_espionar=0.25,
)

PERSONALIDADES = {
    p.nome: p for p in (RATIONAL_SHARK, MAVERICK_BLUFFER, LOOSE_CANNON, GRINDER)
}
