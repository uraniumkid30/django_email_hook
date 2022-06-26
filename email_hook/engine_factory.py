from email_hook.engine import (
    EmailEngine,
    DjangoEmailEngine,
    PostmarkEmailEngine,
    AWSSESEmailEngine,
)


def email_engine_factory(engine_name: str) -> EmailEngine:
    email_engine_factory = {
        "DJANGO": DjangoEmailEngine,
        "POSTMARK": PostmarkEmailEngine,
        "AWSSES": AWSSESEmailEngine,
    }
    if email_engine_factory.get(engine_name):
        return email_engine_factory.get(engine_name)
    raise f"Invalid Email engine name {engine_name}, choose from {list(email_engine_factory.keys())}"
