"""
Excel-style labeling utility for temporary sections.
Generates labels like A, B, ..., Z, AA, AB, ..., AZ, BA, BB, etc.
"""


def to_label(n: int) -> str:
    """
    Convert a 1-based index to Excel-style column label.
    
    Args:
        n: 1-based index (1 = A, 2 = B, ..., 26 = Z, 27 = AA, etc.)
        
    Returns:
        Excel-style label string
        
    Examples:
        to_label(1) -> "A"
        to_label(26) -> "Z" 
        to_label(27) -> "AA"
        to_label(28) -> "AB"
        to_label(52) -> "AZ"
        to_label(53) -> "BA"
    """
    if n < 1:
        raise ValueError("Index must be >= 1")
    
    result = ""
    while n > 0:
        n -= 1  # Convert to 0-based
        result = chr(ord('A') + (n % 26)) + result
        n //= 26
    
    return result


def test_to_label():
    """Unit tests for to_label function."""
    test_cases = [
        (1, "A"),
        (2, "B"),
        (25, "Y"),
        (26, "Z"),
        (27, "AA"),
        (28, "AB"),
        (51, "AY"),
        (52, "AZ"),
        (53, "BA"),
        (54, "BB"),
        (77, "BY"),
        (78, "BZ"),
        (79, "CA"),
        (702, "ZZ"),
        (703, "AAA"),
        (704, "AAB"),
    ]
    
    for n, expected in test_cases:
        result = to_label(n)
        assert result == expected, f"to_label({n}) = '{result}', expected '{expected}'"
    
    print("All to_label tests passed!")


if __name__ == "__main__":
    test_to_label()
