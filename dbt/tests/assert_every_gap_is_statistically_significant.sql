-- gap_scores is documented to hold only gaps that survived the Benjamini-Hochberg correction (q < 0.05).
select gap_id, q_value from {{ ref('fct_program_skill_gaps') }} where q_value >= 0.05
