from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from ortools.sat.python import cp_model

QUANTITY_GRANULARITY_GRAMS = 1000
ALGORITHM_VERSION = "cp-sat-v1.0"


class AllocationStrategy(StrEnum):
    REVENUE_FIRST = "REVENUE_FIRST"
    RESCUE_FIRST = "RESCUE_FIRST"


class SolverStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class BuyerOfferInput:
    buyer_id: str
    unit_price_paise_per_kg: int
    min_quantity_grams: int
    max_quantity_grams: int
    estimated_collection_at: datetime
    farmer_paid_variable_transport_paise_per_kg: int = 0
    farmer_paid_fixed_pickup_cost_paise: int = 0
    reliability_score: int = 100
    is_eligible: bool = True


@dataclass(frozen=True)
class AllocationInput:
    available_quantity_grams: int
    committed_quantity_grams: int
    reserve_price_paise_per_kg: int
    hard_collection_deadline: datetime
    strategy: AllocationStrategy = AllocationStrategy.REVENUE_FIRST
    min_net_revenue_paise: int = 0
    min_reliability_score: int = 20
    time_limit_seconds: float = 2.0
    offers: list[BuyerOfferInput] = field(default_factory=list)


@dataclass(frozen=True)
class SelectedBuyerAllocation:
    buyer_id: str
    allocated_quantity_grams: int
    unit_price_paise_per_kg: int
    gross_revenue_paise: int
    transportation_cost_paise: int
    net_revenue_paise: int
    reliability_score: int


@dataclass(frozen=True)
class AllocationOutput:
    selected_buyers: list[SelectedBuyerAllocation]
    total_allocated_grams: int
    gross_revenue_paise: int
    transportation_cost_paise: int
    estimated_net_revenue_paise: int
    unallocated_quantity_grams: int
    collection_feasible: bool
    solver_status: SolverStatus
    used_fallback: bool
    execution_time_ms: int
    algorithm_version: str
    explanations: list[str]


@dataclass(frozen=True)
class _PreparedOffer:
    offer: BuyerOfferInput
    min_kg: int
    max_kg: int
    net_paise_per_kg: int


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _filter_offers(inp: AllocationInput) -> tuple[list[_PreparedOffer], list[str], int]:
    available_kg = max(0, inp.available_quantity_grams // QUANTITY_GRANULARITY_GRAMS)
    deadline_utc = _ensure_utc(inp.hard_collection_deadline)
    prepared: list[_PreparedOffer] = []
    explanations: list[str] = []

    if inp.committed_quantity_grams > 0:
        explanations.append(
            f"Preserved {inp.committed_quantity_grams}g of existing committed inventory."
        )

    remainder_grams = max(0, inp.available_quantity_grams % QUANTITY_GRANULARITY_GRAMS)
    if remainder_grams > 0:
        explanations.append(
            f"Solver operates in {QUANTITY_GRANULARITY_GRAMS}g (1 kg) increments; "
            f"{remainder_grams}g remainder stays explicitly unallocated."
        )

    # Sort deterministically by buyer_id before indexing
    for offer in sorted(inp.offers, key=lambda o: o.buyer_id):
        if not offer.is_eligible:
            explanations.append(f"Excluded {offer.buyer_id}: offer marked ineligible/cancelled.")
            continue
        if offer.unit_price_paise_per_kg < inp.reserve_price_paise_per_kg:
            explanations.append(
                f"Excluded {offer.buyer_id}: price {offer.unit_price_paise_per_kg} paise/kg "
                f"below reserve {inp.reserve_price_paise_per_kg} paise/kg."
            )
            continue
        if _ensure_utc(offer.estimated_collection_at) > deadline_utc:
            explanations.append(
                f"Excluded {offer.buyer_id}: collection time exceeds hard deadline."
            )
            continue
        if offer.reliability_score < inp.min_reliability_score:
            explanations.append(
                f"Excluded {offer.buyer_id}: reliability score {offer.reliability_score} "
                f"below minimum {inp.min_reliability_score}."
            )
            continue

        min_kg = (
            offer.min_quantity_grams + QUANTITY_GRANULARITY_GRAMS - 1
        ) // QUANTITY_GRANULARITY_GRAMS
        max_kg = min(offer.max_quantity_grams // QUANTITY_GRANULARITY_GRAMS, available_kg)
        if min_kg <= 0:
            min_kg = 1
        if max_kg < min_kg:
            explanations.append(
                f"Excluded {offer.buyer_id}: minimum {min_kg} kg exceeds feasible cap {max_kg} kg."
            )
            continue

        net_per_kg = (
            offer.unit_price_paise_per_kg - offer.farmer_paid_variable_transport_paise_per_kg
        )
        prepared.append(
            _PreparedOffer(
                offer=offer,
                min_kg=min_kg,
                max_kg=max_kg,
                net_paise_per_kg=net_per_kg,
            )
        )

    return prepared, explanations, available_kg


def _build_base_model(
    prepared: list[_PreparedOffer],
    available_kg: int,
    min_net_revenue_paise: int,
) -> tuple[
    cp_model.CpModel,
    list[cp_model.IntVar],
    list[cp_model.IntVar],
    cp_model.LinearExpr,
    cp_model.LinearExpr,
    cp_model.LinearExpr,
    cp_model.LinearExpr,
]:
    model = cp_model.CpModel()
    y_vars: list[cp_model.IntVar] = []
    q_vars: list[cp_model.IntVar] = []

    for idx, item in enumerate(prepared):
        y = model.new_bool_var(f"y_{idx}")
        q = model.new_int_var(0, item.max_kg, f"q_{idx}")
        model.add(q >= item.min_kg * y)
        model.add(q <= item.max_kg * y)
        y_vars.append(y)
        q_vars.append(q)

    total_kg = cp_model.LinearExpr.sum(q_vars)
    model.add(total_kg <= available_kg)

    gross_rev = cp_model.LinearExpr.sum([
        q_vars[i] * prepared[i].offer.unit_price_paise_per_kg for i in range(len(prepared))
    ])
    transport_cost = cp_model.LinearExpr.sum([
        q_vars[i] * prepared[i].offer.farmer_paid_variable_transport_paise_per_kg
        + y_vars[i] * prepared[i].offer.farmer_paid_fixed_pickup_cost_paise
        for i in range(len(prepared))
    ])
    net_rev = gross_rev - transport_cost
    if min_net_revenue_paise > 0:
        model.add(net_rev >= min_net_revenue_paise)

    tie_break = cp_model.LinearExpr.sum([
        q_vars[i] * prepared[i].offer.reliability_score for i in range(len(prepared))
    ])
    return model, y_vars, q_vars, total_kg, gross_rev, net_rev, tie_break


def _greedy_fallback(
    inp: AllocationInput,
    prepared: list[_PreparedOffer],
    explanations: list[str],
    available_kg: int,
    start_ns: int,
) -> AllocationOutput:
    """Deterministic greedy fallback used only when CP-SAT returns UNKNOWN."""
    if inp.strategy == AllocationStrategy.REVENUE_FIRST:
        ordered = sorted(
            prepared,
            key=lambda p: (
                -p.net_paise_per_kg,
                -p.offer.reliability_score,
                p.offer.buyer_id,
            ),
        )
    else:
        ordered = sorted(
            prepared,
            key=lambda p: (
                -p.max_kg,
                -p.net_paise_per_kg,
                -p.offer.reliability_score,
                p.offer.buyer_id,
            ),
        )

    remaining_kg = available_kg
    selected: list[SelectedBuyerAllocation] = []
    gross_rev = 0
    transport_cost = 0

    for item in ordered:
        if remaining_kg < item.min_kg:
            continue
        alloc_kg = min(item.max_kg, remaining_kg)
        item_gross = alloc_kg * item.offer.unit_price_paise_per_kg
        item_transport = (
            alloc_kg * item.offer.farmer_paid_variable_transport_paise_per_kg
            + item.offer.farmer_paid_fixed_pickup_cost_paise
        )
        item_net = item_gross - item_transport
        if inp.strategy == AllocationStrategy.REVENUE_FIRST and item_net <= 0:
            continue
        selected.append(
            SelectedBuyerAllocation(
                buyer_id=item.offer.buyer_id,
                allocated_quantity_grams=alloc_kg * QUANTITY_GRANULARITY_GRAMS,
                unit_price_paise_per_kg=item.offer.unit_price_paise_per_kg,
                gross_revenue_paise=item_gross,
                transportation_cost_paise=item_transport,
                net_revenue_paise=item_net,
                reliability_score=item.offer.reliability_score,
            )
        )
        remaining_kg -= alloc_kg
        gross_rev += item_gross
        transport_cost += item_transport

    net_rev = gross_rev - transport_cost
    elapsed_ms = max(1, (time.perf_counter_ns() - start_ns) // 1_000_000)

    if not selected or net_rev < inp.min_net_revenue_paise:
        return AllocationOutput(
            selected_buyers=[],
            total_allocated_grams=0,
            gross_revenue_paise=0,
            transportation_cost_paise=0,
            estimated_net_revenue_paise=0,
            unallocated_quantity_grams=inp.available_quantity_grams,
            collection_feasible=False,
            solver_status=SolverStatus.UNKNOWN,
            used_fallback=True,
            execution_time_ms=elapsed_ms,
            algorithm_version=ALGORITHM_VERSION,
            explanations=[*explanations, "Greedy fallback found no qualifying allocation."],
        )

    total_grams = sum(s.allocated_quantity_grams for s in selected)
    return AllocationOutput(
        selected_buyers=selected,
        total_allocated_grams=total_grams,
        gross_revenue_paise=gross_rev,
        transportation_cost_paise=transport_cost,
        estimated_net_revenue_paise=net_rev,
        unallocated_quantity_grams=inp.available_quantity_grams - total_grams,
        collection_feasible=True,
        solver_status=SolverStatus.FEASIBLE,
        used_fallback=True,
        execution_time_ms=elapsed_ms,
        algorithm_version=ALGORITHM_VERSION,
        explanations=[
            *explanations,
            "CP-SAT reached time limit with no solution; used deterministic greedy fallback.",
        ],
    )


def solve_allocation(inp: AllocationInput) -> AllocationOutput:
    """Solve constrained produce allocation using lexicographic OR-Tools CP-SAT."""
    start_ns = time.perf_counter_ns()
    prepared, explanations, available_kg = _filter_offers(inp)

    if available_kg <= 0 or not prepared:
        elapsed_ms = max(0, (time.perf_counter_ns() - start_ns) // 1_000_000)
        return AllocationOutput(
            selected_buyers=[],
            total_allocated_grams=0,
            gross_revenue_paise=0,
            transportation_cost_paise=0,
            estimated_net_revenue_paise=0,
            unallocated_quantity_grams=max(0, inp.available_quantity_grams),
            collection_feasible=False,
            solver_status=SolverStatus.INFEASIBLE,
            used_fallback=False,
            execution_time_ms=elapsed_ms,
            algorithm_version=ALGORITHM_VERSION,
            explanations=[
                *explanations,
                "No eligible buyer offers or available whole-kg inventory.",
            ],
        )

    time_limit = max(0.01, inp.time_limit_seconds)
    per_phase_limit = time_limit / 3.0

    model, y_vars, q_vars, total_kg, gross_rev, net_rev, tie_break = _build_base_model(
        prepared, available_kg, inp.min_net_revenue_paise
    )
    primary_expr = net_rev if inp.strategy == AllocationStrategy.REVENUE_FIRST else total_kg
    secondary_expr = total_kg if inp.strategy == AllocationStrategy.REVENUE_FIRST else net_rev

    # Phase 1: Primary objective
    model.maximize(primary_expr)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = per_phase_limit
    solver.parameters.num_search_workers = 1
    status_1 = solver.solve(model)

    if status_1 == cp_model.INFEASIBLE:
        elapsed_ms = max(0, (time.perf_counter_ns() - start_ns) // 1_000_000)
        return AllocationOutput(
            selected_buyers=[],
            total_allocated_grams=0,
            gross_revenue_paise=0,
            transportation_cost_paise=0,
            estimated_net_revenue_paise=0,
            unallocated_quantity_grams=inp.available_quantity_grams,
            collection_feasible=False,
            solver_status=SolverStatus.INFEASIBLE,
            used_fallback=False,
            execution_time_ms=elapsed_ms,
            algorithm_version=ALGORITHM_VERSION,
            explanations=[*explanations, "CP-SAT proved no feasible allocation exists."],
        )

    if status_1 == cp_model.UNKNOWN:
        return _greedy_fallback(inp, prepared, explanations, available_kg, start_ns)

    best_primary = int(solver.value(primary_expr))
    all_optimal = status_1 == cp_model.OPTIMAL

    # Phase 2: Secondary objective with primary pinned
    model.add(primary_expr == best_primary)
    model.maximize(secondary_expr)
    solver.parameters.max_time_in_seconds = per_phase_limit
    status_2 = solver.solve(model)

    if status_2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        best_secondary = int(solver.value(secondary_expr))
        all_optimal = all_optimal and (status_2 == cp_model.OPTIMAL)

        # Phase 3: Deterministic reliability tie-breaker with secondary pinned
        model.add(secondary_expr == best_secondary)
        model.maximize(tie_break)
        solver.parameters.max_time_in_seconds = per_phase_limit
        status_3 = solver.solve(model)
        all_optimal = all_optimal and (status_3 == cp_model.OPTIMAL)
        final_solver = solver if status_3 in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    else:
        all_optimal = False
        final_solver = None

    if final_solver is None:
        # Re-solve Phase 1 to recover guaranteed valid values if Phase 2/3 timed out.
        m_rec, _, q_rec, _, _, _, _ = _build_base_model(
            prepared, available_kg, inp.min_net_revenue_paise
        )
        p_rec = (
            sum(
                q_rec[i] * prepared[i].offer.unit_price_paise_per_kg
                - q_rec[i] * prepared[i].offer.farmer_paid_variable_transport_paise_per_kg
                for i in range(len(prepared))
            )
            if inp.strategy == AllocationStrategy.REVENUE_FIRST
            else sum(q_rec)
        )
        m_rec.maximize(p_rec)
        rec_solver = cp_model.CpSolver()
        rec_solver.parameters.max_time_in_seconds = per_phase_limit
        rec_solver.parameters.num_search_workers = 1
        rec_status = rec_solver.solve(m_rec)
        if rec_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return _greedy_fallback(inp, prepared, explanations, available_kg, start_ns)
        q_vals = [int(rec_solver.value(q_rec[i])) for i in range(len(prepared))]
        all_optimal = False
    else:
        q_vals = [int(final_solver.value(q_vars[i])) for i in range(len(prepared))]

    selected: list[SelectedBuyerAllocation] = []
    total_gross = 0
    total_transport = 0
    total_grams = 0

    for i, alloc_kg in enumerate(q_vals):
        if alloc_kg <= 0:
            continue
        item = prepared[i]
        item_gross = alloc_kg * item.offer.unit_price_paise_per_kg
        item_transport = (
            alloc_kg * item.offer.farmer_paid_variable_transport_paise_per_kg
            + item.offer.farmer_paid_fixed_pickup_cost_paise
        )
        item_net = item_gross - item_transport
        selected.append(
            SelectedBuyerAllocation(
                buyer_id=item.offer.buyer_id,
                allocated_quantity_grams=alloc_kg * QUANTITY_GRANULARITY_GRAMS,
                unit_price_paise_per_kg=item.offer.unit_price_paise_per_kg,
                gross_revenue_paise=item_gross,
                transportation_cost_paise=item_transport,
                net_revenue_paise=item_net,
                reliability_score=item.offer.reliability_score,
            )
        )
        total_gross += item_gross
        total_transport += item_transport
        total_grams += alloc_kg * QUANTITY_GRANULARITY_GRAMS
        explanations.append(
            f"Selected {item.offer.buyer_id}: {alloc_kg} kg @ "
            f"{item.offer.unit_price_paise_per_kg} paise/kg "
            f"(transport {item_transport} paise, net {item_net} paise)."
        )

    final_status = SolverStatus.OPTIMAL if all_optimal else SolverStatus.FEASIBLE
    elapsed_ms = max(0, (time.perf_counter_ns() - start_ns) // 1_000_000)

    return AllocationOutput(
        selected_buyers=selected,
        total_allocated_grams=total_grams,
        gross_revenue_paise=total_gross,
        transportation_cost_paise=total_transport,
        estimated_net_revenue_paise=total_gross - total_transport,
        unallocated_quantity_grams=inp.available_quantity_grams - total_grams,
        collection_feasible=len(selected) > 0,
        solver_status=final_status,
        used_fallback=False,
        execution_time_ms=elapsed_ms,
        algorithm_version=ALGORITHM_VERSION,
        explanations=explanations,
    )
