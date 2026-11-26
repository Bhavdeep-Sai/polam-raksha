# Produce Allocation Engine — PolamRaksha (పొలంరక్ష)

**Algorithm Version:** `cp-sat-v1.0`  
**Solver:** Google OR-Tools CP-SAT (`ortools.sat.python.cp_model`)

---

## 1. Design Principles

- **Pure & Framework-Independent:** `backend/app/modules/allocation/solver.py` has zero dependencies on FastAPI, SQLAlchemy, or frontend code.
- **Integer Arithmetic:** All monetary values are computed in integer **paise**; all quantities are solved in integer **1 kg (`1000 g`)** increments. Any sub-kilogram remainder (`available_quantity_grams % 1000`) is explicitly tracked and reported in `unallocated_quantity_grams` rather than silently rounded away.
- **Net Sales Revenue vs. Profit:** Estimated net sales revenue equals gross sales revenue minus farmer-paid variable and fixed transportation costs. It is never labelled "profit" because farm production costs are excluded.

---

## 2. Mathematical Formulation

### Sets & Parameters
Let $A_{\text{kg}} = \lfloor \text{available\_quantity\_grams} / 1000 \rfloor$ be the available whole kilograms (excluding existing committed inventory).  
Each eligible offer $i \in E$ has:
- Unit price $p_i \ge \text{reserve\_price}$ (paise/kg)
- Minimum acceptable quantity $l_i = \lceil \text{min\_quantity\_grams}_i / 1000 \rceil$ (kg)
- Maximum acceptable quantity $u_i = \min(\lfloor \text{max\_quantity\_grams}_i / 1000 \rfloor, A_{\text{kg}})$ (kg)
- Farmer-paid variable transport cost $v_i$ (paise/kg)
- Farmer-paid fixed pickup cost $f_i$ (paise, incurred only if buyer $i$ is selected)
- Collection feasibility: $\text{estimated\_collection\_at}_i \le \text{hard\_collection\_deadline}$
- Reliability eligibility: $\text{reliability\_score}_i \ge \text{min\_reliability\_score}$

### Decision Variables
- $y_i \in \{0, 1\}$: 1 if buyer $i$ is selected, 0 otherwise.
- $q_i \in \mathbb{Z}_{\ge 0}$: whole kilograms allocated to buyer $i$.

### Constraints
1. **Linking & MOQ/Cap:** $l_i \cdot y_i \le q_i \le u_i \cdot y_i \quad \forall i \in E$
2. **Available Inventory Cap:** $\sum_{i \in E} q_i \le A_{\text{kg}}$
3. **Minimum Net Revenue (optional):**
   $$\text{NetRev} = \sum_{i \in E} \left( (p_i - v_i) q_i - f_i y_i \right) \ge \text{min\_net\_revenue\_paise}$$

### Lexicographic Objectives
- **Revenue-First (`REVENUE_FIRST`):**
  1. Maximize $\text{NetRev}$
  2. Maximize $\sum_{i \in E} q_i$ (with $\text{NetRev}$ pinned)
  3. Maximize $\sum_{i \in E} \text{reliability\_score}_i \cdot q_i$ (deterministic tie-breaker)
- **Rescue-First (`RESCUE_FIRST`):**
  1. Maximize $\sum_{i \in E} q_i$
  2. Maximize $\text{NetRev}$ (with $\sum q_i$ pinned)
  3. Maximize $\sum_{i \in E} \text{reliability\_score}_i \cdot q_i$ (deterministic tie-breaker)

---

## 3. Solver Status, Fallback & Limitations

- **Status Honesty:** `OPTIMAL` is returned only when all lexicographic phases prove optimality; `FEASIBLE` is returned if a time limit is hit after finding a valid solution; `INFEASIBLE` when no valid solution exists.
- **Deterministic Greedy Fallback:** Used only when CP-SAT returns `UNKNOWN` within the configured time limit; clearly flagged with `used_fallback=True` and never violates constraints.
- **Approval & Stale-Inventory Revalidation:** `AllocationRun` stores `input_snapshot_json`, `algorithm_version`, and `explanations_json`. Before committing `Order`s, `approve_allocation_run` locks the listing and revalidates that `available_quantity_grams >= total_allocated_grams` and the collection deadline has not passed.
- **Limitations:** MVP granularity is `1 kg`; sub-kilogram lots (`< 1000 g`) cannot be allocated by the solver.

