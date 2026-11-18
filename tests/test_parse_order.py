"""Tests for reorder_boxes_by_stream: layout boxes re-sorted by the PDF's own text order.

Boxes are simple stand-ins with x0, y0, x1, y1 and a name. Words are (x0, y0, x1, y1, text)
tuples in PDF stream order, like page.get_text("words").
"""

from dataclasses import dataclass

from rag.parse import reorder_boxes_by_stream


@dataclass
class Box:
    name: str
    x0: float
    y0: float
    x1: float
    y1: float


def word(text: str, x: float, y: float) -> tuple:
    return (x, y, x + 10, y + 10, text)


def names(boxes: list[Box]) -> list[str]:
    return [b.name for b in boxes]


def test_labels_hoisted_by_the_model_go_back_above_their_own_column():
    # Equinor p8 shape: the model lists Q1..Q4 first, then the column bodies.
    labels = [Box(f"Q{i}", 100 * i, 10, 100 * i + 40, 30) for i in range(1, 5)]
    bodies = [Box(f"body{i}", 100 * i, 50, 100 * i + 80, 200) for i in range(1, 5)]
    model_order = labels + bodies
    # The PDF stream is Q1, body1, Q2, body2, ...
    words = []
    for i in range(1, 5):
        words.append(word(f"Q{i}", 100 * i + 5, 15))
        words.append(word(f"text{i}", 100 * i + 5, 60))
    assert names(reorder_boxes_by_stream(model_order, words)) == [
        "Q1", "body1", "Q2", "body2", "Q3", "body3", "Q4", "body4",
    ]


def test_order_already_matching_the_stream_is_unchanged():
    boxes = [Box("a", 0, 0, 100, 20), Box("b", 0, 30, 100, 50), Box("c", 0, 60, 100, 80)]
    words = [word("a", 5, 5), word("b", 5, 35), word("c", 5, 65)]
    assert names(reorder_boxes_by_stream(boxes, words)) == ["a", "b", "c"]


def test_picture_without_words_stays_after_the_box_before_it():
    boxes = [Box("right", 500, 0, 600, 100), Box("pic", 0, 0, 100, 100), Box("left", 200, 0, 300, 100)]
    # Stream: left text first, then right text. The picture has no words of its own.
    words = [word("l", 205, 5), word("r", 505, 5)]
    # right (key 1), pic inherits right's key, left (key 0) -> left first, then right, pic.
    assert names(reorder_boxes_by_stream(boxes, words)) == ["left", "right", "pic"]


def test_big_box_does_not_steal_words_from_boxes_inside_it():
    # A picture covers the page; the text box inside it owns the word, not the picture.
    boxes = [Box("big", 0, 0, 1000, 1000), Box("inner", 100, 100, 200, 200), Box("later", 300, 300, 400, 400)]
    words = [word("x", 120, 120), word("y", 320, 320)]
    # big has no words of its own -> inherits the key of the box before it (none): key -1, so first.
    assert names(reorder_boxes_by_stream(boxes, words)) == ["big", "inner", "later"]


def test_ties_keep_the_model_order():
    # Two boxes holding words of the same index cannot happen, but boxes without words tie.
    boxes = [Box("a", 0, 0, 10, 10), Box("p1", 50, 50, 60, 60), Box("p2", 70, 70, 80, 80)]
    words = [word("a", 2, 2)]
    assert names(reorder_boxes_by_stream(boxes, words)) == ["a", "p1", "p2"]


def test_words_outside_every_box_are_ignored():
    boxes = [Box("only", 0, 0, 10, 10)]
    assert names(reorder_boxes_by_stream(boxes, [word("lost", 500, 500)])) == ["only"]
