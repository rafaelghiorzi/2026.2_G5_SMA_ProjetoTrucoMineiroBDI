import random
from core.carta import Carta, NAIPES, VALORES_NORMAIS, CURINGA


def novo_baralho() -> list[Carta]:
    cartas = []

    for valor in VALORES_NORMAIS:
        for naipe in NAIPES:
            cartas.append(Carta(valor, naipe))

    cartas.append(Carta(CURINGA, None))
    cartas.append(Carta("7", "ouros"))
    cartas.append(Carta("7", "copas"))
    cartas.append(Carta("4", "paus"))


def embaralhar(baralho: list[Carta], seed: int | None = None) -> list[Carta]:
    rng = random.Random(seed)
    baralho = list(baralho)
    rng.shuffle(baralho)
    return baralho


def distribuir(baralho: list[Carta], jogadores: list[str], cartas_por_jogador: int = 3):
    maos = {}
    for j in jogadores:
        maos[j] = []
    idx = 0
    for _ in range(cartas_por_jogador):
        for j in jogadores:
            maos[j].append(baralho[idx])
            idx += 1

    return maos, baralho[idx:]
