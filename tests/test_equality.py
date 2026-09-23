from pythonnative.equality import equal


def test_equal_returns_bool_for_equal_and_unequal_values():
    assert equal(1, 1) is True
    assert equal(1, 2) is False


def test_equal_same_object_does_not_call_eq():
    class ExplodingEq:
        def __eq__(self, other):
            raise AssertionError("__eq__ should not be called")

    value = ExplodingEq()

    assert equal(value, value) is True


def test_equal_returns_false_when_comparison_raises():
    class ExplodingEq:
        def __eq__(self, other):
            raise RuntimeError("comparison failed")

    left = ExplodingEq()
    right = ExplodingEq()

    assert equal(left, right) is False


def test_equal_returns_false_for_nonboolean_comparison_result():
    class ComparisonResult:
        def __bool__(self):
            raise AssertionError("__bool__ should not be called")

    class ReturnsNonBool:
        def __eq__(self, other):
            return ComparisonResult()

    left = ReturnsNonBool()
    right = ReturnsNonBool()

    assert equal(left, right) is False


def test_equal_does_not_treat_truthy_nonbool_as_true():
    class ReturnsOne:
        def __eq__(self, other):
            return 1

    left = ReturnsOne()
    right = ReturnsOne()

    assert equal(left, right) is False


def test_equal_same_mutable_object_after_in_place_mutation():
    value = []

    value.append("changed")

    assert equal(value, value) is True