# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo", "pandas", "numpy", "scipy", "altair", "tzdata"]
# ///
import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium", app_title="Is a home battery worth it on Octopus Agile?")


@app.cell(hide_code=True)
def _():
    import math

    import altair as alt
    import marimo as mo
    import numpy as np
    import pandas as pd
    import tzdata  # noqa: F401  (time-zone data; the browser's Python (Pyodide) ships without it)
    from scipy.optimize import linprog
    from scipy.sparse import lil_matrix
    return alt, linprog, lil_matrix, math, mo, np, pd


@app.cell(hide_code=True)
def _():
    # Chart tokens (validated default palette): series 1 blue, series 2 orange; sequential blue ramp.
    BLUE, ORANGE = "#2a78d6", "#eb6834"
    BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
    AXIS = dict(gridColor="#e1e0d9", domainColor="#c3c2b7", tickColor="#c3c2b7",
                labelColor="#898781", titleColor="#898781", labelFontSize=11, titleFontSize=11)

    def hour_axis(title=None):
        import altair as _alt
        return _alt.Axis(title=title, values=list(range(0, 25, 3)), labelExpr="datum.value + ':00'")
    return AXIS, BLUE, BLUE_RAMP, ORANGE, hour_axis


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Is a home battery worth it on Octopus Agile?

    A UK household with **no solar and no export** asks whether a
    5 kWh plug-in battery (Anker SOLIX Solarbank 4 E5000 Pro, about £1,699 +
    installation) pays for itself on Octopus **Agile**. Agile's price changes every half-hour,
    so a battery can charge when power is cheap and run the house when it's expensive.

    Below: first what the household's usage and Agile prices actually look like, then a battery
    model you can change and re-run. Everything runs in your browser.
    """)
    return


@app.cell(hide_code=True)
def _(pd, mo):
    def _read(name):
        src = str(mo.notebook_location() / "public" / name)
        if src.startswith("http"):
            # In the browser: GitHub Pages serves CSVs gzip-encoded and pandas' own URL reader then
            # tries to gunzip text the browser already decoded. Fetch with Pyodide instead.
            from pyodide.http import open_url
            return pd.read_csv(open_url(src))
        return pd.read_csv(src)

    _load = _read("load_halfhourly.csv")
    _prices = _read("agile_prices.csv")
    df = _load.merge(_prices, on="interval_start")
    df.index = pd.to_datetime(df.pop("interval_start"), utc=True)
    df = df.sort_index()
    TZ = "Europe/London"
    local = df.index.tz_convert(TZ)
    # tidy frame for exploration: one row per half-hour with local time features
    hh = df.assign(
        day=local.date, month=local.strftime("%Y-%m"), hour=local.hour + local.minute / 60,
        weekend=local.dayofweek >= 5, kw=df["load_kwh"] * 2, cost_p=df["load_kwh"] * df["price_p"],
    )
    MONTHS = sorted(hh["month"].unique())
    MONTH_LABEL = {m: pd.Period(m).strftime("%b %y") for m in MONTHS}
    hh["month_label"] = hh["month"].map(MONTH_LABEL)
    return MONTHS, MONTH_LABEL, TZ, df, hh, local


@app.cell(hide_code=True)
def _(hh, mo):
    _daily = hh.groupby("day").agg(kwh=("load_kwh", "sum"), peak_kw=("kw", "max"), base_kw=("kw", "min"),
                                   cost=("cost_p", "sum"))
    _peak_hour = hh.loc[hh.groupby("day")["kw"].idxmax(), "hour"]
    _typical_peak = _peak_hour.round().mode().iloc[0]
    _evening = hh.loc[(hh.hour >= 16) & (hh.hour < 19), "load_kwh"].sum() / hh["load_kwh"].sum()
    _wavg = (hh["load_kwh"] * hh["price_p"]).sum() / hh["load_kwh"].sum()
    mo.vstack([
        mo.md("## What the data shows\n\n"
              f"{len(_daily)} days of half-hourly electricity import, {hh.month_label.iloc[0]} to {hh.month_label.iloc[-1]}."),
        mo.hstack([
            mo.stat(f"{_daily.kwh.mean():.1f} kWh", label="Average day", caption=f"≈ {_daily.kwh.mean() * 365:,.0f} kWh/yr"),
            mo.stat(f"{_daily.base_kw.median() * 1000:.0f} W", label="Always-on base load",
                    caption="median of each day's quietest half-hour"),
            mo.stat(f"{_daily.peak_kw.median():.1f} kW", label="Typical daily peak",
                    caption=f"most often around {int(_typical_peak):02d}:00"),
            mo.stat(f"{_evening:.0%}", label="Use in 16:00-19:00", caption="Agile's most expensive window"),
            mo.stat(f"{_wavg:.1f}p", label="Average price paid", caption=f"vs {hh.price_p.mean():.1f}p simple average"),
        ], justify="start", gap=1, wrap=True),
    ])
    return


@app.cell(hide_code=True)
def _(AXIS, BLUE_RAMP, MONTH_LABEL, MONTHS, alt, hh, hour_axis, mo):
    _g = hh.groupby(["month_label", "hour"], as_index=False).agg(kw=("kw", "mean"), price=("price_p", "mean"))
    _g["hour_end"] = _g["hour"] + 0.5
    _order = [MONTH_LABEL[m] for m in MONTHS]
    _y = alt.Y("month_label:O", title=None, sort=_order)
    _x = alt.X("hour:Q", axis=hour_axis(), scale=alt.Scale(domain=[0, 24], nice=False))
    _usage = alt.Chart(_g).mark_rect().encode(
        x=_x, x2="hour_end:Q", y=_y,
        color=alt.Color("kw:Q", title="kW", scale=alt.Scale(range=BLUE_RAMP),
                        legend=alt.Legend(orient="right", gradientLength=140)),
        tooltip=[alt.Tooltip("month_label:N", title="Month"), alt.Tooltip("hour:Q", title="From (h)", format=".1f"),
                 alt.Tooltip("kw:Q", title="Average kW", format=".2f")],
    ).properties(title="Average usage by month and time of day", height=240, width="container").configure_axis(**AXIS)
    _price = alt.Chart(_g).mark_rect().encode(
        x=_x, x2="hour_end:Q", y=_y,
        color=alt.Color("price:Q", title="p/kWh", scale=alt.Scale(scheme="oranges"),
                        legend=alt.Legend(orient="right", gradientLength=140)),
        tooltip=[alt.Tooltip("month_label:N", title="Month"), alt.Tooltip("hour:Q", title="From (h)", format=".1f"),
                 alt.Tooltip("price:Q", title="Average p/kWh", format=".1f")],
    ).properties(title="Average Agile price by month and time of day", height=240, width="container").configure_axis(**AXIS)
    mo.vstack([
        mo.md("### When power is used, and when it's expensive\n\n"
              "Darker means more. Usage stays fairly high from mid-morning to late evening, with no single evening spike, "
              "and is heaviest from July to September. Agile's dark band is 16:00-19:00 all year. The cheapest hours are "
              "overnight and, in spring and summer, around midday when solar floods the grid."),
        _usage, _price,
    ])
    return


@app.cell(hide_code=True)
def _(AXIS, BLUE, ORANGE, alt, hh, hour_axis, mo, pd):
    _peak = hh.loc[hh.groupby("day")["kw"].idxmax(), ["hour", "weekend"]]
    _peak["bucket"] = _peak["hour"].astype(int)
    _counts = (_peak.groupby("bucket").size().reindex(range(24), fill_value=0)
               .rename_axis("bucket").rename("days").reset_index())
    _counts["share"] = _counts["days"] / _counts["days"].sum()
    _counts["end"] = _counts["bucket"] + 1
    _hist = alt.Chart(_counts).mark_rect(color=BLUE, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, stroke="white",
                                         strokeWidth=2).encode(
        x=alt.X("bucket:Q", axis=hour_axis(), scale=alt.Scale(domain=[0, 24], nice=False)), x2="end:Q",
        y=alt.Y("share:Q", title="Share of days", axis=alt.Axis(format="%")),
        tooltip=[alt.Tooltip("bucket:Q", title="Hour starting"), alt.Tooltip("days:Q", title="Days"),
                 alt.Tooltip("share:Q", title="Share", format=".0%")],
    ).properties(title="When the day's biggest half-hour happens", height=220, width="container").configure_axis(**AXIS)

    _prof = hh.assign(kind=hh["weekend"].map({False: "Weekday", True: "Weekend"})).groupby(
        ["kind", "hour"], as_index=False)["kw"].mean()
    _lines = alt.Chart(_prof).mark_line(strokeWidth=2).encode(
        x=alt.X("hour:Q", axis=hour_axis(), scale=alt.Scale(domain=[0, 24], nice=False)),
        y=alt.Y("kw:Q", title="Average kW"),
        color=alt.Color("kind:N", title=None, scale=alt.Scale(domain=["Weekday", "Weekend"], range=[BLUE, ORANGE]),
                        legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("kind:N"), alt.Tooltip("hour:Q", title="Time (h)", format=".1f"),
                 alt.Tooltip("kw:Q", title="Average kW", format=".2f")],
    )
    _band = alt.Chart(pd.DataFrame({"a": [16], "b": [19]})).mark_rect(opacity=0.08, color="#898781").encode(x="a:Q", x2="b:Q")
    _week = alt.layer(_band, _lines).properties(title="Average day: weekday vs weekend (16:00-19:00 shaded)",
                                                height=220, width="container").configure_axis(**AXIS)
    mo.vstack([mo.md("### Daily peaks\n\nThe day's biggest half-hour can come at any time from mid-morning to late evening. "
                     "Only a minority of days peak inside the expensive 16:00-19:00 window, which limits what a battery can save."),
               mo.hstack([_hist, _week], widths="equal", wrap=True)])
    return


@app.cell(hide_code=True)
def _(AXIS, BLUE, MONTH_LABEL, MONTHS, alt, hh, mo):
    _d = hh.groupby(["month_label", "day"], as_index=False).agg(kwh=("load_kwh", "sum"), cost=("cost_p", "sum"))
    _m = _d.groupby("month_label", as_index=False).agg(kwh=("kwh", "mean"), cost=("cost", "mean"), days=("day", "count"))
    _m["cost"] = _m["cost"] / 100
    _m["unit"] = _m["cost"] * 100 / _m["kwh"]
    _order = [MONTH_LABEL[m] for m in MONTHS]
    _bars = alt.Chart(_m).mark_bar(color=BLUE, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("month_label:O", sort=_order, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("kwh:Q", title="kWh per day"),
        tooltip=[alt.Tooltip("month_label:N", title="Month"), alt.Tooltip("kwh:Q", title="kWh/day", format=".1f"),
                 alt.Tooltip("cost:Q", title="£/day on Agile", format=".2f"),
                 alt.Tooltip("unit:Q", title="Average p/kWh", format=".1f"), alt.Tooltip("days:Q", title="Days")],
    ).properties(title="Average daily usage by month", height=220, width="container").configure_axis(**AXIS)
    mo.vstack([mo.md("### Across the year\n\nDaily use rose steadily, from about 8 kWh/day in Jan-Feb to about 15 in September "
                     "(December covers only the 18th onwards). Hover for the daily cost if the whole period had been on Agile."), _bars])
    return


@app.cell(hide_code=True)
def _(mo):
    capacity = mo.ui.number(start=0.5, stop=20.0, step=0.001, value=5.024, label="Usable capacity (kWh)")
    power = mo.ui.slider(start=0.8, stop=5.0, step=0.1, value=2.5, label="Charge / discharge power (kW)", show_value=True)
    rte = mo.ui.slider(start=0.80, stop=0.97, step=0.01, value=0.90, label="Round-trip efficiency", show_value=True)
    standby = mo.ui.number(start=0, stop=50, step=1, value=10, label="Standby draw (W)")
    price = mo.ui.number(start=0, stop=10000, step=1, value=1699, label="Battery price (£)")
    install = mo.ui.number(start=0, stop=3000, step=1, value=400, label="Installation (£)")
    form = mo.md("""
    ## The battery model

    Defaults are the Solarbank 4 E5000 Pro. Change anything and press **Run the model**.

    {capacity} {power}

    {rte} {standby}

    {price} {install}
    """).batch(capacity=capacity, power=power, rte=rte, standby=standby, price=price, install=install).form(
        submit_button_label="Run the model", bordered=True)
    form
    return (form,)


@app.cell(hide_code=True)
def _(form):
    cfg = form.value or dict(capacity=5.024, power=2.5, rte=0.90, standby=10, price=1699, install=400)
    return (cfg,)


@app.cell(hide_code=True)
def _(TZ, df, lil_matrix, linprog, math, np, pd):
    SLOT_H = 0.5

    def params(cfg):
        eta = math.sqrt(cfg["rte"])
        return dict(cap=cfg["capacity"], pc=cfg["power"] * SLOT_H, pd=cfg["power"] * SLOT_H, eta_c=eta, eta_d=eta)

    def _lp(price, load, soc0, P):
        n = len(price)
        A = lil_matrix((n, 3 * n))
        for t in range(n):
            A[t, 2 * n + t] = 1.0
            if t:
                A[t, 2 * n + t - 1] = -1.0
            A[t, t] = -P["eta_c"]
            A[t, n + t] = 1.0 / P["eta_d"]
        b = np.zeros(n); b[0] = soc0
        cost = np.concatenate([price + 0.001, -price + 0.001, np.zeros(n)])
        bounds = [(0, P["pc"])] * n + [(0, min(P["pd"], max(l, 0.0))) for l in load] + [(0, P["cap"])] * n
        x = linprog(cost, A_eq=A.tocsr(), b_eq=b, bounds=bounds, method="highs").x
        return x[:n], x[n:2 * n], x[2 * n:]

    def run_lp(P):
        """Optimal: each day optimised over today + tomorrow (Agile publishes ~16:00), today committed."""
        days = df.groupby(df.index.tz_convert(TZ).date).indices
        keys = sorted(days)
        price, load = df["price_p"].to_numpy(), df["load_kwh"].to_numpy()
        c = np.zeros(len(df)); d = np.zeros(len(df)); soc = 0.0
        for i, k in enumerate(keys):
            idx = days[k]
            hz = np.concatenate([idx, days[keys[i + 1]]]) if i + 1 < len(keys) else idx
            hc, hd, hs = _lp(price[hz], load[hz], soc, P)
            m = len(idx)
            c[idx], d[idx] = hc[:m], hd[:m]
            soc = float(np.clip(hs[m - 1], 0, P["cap"]))
        return c, d

    def run_rule(P):
        """Simple: charge in the cheapest slots 23:00-07:00, discharge 16:00-23:00 to cover load."""
        local = df.index.tz_convert(TZ)
        hour = local.hour
        night = (hour >= 23) | (hour < 7)
        win = pd.Series((local + pd.Timedelta(hours=1)).date, index=df.index)
        n_slots = math.ceil(P["cap"] / (P["pc"] * P["eta_c"]))
        charge = np.zeros(len(df), bool)
        for _, g in df[night].assign(win=win[night]).groupby("win"):
            charge[df.index.get_indexer(g.nsmallest(n_slots, "price_p").index)] = True
        dis = (hour >= 16) & (hour < 23)
        load = df["load_kwh"].to_numpy()
        c = np.zeros(len(df)); d = np.zeros(len(df)); soc = 0.0
        for t in range(len(df)):
            if charge[t]:
                c[t] = min(P["pc"], (P["cap"] - soc) / P["eta_c"]); soc += c[t] * P["eta_c"]
            elif dis[t]:
                d[t] = min(P["pd"], max(load[t], 0), soc * P["eta_d"]); soc -= d[t] / P["eta_d"]
        return c, d

    MONTH_DAYS = {m: pd.Period(f"2026-{m:02d}").days_in_month for m in range(1, 13)}

    def annualise(daily_by_month):
        """Σ days-in-month × mean daily value; Oct/Nov (no data) interpolated between Sep and Dec."""
        m = dict(daily_by_month)
        if 9 in m and 12 in m:
            m.setdefault(10, m[9] + (m[12] - m[9]) / 3)
            m.setdefault(11, m[9] + (m[12] - m[9]) * 2 / 3)
        return sum(MONTH_DAYS[k] * v for k, v in m.items())

    def evaluate(c, d, P, standby_w):
        price = df["price_p"].to_numpy()
        sb = standby_w / 1000 * SLOT_H
        load = df["load_kwh"].to_numpy()
        save = (load * price - (load - d + c + sb) * price) / 100
        loc = df.index.tz_convert(TZ)
        s = pd.DataFrame({"save": save, "d": d, "c": c, "price": price, "month": loc.month, "day": loc.date,
                          "ym": loc.strftime("%b %y"), "hour": loc.hour + loc.minute / 60}, index=df.index)
        daily = s.groupby(["month", "day"]).agg(save=("save", "sum"), d=("d", "sum"))
        return dict(
            annual=annualise(daily["save"].groupby("month").mean().to_dict()),
            cycles=annualise(daily["d"].groupby("month").mean().to_dict()) / P["eta_d"] / P["cap"],
            spread=(s.d @ s.price) / s.d.sum() - (s.c @ s.price) / s.c.sum() if s.c.sum() and s.d.sum() else 0.0,
            monthly=s.groupby("ym", sort=False)["save"].sum(),
            by_hour=s.groupby("hour")[["c", "d"]].mean(),
        )
    return evaluate, params, run_lp, run_rule


@app.cell(hide_code=True)
def _(cfg, evaluate, mo, params, run_lp, run_rule):
    P = params(cfg)
    with mo.status.spinner(title="Simulating every half-hour…"):
        res = {
            "Smart (day-ahead optimal)": evaluate(*run_lp(P), P, cfg["standby"]),
            "Simple rule (night charge, evening use)": evaluate(*run_rule(P), P, cfg["standby"]),
        }
    return (res,)


@app.cell(hide_code=True)
def _(cfg, mo, res):
    capex = cfg["price"] + cfg["install"]

    def fin(s, fade=0.01, years=10, rate=0.04):
        yearly = [s * (1 - fade) ** y for y in range(years)]
        return dict(payback=capex / s if s > 0 else float("inf"), net=sum(yearly) - capex,
                    npv=sum(v / (1 + rate) ** (y + 1) for y, v in enumerate(yearly)) - capex)

    _tiles = []
    for _name, _r in res.items():
        _f = fin(_r["annual"])
        _tiles.append(mo.vstack([
            mo.md(f"### {_name}"),
            mo.hstack([
                mo.stat(f"£{_r['annual']:,.0f}", label="Saving per year"),
                mo.stat(f"{_f['payback']:.1f} yrs" if _f["payback"] != float("inf") else "never", label="Simple payback"),
                mo.stat(f"£{_f['net']:,.0f}", label="10-yr net (1%/yr fade)"),
                mo.stat(f"£{_f['npv']:,.0f}", label="10-yr net at 4% discount"),
            ], justify="start", gap=1, wrap=True),
            mo.md(f"{_r['cycles']:.0f} cycles/yr · average spread captured {_r['spread']:.1f}p/kWh"),
        ]))
    _need = capex / sum(0.99 ** y for y in range(7))
    _best = max(r["annual"] for r in res.values())
    mo.vstack([
        mo.md(f"## Result for £{capex:,.0f} all-in"),
        *_tiles,
        mo.callout(mo.md(
            f"A **7-year payback** would need about **£{_need:,.0f}/yr**, which is "
            f"{_need / _best:.1f}× the best strategy above."), kind="info"),
    ])
    return


@app.cell(hide_code=True)
def _(AXIS, BLUE, ORANGE, alt, hour_axis, mo, pd, res):
    _colors = dict(zip(res, [BLUE, ORANGE]))
    _m = pd.concat([r["monthly"].rename(k) for k, r in res.items()], axis=1).reset_index(names="month").melt(
        "month", var_name="strategy", value_name="saving")
    _order = list(res[next(iter(res))]["monthly"].index)
    _monthly = alt.Chart(_m).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("month:N", title=None, sort=_order, axis=alt.Axis(labelAngle=0)),
        xOffset=alt.XOffset("strategy:N", sort=list(_colors)),
        y=alt.Y("saving:Q", title="Saving (£)"),
        color=alt.Color("strategy:N", title=None, legend=alt.Legend(orient="top", labelLimit=0),
                        scale=alt.Scale(domain=list(_colors), range=list(_colors.values()))),
        tooltip=[alt.Tooltip("month:N"), alt.Tooltip("strategy:N"), alt.Tooltip("saving:Q", title="Saving (£)", format=".2f")],
    ).properties(title="Saving by month", height=240, width="container").configure_axis(**AXIS)

    _smart = res[next(iter(res))]["by_hour"].reset_index()
    _flow = pd.concat([
        _smart.assign(kind="Charging from grid", kw=_smart["c"] * 2),
        _smart.assign(kind="Supplying the house", kw=-_smart["d"] * 2),
    ])
    _flow["end"] = _flow["hour"] + 0.5
    _when = alt.Chart(_flow).mark_rect(stroke="white", strokeWidth=1).encode(
        x=alt.X("hour:Q", axis=hour_axis(), scale=alt.Scale(domain=[0, 24], nice=False)), x2="end:Q",
        y=alt.Y("kw:Q", title="Average kW (charge + / discharge −)"),
        color=alt.Color("kind:N", title=None, legend=alt.Legend(orient="top"),
                        scale=alt.Scale(domain=["Charging from grid", "Supplying the house"], range=[BLUE, ORANGE])),
        tooltip=[alt.Tooltip("kind:N"), alt.Tooltip("hour:Q", title="Time (h)", format=".1f"),
                 alt.Tooltip("kw:Q", title="Average kW", format=".2f")],
    ).properties(title="What the smart battery does, on average", height=240, width="container").configure_axis(**AXIS)
    mo.vstack([
        mo.md("Dec is a partial month (from the 18th). Dec to mid-Mar is priced *as if* on Agile; the household was "
              "actually on a fixed tariff then."),
        _monthly,
        mo.md("The smart strategy charges overnight and, from spring, in the cheap midday dip, then covers the "
              "evening peak. Because there's no export it can never discharge more than the house is using, which is "
              "what caps the saving."),
        _when,
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Verdict

    **Marginal.** With good automated day-ahead scheduling the battery saves roughly £235 a year, which pays back
    in about 9-10 years and roughly breaks even over 10 years (it loses money once you discount future savings).
    A fixed overnight-charge/evening-discharge timer earns only about half that. The house uses
    relatively little in the evening peak, so a 5 kWh battery often runs out of load to serve before it runs out
    of charge. It's not worth buying purely to trade on Agile prices. It looks better with solar, or if Agile's
    gap between cheap and expensive hours widens.

    ## How the model works

    - **No export.** In each half-hour the battery can only supply up to what the house is using.
      Standing charges are unchanged, so they're left out.
    - **Smart strategy:** each day is solved as a linear program over today plus tomorrow (Agile prices for
      tomorrow are published around 16:00), and today's plan is committed. Charge left in the battery carries
      over to the next day. Because it assumes perfect foresight of those prices, it is an upper bound.
    - **Simple rule:** charge in the cheapest overnight slots (23:00-07:00) until full, then discharge from
      16:00 to 23:00. This is roughly what a fixed timer would do: a realistic lower bound.
    - **Efficiency** is split evenly between charging and discharging (√RTE each way). Standby draw is bought at the
      half-hour's price.
    - **One year** is built from the average daily saving in each calendar month. October and November have no data,
      so they're interpolated between September and December.
    - **Grid charging on a schedule:** Anker lists Time-of-Use and Dynamic Tariff modes with 2.5 kW grid charging
      for the UK model (with its smart meter/CT). Whether output to the house is capped at 800 W unless it is
      hardwired is unconfirmed; set the power to 0.8 kW to see that case.

    ## About the data

    Household usage is **anonymised** before publishing:

    - No account, meter or address identifiers are included, and gas is left out.
    - Within each month, whole days are randomly swapped with other days of the same kind (weekday with weekday,
      weekend with weekend). Daily shapes, weekday/weekend patterns and monthly totals are real, but the
      specific dates aren't.

    Agile prices (region H) are Octopus's public prices. Results on this anonymised data are within a
    few pounds a year of the private original.

    *Built with [marimo](https://marimo.io); it runs entirely in your browser.*
    """)
    return


if __name__ == "__main__":
    app.run()
