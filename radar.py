import json
from datetime import datetime, timezone
import math
import yfinance as yf

# Universo inicial de empresas líquidas do Brasil e dos EUA.
# A cobertura é limitada a esta lista; não representa todo o mercado.
UNIVERSE = [
    ("ITUB4.SA","Itaú Unibanco","Brasil","BMFBOVESPA:ITUB4"),
    ("BBAS3.SA","Banco do Brasil","Brasil","BMFBOVESPA:BBAS3"),
    ("WEGE3.SA","WEG","Brasil","BMFBOVESPA:WEGE3"),
    ("EGIE3.SA","Engie Brasil","Brasil","BMFBOVESPA:EGIE3"),
    ("PSSA3.SA","Porto Seguro","Brasil","BMFBOVESPA:PSSA3"),
    ("VIVT3.SA","Telefônica Brasil","Brasil","BMFBOVESPA:VIVT3"),
    ("B3SA3.SA","B3","Brasil","BMFBOVESPA:B3SA3"),
    ("PETR4.SA","Petrobras","Brasil","BMFBOVESPA:PETR4"),
    ("VALE3.SA","Vale","Brasil","BMFBOVESPA:VALE3"),
    ("PRIO3.SA","PRIO","Brasil","BMFBOVESPA:PRIO3"),
    ("TOTS3.SA","TOTVS","Brasil","BMFBOVESPA:TOTS3"),
    ("RADL3.SA","Raia Drogasil","Brasil","BMFBOVESPA:RADL3"),
    ("FLRY3.SA","Fleury","Brasil","BMFBOVESPA:FLRY3"),
    ("MSFT","Microsoft","EUA","NASDAQ:MSFT"),
    ("GOOGL","Alphabet","EUA","NASDAQ:GOOGL"),
    ("META","Meta Platforms","EUA","NASDAQ:META"),
    ("NVDA","NVIDIA","EUA","NASDAQ:NVDA"),
    ("JPM","JPMorgan Chase","EUA","NYSE:JPM"),
    ("V","Visa","EUA","NYSE:V"),
    ("MA","Mastercard","EUA","NYSE:MA"),
    ("KO","Coca-Cola","EUA","NYSE:KO"),
    ("PEP","PepsiCo","EUA","NASDAQ:PEP"),
    ("PG","Procter & Gamble","EUA","NYSE:PG"),
    ("COST","Costco","EUA","NASDAQ:COST"),
    ("AMZN","Amazon","EUA","NASDAQ:AMZN"),
    ("AVGO","Broadcom","EUA","NASDAQ:AVGO"),
    ("XOM","Exxon Mobil","EUA","NYSE:XOM"),
    ("BRK-B","Berkshire Hathaway","EUA","NYSE:BRK.B"),
]

def num(info, key):
    value = info.get(key)
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None

def clamp(value, low=0, high=100):
    return max(low, min(high, value))

def score_company(ticker, name, market, tv_symbol):
    stock = yf.Ticker(ticker)
    info = stock.info
    history = stock.history(period="1y", auto_adjust=True)
    if history.empty or len(history) < 60:
        raise ValueError("histórico insuficiente")

    price = float(history["Close"].iloc[-1])
    close_6m = float(history["Close"].iloc[max(0, len(history)-126)])
    momentum = ((price / close_6m) - 1) * 100 if close_6m else None

    roe = num(info, "returnOnEquity")
    margin = num(info, "profitMargins")
    op_margin = num(info, "operatingMargins")
    debt_equity = num(info, "debtToEquity")
    fcf = num(info, "freeCashflow")
    revenue_growth = num(info, "revenueGrowth")
    earnings_growth = num(info, "earningsGrowth")
    pe = num(info, "forwardPE") or num(info, "trailingPE")

    quality_parts = []
    if roe is not None: quality_parts.append((clamp(roe * 100 / 25), .22))
    if margin is not None: quality_parts.append((clamp(margin * 100 / 25), .18))
    if op_margin is not None: quality_parts.append((clamp(op_margin * 100 / 25), .14))
    if debt_equity is not None: quality_parts.append((clamp(100 - debt_equity / 3), .16))
    if fcf is not None: quality_parts.append((85 if fcf > 0 else 15, .14))
    if revenue_growth is not None: quality_parts.append((clamp(50 + revenue_growth * 100), .08))
    if earnings_growth is not None: quality_parts.append((clamp(50 + earnings_growth * 100), .08))
    quality = sum(s*w for s,w in quality_parts) / sum(w for _,w in quality_parts) if quality_parts else None

    opportunity_parts = []
    if pe is not None and pe > 0:
        opportunity_parts.append((clamp(100 - abs(pe - 18) * 2.5), .30))
    if momentum is not None:
        opportunity_parts.append((clamp(50 + momentum * 1.25), .25))
    if revenue_growth is not None:
        opportunity_parts.append((clamp(50 + revenue_growth * 100), .20))
    if earnings_growth is not None:
        opportunity_parts.append((clamp(50 + earnings_growth * 100), .15))
    if fcf is not None:
        opportunity_parts.append((85 if fcf > 0 else 20, .10))
    opportunity = sum(s*w for s,w in opportunity_parts) / sum(w for _,w in opportunity_parts) if opportunity_parts else None

    if quality is None or opportunity is None:
        raise ValueError("fundamentos insuficientes")

    reasons = []
    if roe is not None: reasons.append(f"ROE {roe*100:.1f}%")
    if margin is not None: reasons.append(f"margem líquida {margin*100:.1f}%")
    if debt_equity is not None: reasons.append(f"dívida/patrimônio {debt_equity:.0f}")
    if pe is not None: reasons.append(f"P/L {pe:.1f}")
    if momentum is not None: reasons.append(f"variação em ~6 meses {momentum:+.1f}%")
    if fcf is not None: reasons.append("fluxo de caixa livre positivo" if fcf > 0 else "fluxo de caixa livre negativo")

    return {
        "ticker": ticker.replace(".SA",""), "name": name, "market": market,
        "tvSymbol": tv_symbol, "price": round(price, 2),
        "currency": "BRL" if market == "Brasil" else (info.get("currency") or "USD"),
        "qualityScore": round(quality, 1), "opportunityScore": round(opportunity, 1),
        "forwardPE": round(pe, 1) if pe is not None else None,
        "momentum6m": round(momentum, 1) if momentum is not None else None,
        "reasons": reasons[:4], "sector": info.get("sector") or "—",
    }

def main():
    scored, errors = [], []
    for ticker, name, market, tv_symbol in UNIVERSE:
        try:
            scored.append(score_company(ticker, name, market, tv_symbol))
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)[:120]})

    quality = sorted(scored, key=lambda x: x["qualityScore"], reverse=True)[:4]
    selected = {x["ticker"] for x in quality}
    opportunities_pool = [x for x in scored if x["ticker"] not in selected]
    opportunities = sorted(opportunities_pool, key=lambda x: x["opportunityScore"], reverse=True)[:2]

    if len(quality) < 4 or len(opportunities) < 2:
        raise RuntimeError(f"Cobertura insuficiente: {len(quality)} qualidade, {len(opportunities)} oportunidades.")

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "provider": "Yahoo Finance via yfinance",
        "methodology": "Pontuações heurísticas próprias; não são recomendação. Universo limitado à lista configurada.",
        "quality": quality, "opportunities": opportunities,
        "coverage": {"analyzed": len(scored), "universe": len(UNIVERSE), "errors": errors[:12]},
    }
    with open("ranking.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Ranking salvo: {len(scored)}/{len(UNIVERSE)} ativos analisados.")

if __name__ == "__main__":
    main()
