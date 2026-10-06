"""Intenções: o resultado de cada deliberação (Seção 4.3 da especificação)."""

from enum import StrEnum


class Resposta(StrEnum):
    CORRER = "correr"
    ACEITAR = "aceitar"
    AUMENTAR = "aumentar"


class AcaoConversa(StrEnum):
    ENVIAR = "enviar"
    RECEBER = "receber"
    ESPIONAR = "espionar"
    BLEFAR = "blefar"
    NADA = "nada"
