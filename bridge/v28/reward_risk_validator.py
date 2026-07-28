"""Net account-currency reward/risk including all governed costs."""
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class RewardRisk:
    gross_reward_per_volume: float; gross_risk_per_volume: float; total_cost_per_volume: float
    net_expected_reward_per_volume: float; net_expected_risk_per_volume: float
    net_reward_risk_ratio: float; execution_viability: str; reasons: tuple[str,...]

def calculate_reward_risk(*,entry,stop,target,spec,quote,constraints):
    d=lambda v: Decimal(str(v)); tick=d(spec.tick_size); tick_value=d(spec.tick_value_per_volume)
    risk_ticks=abs(d(entry)-d(stop))/tick; reward_ticks=abs(d(target)-d(entry))/tick
    spread_ticks=(d(quote.ask)-d(quote.bid))/tick
    spread_cost=spread_ticks*tick_value
    quote_slippage_cost=(d(quote.maximum_slippage_price)/tick)*tick_value
    costs=(spread_cost+quote_slippage_cost+d(constraints.commission_account_currency_per_volume)+
           d(constraints.slippage_account_currency_per_volume)+d(constraints.other_cost_account_currency_per_volume))
    costs=float(costs); gross_risk=float(risk_ticks*tick_value); gross_reward=float(reward_ticks*tick_value)
    net_risk=gross_risk+costs; net_reward=gross_reward-costs; ratio=net_reward/net_risk if net_risk>0 else 0
    valid=net_reward>0 and ratio>=constraints.minimum_net_reward_risk_ratio
    return RewardRisk(gross_reward,gross_risk,costs,net_reward,net_risk,ratio,"VALID" if valid else "INVALID",("REWARD_RISK_VALID",) if valid else ("MINIMUM_NET_REWARD_RISK_FAILED",))
