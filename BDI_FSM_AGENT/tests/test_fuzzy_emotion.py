from bdi_fsm.fuzzy import (FuzzySpace, FuzzySet, gaussian, keyword_membership,
                           trapezoid, clamp)
from bdi_fsm.emotion import (EmotionColor, continuity, emotion_of, hue_distance,
                             is_continuous)


# --- fuzzy sets -------------------------------------------------------------

def test_trapezoid_membership():
    mu = trapezoid(0, 2, 3, 5)
    assert mu(0) == 0.0 and mu(5) == 0.0
    assert mu(2.5) == 1.0  # plateau
    assert 0.0 < mu(1) < 1.0  # rising edge is a gradient, not a cliff


def test_gaussian_peaks_at_center():
    mu = gaussian(10, 1.0)
    assert mu(10) == 1.0
    assert mu(20) < 0.1


def test_keyword_membership_partial_credit():
    mu = keyword_membership(["help", "please", "fix"])
    assert mu("please help me fix this") == 1.0
    assert mu("please help me") == 2 / 3
    assert mu("goodbye") == 0.0


def test_probability_cloud():
    space = (FuzzySpace()
             .add("help", keyword_membership(["help", "please"]))
             .add("hostility", keyword_membership(["hate", "attack"]))
             .add("sarcasm", keyword_membership(["obviously", "sure"])))
    cloud = space.grade("please help me, obviously")
    assert cloud["help"] == 1.0
    assert 0.0 < cloud["sarcasm"] < 1.0
    assert cloud["hostility"] == 0.0
    assert space.best("please help me") == "help"


# --- emotional fiber bundle ---------------------------------------------------

def test_emotion_of_joy_is_warm_hue():
    c = emotion_of("I am so happy and full of joy")
    assert 40 <= c.hue <= 70  # yellow/green region
    assert c.saturation > 0.6


def test_emotion_of_grief_is_cool_dark():
    c = emotion_of("deep grief and sorrow")
    assert 240 <= c.hue <= 285  # blue/purple region
    assert c.saturation > 0.7


def test_emotion_of_neutral_is_gray():
    c = emotion_of("the file is 42 bytes")
    assert c.saturation == 0.0


def test_hue_wraps_around():
    assert hue_distance(0, 350) == 10.0
    assert hue_distance(10, 20) == 10.0


def test_continuity_detects_jarring_jump():
    joy = emotion_of("happy joy")
    grief = emotion_of("grief sorrow")
    assert continuity(joy, grief) > continuity(joy, emotion_of("glad hope"))
    assert not is_continuous(joy, grief)
    assert is_continuous(joy, emotion_of("glad hope"))
