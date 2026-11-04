from enum import StrEnum


class PaymentMethod(StrEnum):
    BOLETO = "boleto"
    PIX = "pix"
    DEBIT = "debit"
    CREDIT_3X = "credit_3x"
    CREDIT_6X = "credit_6x"
    CREDIT_12X = "credit_12x"
