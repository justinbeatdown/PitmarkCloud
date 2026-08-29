from services.autopilot_ai import _extract_output_text, SYSTEM_PROMPT

sample={"output":[{"content":[{"type":"output_text","text":"Friday night lights, dirt in the air, and race cars rolling out. What track are you at this weekend? 🏁"}]}]}
assert _extract_output_text(sample).startswith('Friday night lights')
assert 'Return ONLY finished post copy' in SYSTEM_PROMPT
assert 'Do not invent race results' in SYSTEM_PROMPT
print('autopilot AI smoke test passed')
