-- One row per significant (program, skill, scope) gap. A null cluster_id means "overall market".
select
    gap_id,
    program_id,
    skill_id,
    cluster_id,
    cluster_id is null as is_overall_scope,
    cast(program_coverage_rate as double) as coverage_rate,
    cast(market_demand_rate as double) as demand_rate,
    cast(gap_value as double) as gap_value,
    cast(p_value as double) as p_value,
    cast(q_value as double) as q_value,
    test_method
from {{ source('aligned', 'gap_scores') }}
