-- One row per program: size, how many significant gaps it has in the overall market, and its biggest one.
with overall as (
    select * from {{ ref('fct_program_skill_gaps') }} where is_overall_scope
),
ranked as (
    select program_id, skill_name, gap_value,
           row_number() over (partition by program_id order by gap_value desc, skill_name) as rn
    from overall
),
courses as (
    select program_id, count(*) as course_count from {{ ref('stg_courses') }} group by program_id
)
select
    p.program_id,
    p.program_label,
    p.tier,
    coalesce(c.course_count, 0) as course_count,
    count(o.gap_id) as significant_gap_count,
    count(*) filter (where o.priority_tier = 'high') as high_priority_gap_count,
    round(avg(o.gap_value), 4) as avg_gap_value,
    max(r.skill_name) as biggest_gap_skill
from {{ ref('stg_programs') }} p
left join courses c using (program_id)
left join overall o using (program_id)
left join ranked r on r.program_id = p.program_id and r.rn = 1
group by p.program_id, p.program_label, p.tier, c.course_count
