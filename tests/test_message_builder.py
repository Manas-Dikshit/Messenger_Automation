from datetime import date

from birthday_sms.message_builder import MessageBuilder
from birthday_sms.models import Contact


def make_contact(**overrides) -> Contact:
    defaults = dict(
        name="Rahul Sharma",
        phone_number="+919876543210",
        birthday=date(1999, 5, 16),
        classification="Student",
        brief="Class 10 - Section B",
    )
    defaults.update(overrides)
    return Contact(**defaults)


class TestMessageBuilder:
    def test_substitutes_all_known_placeholders(self):
        builder = MessageBuilder()
        contact = make_contact()
        template = (
            "Hi {FIRST_NAME} ({NAME}), happy {AGE}th birthday on {TODAY} in "
            "{YEAR}! Group: {CLASSIFICATION} - {BRIEF}"
        )

        result = builder.render(template, contact, today=date(2026, 5, 16))

        assert "Rahul" in result
        assert "Rahul Sharma" in result
        assert "27th birthday" in result
        assert "2026-05-16" in result
        assert "2026" in result
        assert "Student" in result
        assert "Class 10 - Section B" in result

    def test_leaves_unknown_placeholders_untouched(self):
        builder = MessageBuilder()
        contact = make_contact()
        result = builder.render("Hello {NAEM}!", contact, today=date(2026, 5, 16))
        assert result == "Hello {NAEM}!"

    def test_first_name_extraction(self):
        contact = make_contact(name="Ananya Verma")
        assert contact.first_name == "Ananya"

    def test_age_turning(self):
        contact = make_contact(birthday=date(1999, 5, 16))
        assert contact.age_turning(date(2026, 5, 16)) == 27
