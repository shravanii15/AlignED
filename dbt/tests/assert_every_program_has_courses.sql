select program_id, program_label from {{ ref('dim_program_summary') }} where course_count = 0
