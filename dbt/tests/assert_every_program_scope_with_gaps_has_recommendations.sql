-- Recommendations are capped per program and scope, so not every gap is listed. What must hold is that a
-- program/scope with any significant gap is never left with zero recommendations, or a student would see nothing.
select program_label, scope, count(*) as gaps, count(priority_tier) as recommended
from {{ ref('fct_program_skill_gaps') }}
group by program_label, scope
having count(priority_tier) = 0
