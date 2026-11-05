from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.modules.agent.domain.store_policy import (
    ReturnItemContext,
    ReturnOrderContext,
    ReturnReason,
    StoreSchedule,
    calculate_payment_options,
    estimate_shipping,
    evaluate_return,
)


def test_store_status_handles_weekday_and_weekend() -> None:
    schedule = StoreSchedule()

    monday = schedule.status_at(datetime(2026, 11, 2, 12, 0, tzinfo=UTC))
    saturday = schedule.status_at(datetime(2026, 11, 7, 15, 0, tzinfo=UTC))
    sunday = schedule.status_at(datetime(2026, 11, 8, 15, 0, tzinfo=UTC))

    assert monday.is_open is True
    assert monday.local_time.hour == 9
    assert saturday.is_open is True
    assert sunday.is_open is False
    assert sunday.next_opening is not None
    assert sunday.next_opening.weekday() == 0


def test_store_status_handles_holiday() -> None:
    schedule = StoreSchedule(holidays=frozenset({date(2026, 11, 2)}))

    status = schedule.status_at(datetime(2026, 11, 2, 12, 0, tzinfo=UTC))

    assert status.is_open is False
    assert status.is_holiday is True


def test_payment_pix_discount_only_on_regular_price() -> None:
    regular = calculate_payment_options(Decimal("100.00"), promotional=False)
    promotional = calculate_payment_options(Decimal("80.00"), promotional=True)

    pix = next(option for option in regular.options if option.method == "pix")
    promo_pix = next(
        option for option in promotional.options if option.method == "pix"
    )

    assert pix.total_brl == Decimal("95.00")
    assert pix.discount_percent == 5
    assert promo_pix.total_brl == Decimal("80.00")
    assert promo_pix.discount_percent == 0


def test_payment_installment_minimums() -> None:
    options = calculate_payment_options(Decimal("500.00"), promotional=False)

    six = next(
        option for option in options.options if option.method == "credit_6x"
    )
    twelve = next(
        option for option in options.options if option.method == "credit_12x"
    )
    low = calculate_payment_options(Decimal("40.00"), promotional=False)
    low_three = next(
        option for option in low.options if option.method == "credit_3x"
    )

    assert six.available is True
    assert six.installment_brl == Decimal("83.33")
    assert twelve.available is False
    assert low_three.available is False


def test_combined_payment_only_above_two_thousand() -> None:
    assert (
        calculate_payment_options(
            Decimal("2000.00"), promotional=False
        ).combined_allowed
        is False
    )
    assert (
        calculate_payment_options(
            Decimal("2000.01"), promotional=False
        ).combined_allowed
        is True
    )


def test_shipping_metro_and_other_city() -> None:
    metro = estimate_shipping(
        cep="79000-000",
        subtotal_brl=Decimal("600.00"),
        metro_cep_prefixes=("790", "791"),
    )
    other = estimate_shipping(
        cep="80000-000",
        subtotal_brl=Decimal("600.00"),
        metro_cep_prefixes=("790", "791"),
    )

    assert metro.requires_quote is False
    assert metro.free_shipping is True
    assert other.requires_quote is True
    assert other.shipping_brl is None
    assert len(other.modalities) == 3


def test_shipping_rejects_invalid_cep() -> None:
    with pytest.raises(ValueError):
        estimate_shipping(
            cep="123",
            subtotal_brl=Decimal("100.00"),
            metro_cep_prefixes=("790",),
        )


def _order(
    *,
    channel: str = "online",
    delivered_at: date | None = date(2026, 10, 30),
    order_date: date = date(2026, 10, 20),
    status: str = "delivered",
    item: ReturnItemContext | None = None,
) -> ReturnOrderContext:
    return ReturnOrderContext(
        order_id=1,
        status=status,
        sales_channel=channel,
        order_date=order_date,
        delivered_at=delivered_at,
        items=(
            item
            or ReturnItemContext(product_id=10, product_name="Yamaha C40"),
        ),
    )


def test_withdrawal_within_seven_days() -> None:
    result = evaluate_return(
        order=_order(),
        product_id=10,
        reason=ReturnReason.WITHDRAWAL,
        today=date(2026, 11, 2),
    )

    assert result.eligible is True
    assert result.days_remaining == 4


def test_withdrawal_requires_online_channel() -> None:
    result = evaluate_return(
        order=_order(channel="in_store"),
        product_id=10,
        reason=ReturnReason.WITHDRAWAL,
        today=date(2026, 11, 2),
    )

    assert result.eligible is False
    assert result.reason == "not_online_purchase"


def test_defect_after_thirty_days_goes_to_warranty() -> None:
    result = evaluate_return(
        order=_order(order_date=date(2026, 9, 1)),
        product_id=10,
        reason=ReturnReason.DEFECT,
        today=date(2026, 11, 2),
    )

    assert result.eligible is False
    assert result.reason == "warranty_window"
    assert result.handoff_required is True


def test_preference_respects_item_restrictions() -> None:
    result = evaluate_return(
        order=_order(
            item=ReturnItemContext(
                product_id=10,
                product_name="Boquilha",
                is_hygiene_restricted=True,
            )
        ),
        product_id=10,
        reason=ReturnReason.PREFERENCE,
        today=date(2026, 11, 2),
    )

    assert result.eligible is False
    assert result.reason == "hygiene_restricted"
