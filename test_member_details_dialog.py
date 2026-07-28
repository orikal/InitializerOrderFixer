from ui.variables_cell import format_member_details_message


def test_format_member_details_message() -> None:
    message = format_member_details_message(["third", "fourth"], ["first", "second"])
    assert "Not initialized in the constructor" not in message
    assert "  • third" in message
    assert "  • fourth" in message
    assert "  • first" in message
    assert "  • second" in message


if __name__ == "__main__":
    test_format_member_details_message()
    print("All member-details dialog tests passed.")
