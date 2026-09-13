from app.models import Article50Rule

ARTICLE_50_1_AI_INTERACTION_DISCLOSURE = "ARTICLE_50_1_AI_INTERACTION_DISCLOSURE"

ARTICLE50_RULES: dict[str, Article50Rule] = {
    ARTICLE_50_1_AI_INTERACTION_DISCLOSURE: Article50Rule(
        id=ARTICLE_50_1_AI_INTERACTION_DISCLOSURE,
        title="AI interaction transparency disclosure",
        description=(
            "Assess whether a person directly interacting with an AI system is clearly informed "
            "that AI is involved in the interaction."
        ),
        source_url="https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
        source_reference="Regulation (EU) 2024/1689, Article 50(1)",
    )
}

PRIMARY_ARTICLE50_RULE = ARTICLE50_RULES[ARTICLE_50_1_AI_INTERACTION_DISCLOSURE]
