from fastapi import FastAPI

from app.routers import (
    b3_indexes,
    companies,
    crypto,
    currencies,
    fiis,
    macro_series,
    metals,
    options,
    rates,
    stocks,
    us_stocks,
)

app = FastAPI(title="Lume Finance API", version="0.1.0")
app.include_router(macro_series.router)
app.include_router(stocks.router)
app.include_router(companies.router)
app.include_router(fiis.router)
app.include_router(fiis.resolve_router)
app.include_router(crypto.router)
app.include_router(b3_indexes.router)
app.include_router(metals.router)
app.include_router(us_stocks.router)
app.include_router(rates.router)
app.include_router(currencies.router)
app.include_router(options.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
