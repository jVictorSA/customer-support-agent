from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from zoneinfo import ZoneInfo


class ReturnReason(StrEnum):
    WITHDRAWAL = "withdrawal"
    DEFECT = "defect"
    PREFERENCE = "preference"


class StoreZone(StrEnum):
    METRO = "metro"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class StoreStatus:
    is_open: bool
    local_time: datetime
    today_open: time | None
    today_close: time | None
    next_opening: datetime | None
    is_holiday: bool


@dataclass(frozen=True, slots=True)
class StoreSchedule:
    """Weekly opening hours and holidays for the physical store."""

    timezone: str = "America/Sao_Paulo"
    holidays: frozenset[date] = field(default_factory=frozenset)
    weekday_open: time = time(9, 0)
    weekday_close: time = time(18, 0)
    saturday_open: time = time(9, 0)
    saturday_close: time = time(13, 0)

    def status_at(self, now_utc: datetime) -> StoreStatus:
        local = now_utc.astimezone(ZoneInfo(self.timezone))
        today = local.date()
        is_holiday = today in self.holidays
        open_at, close_at = self._hours_for(today, is_holiday)
        is_open = (
            open_at is not None
            and close_at is not None
            and open_at <= local.time() < close_at
        )
        next_opening = None
        if not is_open:
            next_opening = self._next_opening(local)
        return StoreStatus(
            is_open=is_open,
            local_time=local,
            today_open=open_at,
            today_close=close_at,
            next_opening=next_opening,
            is_holiday=is_holiday,
        )

    def _hours_for(
        self, day: date, is_holiday: bool
    ) -> tuple[time | None, time | None]:
        if is_holiday:
            return None, None
        if day.weekday() == 6:
            return None, None
        if day.weekday() == 5:
            return self.saturday_open, self.saturday_close
        return self.weekday_open, self.weekday_close

    def _next_opening(self, local: datetime) -> datetime | None:
        for offset in range(1, 8):
            candidate_date = local.date() + timedelta(days=offset)
            if candidate_date in self.holidays:
                continue
            open_at, _ = self._hours_for(candidate_date, False)
            if open_at is not None:
                return datetime.combine(
                    candidate_date, open_at, tzinfo=local.tzinfo
                )
        return None


@dataclass(frozen=True, slots=True)
class PaymentOption:
    method: str
    label: str
    total_brl: Decimal
    installments: int
    installment_brl: Decimal | None
    discount_percent: int = 0
    available: bool = True
    note: str | None = None


@dataclass(frozen=True, slots=True)
class PaymentOptions:
    amount_brl: Decimal
    promotional: bool
    combined_allowed: bool
    options: tuple[PaymentOption, ...]


@dataclass(frozen=True, slots=True)
class ShippingQuote:
    cep: str
    zone: StoreZone
    subtotal_brl: Decimal
    shipping_brl: Decimal | None
    free_shipping: bool
    deadline: str | None
    requires_quote: bool
    modalities: tuple[dict[str, str], ...] = ()
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ReturnItemContext:
    product_id: int
    product_name: str | None
    is_final_sale: bool = False
    is_customized: bool = False
    is_hygiene_restricted: bool = False


@dataclass(frozen=True, slots=True)
class ReturnOrderContext:
    order_id: int
    status: str
    sales_channel: str | None
    order_date: date
    delivered_at: date | None
    items: tuple[ReturnItemContext, ...]


@dataclass(frozen=True, slots=True)
class ReturnEligibility:
    eligible: bool
    reason: str
    rule: str
    deadline: date | None
    days_remaining: int | None
    requirements: tuple[str, ...] = ()
    next_step: str = ""
    handoff_required: bool = False


_MONEY = Decimal("0.01")


def calculate_payment_options(
    amount_brl: Decimal, *, promotional: bool
) -> PaymentOptions:
    amount = _money(amount_brl)
    options: list[PaymentOption] = []

    pix_total = amount
    if not promotional:
        pix_total = _money(amount * Decimal("0.95"))
    options.append(
        PaymentOption(
            method="pix",
            label="PIX",
            total_brl=pix_total,
            installments=1,
            installment_brl=None,
            discount_percent=0 if promotional else 5,
            note=(
                "Desconto de 5% não aplicável sobre preço promocional."
                if promotional
                else None
            ),
        )
    )
    options.append(
        PaymentOption(
            method="debit",
            label="Cartão de débito",
            total_brl=amount,
            installments=1,
            installment_brl=None,
        )
    )
    options.append(
        PaymentOption(
            method="boleto",
            label="Boleto bancário",
            total_brl=amount,
            installments=1,
            installment_brl=None,
            note="Compensação em até 3 dias úteis.",
        )
    )

    for installments in range(1, 13):
        available, note = _credit_available(amount, installments)
        options.append(
            PaymentOption(
                method=f"credit_{installments}x",
                label=f"Cartão de crédito em {installments}x",
                total_brl=amount,
                installments=installments,
                installment_brl=(
                    _money(amount / Decimal(installments))
                    if installments > 1
                    else None
                ),
                available=available,
                note=note,
            )
        )

    return PaymentOptions(
        amount_brl=amount,
        promotional=promotional,
        combined_allowed=amount > Decimal("2000.00"),
        options=tuple(options),
    )


def _credit_available(
    amount: Decimal, installments: int
) -> tuple[bool, str | None]:
    if installments <= 3:
        if amount < Decimal("50.00") and installments > 1:
            return False, "Parcelamento não disponível para compras abaixo de R$ 50,00."
        return True, None
    if installments <= 6:
        if amount / Decimal(installments) < Decimal("80.00"):
            return False, "Parcela mínima de R$ 80,00."
        return True, None
    if amount / Decimal(installments) < Decimal("100.00"):
        return False, "Parcela mínima de R$ 100,00."
    return True, None


def estimate_shipping(
    *,
    cep: str,
    subtotal_brl: Decimal,
    metro_cep_prefixes: tuple[str, ...],
    has_large_items: bool = False,
) -> ShippingQuote:
    normalized = "".join(char for char in cep if char.isdigit())
    if len(normalized) != 8:
        raise ValueError("CEP must contain 8 digits")
    subtotal = _money(subtotal_brl)
    is_metro = any(normalized.startswith(prefix) for prefix in metro_cep_prefixes)
    zone = StoreZone.METRO if is_metro else StoreZone.OTHER

    if has_large_items:
        return ShippingQuote(
            cep=normalized,
            zone=zone,
            subtotal_brl=subtotal,
            shipping_brl=None,
            free_shipping=False,
            deadline=None,
            requires_quote=True,
            note=(
                "Instrumento de grande porte exige cotação individual de frete "
                "por peso e dimensões."
            ),
        )

    if zone is StoreZone.METRO:
        free = subtotal >= Decimal("500.00")
        shipping = (
            Decimal("0.00") if free else Decimal("35.00")
        )
        return ShippingQuote(
            cep=normalized,
            zone=zone,
            subtotal_brl=subtotal,
            shipping_brl=shipping,
            free_shipping=free,
            deadline="1 a 3 dias úteis",
            requires_quote=False,
            note="Entrega por motoboy; o cliente é contatado antes da entrega.",
        )

    return ShippingQuote(
        cep=normalized,
        zone=zone,
        subtotal_brl=subtotal,
        shipping_brl=None,
        free_shipping=False,
        deadline=None,
        requires_quote=True,
        modalities=(
            {"name": "PAC", "deadline": "5 a 12 dias úteis"},
            {"name": "SEDEX", "deadline": "2 a 5 dias úteis"},
            {"name": "Jadlog .package", "deadline": "3 a 8 dias úteis"},
        ),
        note=(
            "Frete calculado por CEP, peso e dimensões. Informe o CEP para "
            "cotação com as transportadoras."
        ),
    )


def evaluate_return(
    *,
    order: ReturnOrderContext,
    product_id: int,
    reason: ReturnReason,
    today: date,
    desired_product_in_stock: bool | None = None,
) -> ReturnEligibility:
    item = next(
        (candidate for candidate in order.items if candidate.product_id == product_id),
        None,
    )
    if item is None:
        return ReturnEligibility(
            eligible=False,
            reason="item_not_in_order",
            rule="O produto informado não pertence a este pedido.",
            deadline=None,
            days_remaining=None,
            next_step="Confirme o produto e o número do pedido.",
        )

    if order.status in {"cancelled", "pending"}:
        return ReturnEligibility(
            eligible=False,
            reason="order_not_eligible",
            rule="Pedido cancelado ou ainda não confirmado não entra em troca/devolução.",
            deadline=None,
            days_remaining=None,
            next_step="Fale com o atendimento para verificar o pedido.",
        )

    blocked = _return_block(item, reason)
    if blocked is not None:
        return blocked

    if reason is ReturnReason.WITHDRAWAL:
        return _withdrawal(order, today)
    if reason is ReturnReason.DEFECT:
        return _defect(order, today)
    return _preference(order, today, desired_product_in_stock)


def _return_block(
    item: ReturnItemContext, reason: ReturnReason
) -> ReturnEligibility | None:
    if reason is ReturnReason.DEFECT:
        return None
    if item.is_final_sale:
        return ReturnEligibility(
            eligible=False,
            reason="final_sale",
            rule="Produtos de liquidação com aviso de venda final não são elegíveis.",
            deadline=None,
            days_remaining=None,
            next_step="Fale com o atendimento para avaliar o caso.",
        )
    if item.is_customized:
        return ReturnEligibility(
            eligible=False,
            reason="customized_item",
            rule="Instrumentos personalizados ou com ajustes sob encomenda não são elegíveis.",
            deadline=None,
            days_remaining=None,
            next_step="Fale com o atendimento para avaliar o caso.",
        )
    if item.is_hygiene_restricted:
        return ReturnEligibility(
            eligible=False,
            reason="hygiene_restricted",
            rule="Boquilhas de sopro não são elegíveis por questões de higiene.",
            deadline=None,
            days_remaining=None,
            next_step="Fale com o atendimento para avaliar o caso.",
        )
    return None


def _withdrawal(order: ReturnOrderContext, today: date) -> ReturnEligibility:
    if order.sales_channel != "online":
        return ReturnEligibility(
            eligible=False,
            reason="not_online_purchase",
            rule="O direito de arrependimento de 7 dias vale para compras online.",
            deadline=None,
            days_remaining=None,
            next_step="Fale com o atendimento para avaliar uma troca presencial.",
        )
    if order.delivered_at is None:
        return ReturnEligibility(
            eligible=False,
            reason="missing_delivery_date",
            rule="É necessário confirmar a data de recebimento do produto.",
            deadline=None,
            days_remaining=None,
            next_step="Informe a data de recebimento ou fale com o atendimento.",
            handoff_required=True,
        )
    return _within_days(
        base_date=order.delivered_at,
        days=7,
        today=today,
        rule="Direito de arrependimento: até 7 dias corridos após o recebimento.",
        next_step=(
            "Solicite a devolução com o produto em embalagem original, sem uso, "
            "com acessórios e manuais. O frete de devolução é por conta da loja."
        ),
    )


def _defect(order: ReturnOrderContext, today: date) -> ReturnEligibility:
    result = _within_days(
        base_date=order.order_date,
        days=30,
        today=today,
        rule="Troca por defeito: até 30 dias corridos após a compra.",
        next_step=(
            "Solicite a troca informando o defeito. Danos por mau uso, queda, "
            "umidade ou modificação não autorizada não são cobertos."
        ),
    )
    if not result.eligible:
        result = ReturnEligibility(
            eligible=False,
            reason="warranty_window",
            rule=(
                "Passaram-se mais de 30 dias da compra; o caso segue para a "
                "garantia do fabricante."
            ),
            deadline=result.deadline,
            days_remaining=result.days_remaining,
            next_step="A loja pode intermediar a garantia do fabricante.",
            handoff_required=True,
        )
    return result


def _preference(
    order: ReturnOrderContext,
    today: date,
    desired_product_in_stock: bool | None,
) -> ReturnEligibility:
    base_date = order.delivered_at or order.order_date
    result = _within_days(
        base_date=base_date,
        days=7,
        today=today,
        rule="Troca por preferência: até 7 dias, com produto em perfeito estado.",
        next_step=(
            "A troca depende de disponibilidade do produto desejado; diferenças "
            "de valor são cobradas ou reembolsadas."
        ),
    )
    if result.eligible and desired_product_in_stock is False:
        return ReturnEligibility(
            eligible=False,
            reason="desired_product_out_of_stock",
            rule="O produto desejado está sem estoque no momento.",
            deadline=result.deadline,
            days_remaining=result.days_remaining,
            next_step="Posso sugerir alternativas disponíveis.",
        )
    return result


def _within_days(
    *,
    base_date: date,
    days: int,
    today: date,
    rule: str,
    next_step: str,
) -> ReturnEligibility:
    deadline = base_date + timedelta(days=days)
    remaining = (deadline - today).days
    if remaining < 0:
        return ReturnEligibility(
            eligible=False,
            reason="deadline_expired",
            rule=rule,
            deadline=deadline,
            days_remaining=remaining,
            next_step="O prazo da política expirou.",
        )
    return ReturnEligibility(
        eligible=True,
        reason="within_deadline",
        rule=rule,
        deadline=deadline,
        days_remaining=remaining,
        requirements=(
            "Produto em embalagem original, sem sinais de uso, com acessórios e manuais.",
        ),
        next_step=next_step,
    )


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY, rounding=ROUND_HALF_UP)
