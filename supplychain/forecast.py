"""Forecasts based exclusively on past observed (uncensored) demand."""
import numpy as np
from statistics import NormalDist


def safety_stock(history, protection_days=2, quantile=.9):
    """Normal approximation to protection-period forecast error; no service guarantee.

    Residuals are generated with expanding past-only windows, using at most the
    last 28 observations. Demand correlation and non-normal tails remain limitations.
    """
    a = np.asarray(history, float)
    if (a.ndim != 3 or len(a) < 14 or not np.isfinite(a).all()
            or (a < 0).any() or protection_days < 1 or not .5 <= quantile < 1):
        raise ValueError('Invalid safety-stock history, protection period or quantile')
    residuals = np.array([a[t] - predict(a[:t], 1)[0]
                          for t in range(max(7, len(a)-28), len(a))])
    sigma = residuals.std(axis=0, ddof=1)
    return np.ceil(NormalDist().inv_cdf(quantile)*sigma*np.sqrt(protection_days)).astype(int)

def predict(history, horizon, buffer=0.):
    a = np.asarray(history,float)
    if a.ndim != 3 or len(a)<7 or horizon<1 or not np.isfinite(a).all() or (a<0).any() or not 0 <= buffer <= 2:
        raise ValueError('Need at least seven days of valid channel/product demand')
    recent=a[-7:].mean(0)
    forecasts=[]
    for step in range(horizon):
        indices=np.arange(len(a)+step-7,-1,-7)
        indices=indices[(indices>=max(0,len(a)-28)) & (indices<len(a))]
        seasonal=a[indices].mean(0) if len(indices) else recent
        forecasts.append(.65*recent+.35*seasonal)
    # Buffer uses only pre-decision history; it is a heuristic, not a robust guarantee.
    scale=a[-28:].std(0,ddof=1)
    return np.maximum(0,np.rint(np.asarray(forecasts)+buffer*scale)).astype(int)


def synthetic_history(net, seed, days=20, regime='normal', training=42):
    if regime not in {'normal','surge','supply_shock'}:
        raise ValueError('Unknown regime')
    rng=np.random.default_rng(seed)
    total=training+days
    weekday=np.array([.92,.96,1.,1.02,1.12,1.20,.78])
    common=rng.lognormal(-.18**2/2,.18,(total,1,1))
    local=rng.lognormal(-.12**2/2,.12,(total,net.C,net.P))
    rate=net.mean_demand[None,:,:]*weekday[np.arange(total)%7,None,None]*common*local
    if regime=='surge':
        rate[training+days//3:]*=1.45
    demands=rng.poisson(rate)
    return demands[:training],demands[training:]
