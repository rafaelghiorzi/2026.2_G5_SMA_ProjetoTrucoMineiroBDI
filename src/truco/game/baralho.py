"""Baralho: montar, embaralhar e distribuir (Especificação 2.1 e 3)."""


class Baralho:
    def montar(self):
        raise NotImplementedError

    def embaralhar(self):
        raise NotImplementedError

    def distribuir(self, jogadores):
        raise NotImplementedError
