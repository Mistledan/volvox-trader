"""Tests for the paper broker."""
import pytest

from ai_trader.trading.broker import PaperBroker


@pytest.fixture
def broker() -> PaperBroker:
    return PaperBroker(initial_balance=10000.0)


def test_initial_balance(broker: PaperBroker) -> None:
    assert broker.portfolio.cash_usd == 10000.0
    assert broker.equity() == 10000.0


def test_buy_and_sell(broker: PaperBroker) -> None:
    broker.update_prices({"BTC/USDT": 50000.0})
    trade = broker.market_buy("BTC/USDT", 5000.0, price=50000.0, reason="test")
    assert trade.quantity == pytest.approx(0.1)
    assert broker.portfolio.cash_usd == pytest.approx(5000.0)

    sell = broker.market_sell("BTC/USDT", 0.1, price=55000.0, reason="test")
    assert sell.pnl_usd == pytest.approx(500.0)
    assert broker.portfolio.cash_usd == pytest.approx(10500.0)
    assert "BTC/USDT" not in broker.portfolio.positions


def test_buy_exceeds_cash_clips(broker: PaperBroker) -> None:
    broker.update_prices({"BTC/USDT": 1000.0})
    trade = broker.market_buy("BTC/USDT", 50000.0, price=1000.0)
    assert trade.value_usd == pytest.approx(10000.0)
    assert broker.portfolio.cash_usd == 0.0


def test_sell_without_position_raises(broker: PaperBroker) -> None:
    broker.update_prices({"BTC/USDT": 1000.0})
    with pytest.raises(ValueError):
        broker.market_sell("BTC/USDT", 0.1, price=1000.0)


def test_equity_includes_liquid_value(broker: PaperBroker) -> None:
    broker.update_prices({"BTC/USDT": 1000.0})
    broker.market_buy("BTC/USDT", 5000.0, price=1000.0)
    portfolio = broker.portfolio
    broker.update_prices({"BTC/USDT": 1500.0})
    assert broker.equity() == pytest.approx(5000.0 + 5000.0 * 1.5)


def test_partial_sell(broker: PaperBroker) -> None:
    broker.update_prices({"BTC/USDT": 1000.0})
    broker.market_buy("BTC/USDT", 5000.0, price=1000.0)
    pos = broker.portfolio.positions["BTC/USDT"]
    before = pos.quantity
    broker.market_sell("BTC/USDT", before / 2, price=1100.0)
    remaining = broker.portfolio.positions["BTC/USDT"].quantity
    assert remaining == pytest.approx(before / 2)