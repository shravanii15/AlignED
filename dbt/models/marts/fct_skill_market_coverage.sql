-- One row per skill (overall market): how much employers want it, how little programs teach it, and how widespread the gap is.
select
    skill_id,
    skill_name,
    round(avg(demand_rate), 4) as avg_demand_rate,
    round(avg(coverage_rate), 4) as avg_coverage_rate,
    round(avg(gap_value), 4) as avg_gap_value,
    count(distinct program_id) as programs_with_gap,
    (select count(*) from {{ ref('stg_programs') }}) as total_programs,
    round(count(distinct program_id) * 1.0 / (select count(*) from {{ ref('stg_programs') }}), 3) as share_of_programs_with_gap
from {{ ref('fct_program_skill_gaps') }}
where is_overall_scope
group by skill_id, skill_name
