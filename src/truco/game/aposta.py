"""Estado da aposta: truco, seis, nove, doze (Especificação 2.4)."""


class Aposta:
    def pode_pedir(self, jogador) -> bool:
        raise NotImplementedError

    def quem_responde(self, jogador_que_pediu):
        raise NotImplementedError

    def pedir(self, jogador):
        raise NotImplementedError

    def aceitar(self):
        raise NotImplementedError

    def correr(self):
        raise NotImplementedError

    def valor_atual(self) -> int:
        raise NotImplementedError
