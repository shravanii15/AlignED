select gap_id, demand_rate, coverage_rate
from {{ ref('fct_program_skill_gaps') }}
where demand_rate < 0 or demand_rate > 1 or coverage_rate < 0 or coverage_rate > 1
