select
    program_id,
    university,
    program_name,
    tier,
    university || ' · ' || program_name as program_label
from {{ source('aligned', 'programs') }}
