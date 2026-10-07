select
    recommendation_id,
    program_id,
    skill_id,
    cluster_id,
    cast(gap_value as double) as gap_value,
    trend_label,
    cast(priority_score as double) as priority_score,
    priority_tier
from {{ source('aligned', 'recommendations') }}
