-- One row per significant gap, with names, evidence strength and the recommendation attached.
select
    g.gap_id,
    g.program_id,
    p.program_label,
    g.skill_id,
    s.skill_name,
    g.cluster_id,
    coalesce(c.role_label, 'overall market') as scope,
    g.is_overall_scope,
    g.demand_rate,
    g.coverage_rate,
    g.gap_value,
    g.q_value,
    g.test_method,
    case
        when g.q_value < 0.001 then 'very strong'
        when g.q_value < 0.01 then 'strong'
        else 'moderate'
    end as evidence_strength,
    r.priority_tier,
    r.priority_score,
    r.trend_label
from {{ ref('stg_gap_scores') }} g
join {{ ref('stg_programs') }} p using (program_id)
join {{ ref('stg_skills') }} s using (skill_id)
left join {{ ref('stg_role_clusters') }} c using (cluster_id)
left join {{ ref('stg_recommendations') }} r
    on r.program_id = g.program_id
   and r.skill_id = g.skill_id
   and r.cluster_id is not distinct from g.cluster_id
