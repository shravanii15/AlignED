select gap_id, demand_rate, coverage_rate, gap_value
from {{ ref('fct_program_skill_gaps') }}
where abs(gap_value - (demand_rate - coverage_rate)) > 1e-6
