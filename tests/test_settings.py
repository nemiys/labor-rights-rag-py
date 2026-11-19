"""Defaults that matter once the repository is public."""

from labor_rights_rag.settings import Settings


def test_the_default_user_agent_names_the_project_not_a_person() -> None:
    # Whoever runs a copy of this code would otherwise identify to Wikimedia as the author.
    user_agent = Settings(_env_file=None).http_user_agent

    assert "@" not in user_agent
    assert "github.com/nemiys/labor-rights-rag-py" in user_agent
