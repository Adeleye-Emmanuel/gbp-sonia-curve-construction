import math


class Curve:
    def __init__(self, discount_factors: dict[float, float]):
        if min(discount_factors) > 0.0:
            discount_factors = {**discount_factors, 0.0: 1.0}
        self.pillars = sorted(discount_factors.items())

    def discount_factor(self, T: float) -> float:
        for pillar_T, D in self.pillars:
            if pillar_T == T:
                return D

        if T < self.pillars[0][0] or T > self.pillars[-1][0]:
            raise ValueError(f"T={T} is outside the pillar range; extrapolation is not supported")

        for (T_i, D_i), (T_j, D_j) in zip(self.pillars, self.pillars[1:]):
            if T_i < T < T_j:
                ln_D = math.log(D_i) + (math.log(D_j) - math.log(D_i)) * (T - T_i) / (T_j - T_i)
                return math.exp(ln_D)

    def zero_rate(self, T: float) -> float:
        D = self.discount_factor(T)
        return -math.log(D) / T

    def forward_rate(self, T1: float, T2: float) -> float:
        if T1 >= T2:
            raise ValueError(f"T1={T1} must be strictly less than T2={T2}")
        D1 = self.discount_factor(T1)
        D2 = self.discount_factor(T2)
        return -math.log(D2 / D1) / (T2 - T1)
