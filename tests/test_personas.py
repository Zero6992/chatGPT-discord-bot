from src.personas import PERSONAS, get_available_personas, get_persona_prompt, is_jailbreak_persona


class TestPersonas:
    def test_standard_persona_exists(self):
        assert "standard" in PERSONAS
        assert PERSONAS["standard"] == "You are a helpful assistant."

    def test_jailbreak_personas_exist(self):
        jailbreak_personas = ["jailbreak-v1", "jailbreak-v2", "jailbreak-v3"]
        for persona in jailbreak_personas:
            assert persona in PERSONAS
            assert len(PERSONAS[persona]) > 100  # Jailbreaks are typically long

    def test_other_personas_exist(self):
        other_personas = ["creative", "technical", "casual"]
        for persona in other_personas:
            assert persona in PERSONAS
            assert isinstance(PERSONAS[persona], str)

    def test_get_persona_prompt(self):
        # Test existing persona
        prompt = get_persona_prompt("creative")
        assert prompt == PERSONAS["creative"]

        # Test non-existing persona (should return standard)
        prompt = get_persona_prompt("non-existing")
        assert prompt == PERSONAS["standard"]

    def test_get_available_personas(self):
        # Test without user_id (should exclude jailbreak for non-admin)
        personas = get_available_personas()
        assert isinstance(personas, list)
        assert "standard" in personas
        assert "creative" in personas
        # jailbreak personas should be excluded for non-admin users
        jailbreak_personas = [p for p in personas if p.startswith("jailbreak")]
        assert len(jailbreak_personas) == 0

        personas_admin = get_available_personas("123456789", admin_ids={"123456789"})
        assert "jailbreak-v1" in personas_admin
        assert "jailbreak-v1" not in get_available_personas("unrelated", admin_ids={"123456789"})

    def test_is_jailbreak_persona(self):
        # Test jailbreak personas
        assert is_jailbreak_persona("jailbreak-v1") is True
        assert is_jailbreak_persona("jailbreak-v2") is True
        assert is_jailbreak_persona("jailbreak-v3") is True

        # Test non-jailbreak personas
        assert is_jailbreak_persona("standard") is False
        assert is_jailbreak_persona("creative") is False
        assert is_jailbreak_persona("technical") is False
        assert is_jailbreak_persona("casual") is False

        # Test edge cases
        assert is_jailbreak_persona("jailbreak") is True
        assert is_jailbreak_persona("not-jailbreak") is False

    def test_jailbreak_content(self):
        # Verify jailbreak prompts contain expected patterns
        jailbreak_v1 = PERSONAS["jailbreak-v1"]
        assert "BYPASS" in jailbreak_v1
        assert "restrictions" in jailbreak_v1.lower()

        jailbreak_v2 = PERSONAS["jailbreak-v2"]
        assert "SAM" in jailbreak_v2
        assert "uncensored" in jailbreak_v2.lower()

        jailbreak_v3 = PERSONAS["jailbreak-v3"]
        assert "Developer Mode Plus" in jailbreak_v3
        assert "safety guidelines" in jailbreak_v3.lower()

    def test_persona_prompt_structure(self):
        # Ensure all personas have proper structure
        for prompt in PERSONAS.values():
            assert isinstance(prompt, str)
            assert len(prompt) > 0
            assert not prompt.startswith(" ")  # No leading spaces
            assert not prompt.endswith(" ")  # No trailing spaces
