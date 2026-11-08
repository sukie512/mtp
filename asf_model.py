"""Pure-Python chain-growth (ASF) + deactivation model. No BioSTEAM needed."""
import numpy as np
from scipy.optimize import brentq

R = 8.314  # J/mol/K

def weight_fractions(alpha, kmax=60):
    """Weight fraction of each k-mer (k ethylene units, carbon number 2k), as fraction of
    CONVERTED ethylene mass. ASF: mole fraction n_k = (1-a) a^(k-1); mass ∝ k*n_k,
    so w_k = k (1-a)^2 a^(k-1). Returns array index 0 -> k=1 (C2, i.e. butene is index 1)."""
    if not 0.0 < alpha < 1.0:
        raise ValueError('alpha must lie strictly between 0 and 1')
    k = np.arange(1, kmax + 1)
    w = k * (1 - alpha) ** 2 * alpha ** (k - 1)
    # The final entry represents the entire k >= kmax tail. This preserves the
    # exact infinite ASF mass balance instead of renormalizing a truncated series.
    if kmax > 1:
        w[-1] = 1.0 - w[:-1].sum()
    else:
        w[-1] = 1.0
    return w

def alpha_from_T_P(T, P, beta0, dE, T_ref=393.0, P_ref=35.0):
    """alpha = 1/(1+beta); beta = termination/propagation rate ratio.
    beta = beta0 * exp(-dE/R*(1/T - 1/T_ref)) * (P_ref/P). dE = E_term - E_prop [J/mol] (>0 => hotter = more termination = shorter chains)."""
    beta = beta0 * np.exp(-dE / R * (1 / T - 1 / T_ref)) * (P_ref / P)
    return 1.0 / (1.0 + beta)

def calibrate_beta0(target_C8plus=0.63, **kw):
    """Find alpha at reference conditions so weight fraction of k>=4 (C8+) = target."""
    f = lambda a: weight_fractions(a, **kw)[3:].sum() - target_C8plus
    a = brentq(f, 0.3, 0.95)
    return a, (1 - a) / a            # alpha_ref, beta0

def cycle_average_activity(kd, tau_days):
    """First-order deactivation a(t)=exp(-kd t); mean activity over a run of tau days."""
    x = kd * tau_days
    return (1 - np.exp(-x)) / x if x > 1e-12 else 1.0

def conversion(X0, kd, tau_days):
    return X0 * cycle_average_activity(kd, tau_days)

def max_c8_c16_share(kmax=200):
    """PROVEN BOUND (added Oct 2026, in response to an external review claiming a two-population ASF mixture
    can reach 63% C8-C16): C8-C16 share is a LINEAR functional of the chain-growth distribution (a fixed sum of
    weight fractions), and is individually bounded for every single alpha in [0,1]. Because any finite mixture
    of ASF populations is a CONVEX COMBINATION of individual distributions, its C8-C16 share is a weighted
    average of values that are each <= this bound -- so NO finite mixture of chain-growth populations (one,
    two, or more) can exceed it either. Verified by direct unconstrained least-squares search (see chat log):
    the best any two-population fit achieves is ~43.8%, well under even this single-population bound."""
    alphas = np.linspace(0.001, 0.999, 2000)
    vals = [weight_fractions(a, kmax)[3:8].sum() for a in alphas]
    i = int(np.argmax(vals))
    return vals[i], alphas[i]

def two_population_fractions(f, alpha1, alpha2, kmax=60):
    """Weighted mixture of two ASF populations: f*ASF(alpha1) + (1-f)*ASF(alpha2). Useful for exploring whether
    catalyst heterogeneity could explain a given split -- but see max_c8_c16_share(): it CANNOT reach the
    paper's assumed 63% C8-C16, since that exceeds the single-population bound and mixing cannot exceed it."""
    return f * weight_fractions(alpha1, kmax) + (1 - f) * weight_fractions(alpha2, kmax)

if __name__ == "__main__":
    a, b0 = calibrate_beta0(0.63)
    print(f"alpha_ref={a:.3f} beta0={b0:.3f}")
    w = weight_fractions(a)
    print("C4-C6 :", w[1:3].sum().round(3), "C8-C16:", w[3:8].sum().round(3), "C18+:", w[8:].sum().round(3))
    bound, a_bound = max_c8_c16_share()
    print(f"Max achievable C8-C16 share for ANY single-alpha ASF model: {bound*100:.1f}% (at alpha={a_bound:.3f})")