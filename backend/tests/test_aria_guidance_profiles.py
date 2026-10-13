from aria_guidance_profiles import CONCISE, SUPPORTIVE, normalize_guidance_profile, render_guidance_profile


def test_missing_unknown_and_none_default_to_supportive():
    assert normalize_guidance_profile(None) == SUPPORTIVE
    assert normalize_guidance_profile("") == SUPPORTIVE
    assert normalize_guidance_profile("invented") == SUPPORTIVE


def test_profiles_are_explicit_mutually_exclusive_and_preserve_global_rules():
    supportive = render_guidance_profile(SUPPORTIVE)
    concise = render_guidance_profile(CONCISE)
    assert "PROFILE: supportive_guided" in supportive and "PROFILE: concise_natural" not in supportive
    assert "PROFILE: concise_natural" in concise and "PROFILE: supportive_guided" not in concise
    assert "never childish" in supportive and "clear goodbye" in supportive
    assert "recently you spoke" in concise and "lingering offers" in concise
    for prompt in (supportive, concise):
        assert "never overrides safety" in prompt
        assert "truth/tool grounding" in prompt
        assert "end-call rules" in prompt
