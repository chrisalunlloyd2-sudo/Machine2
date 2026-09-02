"""Tests for CS-BUDDY '90 — deterministic chat bot, no LLM, learns."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bdi_fsm"))

from bdi_fsm.chatbot90 import Chatbot90, HELP_TEXT, MOTD


def make_bot():
    d = tempfile.mkdtemp()
    bot = Chatbot90(state_path=os.path.join(d, "chatbot.mem"))
    bot._default_tools()
    return bot, d


def test_banner_and_help():
    assert "CS-BUDDY" in MOTD
    assert "help" in HELP_TEXT.lower()


def test_greeting():
    bot, _ = make_bot()
    reply = bot.respond("hello")
    assert reply and "CS-BUDDY" in reply or "Hello" in reply or "Hey" in reply
    assert bot.hits.get("greet", 0) == 1


def test_time_tool_no_llm():
    bot, _ = make_bot()
    reply = bot.respond("what time is it")
    assert any(c.isdigit() for c in reply), reply


def test_date_tool():
    bot, _ = make_bot()
    reply = bot.respond("what date is it")
    assert any(c.isdigit() for c in reply)


def test_define_tool():
    bot, _ = make_bot()
    reply = bot.respond("define help")
    assert "tool" in reply.lower() or "lexicon" in reply.lower()


def test_skills_tool():
    bot, _ = make_bot()
    reply = bot.respond("what can you do")
    assert "tools online" in reply


def test_fact_learning_name():
    """LOOP 4 — 'my name is X' stores a fact; recall works."""
    bot, d = make_bot()
    bot.respond("my name is chris")
    assert bot.facts.get("name") == "Chris"
    reply = bot.respond("what's my name")
    assert "Chris" in reply
    # persists to disk
    bot2 = Chatbot90(state_path=os.path.join(d, "chatbot.mem"))
    assert bot2.facts.get("name") == "Chris"


def test_fact_learning_note():
    bot, _ = make_bot()
    bot.respond("remember that I like hexagons")
    assert any("hexagons" in v for v in bot.facts.values())


def test_word_learning():
    """LOOP 1 — unseen words auto-enter the lexicon."""
    bot, _ = make_bot()
    before = bot.lexicon.size()
    bot.respond("flurble the zorp is groovy")
    assert bot.lexicon.size() >= before + 3  # flurble, zorp, groovy


def test_teach_flow_learns_rule():
    """LOOP 2 — unmatched input -> teach -> new rule routes next time."""
    bot, _ = make_bot()
    reply = bot.respond("glorble snarf the wibble")
    assert "teach" in reply.lower() or "don't" in reply.lower() or "hmm" in reply.lower()
    # confirm the teach flow is pending
    assert bot.pending_teach is not None
    # bind it to an intent
    bot.respond("teach greet")
    assert bot.pending_teach is None
    # now the same phrase should route to greet
    before_hits = bot.hits.get("greet", 0)
    bot.respond("glorble snarf the wibble")
    assert bot.hits.get("greet", 0) > before_hits


def test_reinforce_weight_on_confirm():
    """LOOP 3 — 'yes' to a confirmation strengthens the winning rule."""
    bot, _ = make_bot()
    bot.weights["greet"] = 0.5          # dampen greet below threshold
    bot.respond("hello zyxwv qwerty")   # weak match -> fallback, closest=greet
    assert bot.pending_teach is not None
    w_before = bot.weights["greet"]
    bot.respond("yes")                   # confirm -> reinforce
    assert bot.weights["greet"] > w_before
    assert bot.pending_teach is None


def test_negative_recorded():
    bot, _ = make_bot()
    bot.respond("zyxwv qwerty asdfgh")
    bot.respond("no")
    assert bot.pending_teach is None


def test_status_and_learn_commands():
    bot, _ = make_bot()
    assert "rules" in bot.respond("status")
    assert "learning stats" in bot.respond("learn")


def test_mem_command_empty_then_filled():
    bot, _ = make_bot()
    r1 = bot.respond("mem")
    assert "no facts" in r1.lower() or "facts" in r1.lower()
    bot.respond("my name is aegis")
    r2 = bot.respond("mem")
    assert "aegis" in r2.lower()


def test_determinism_same_input_same_tool():
    """Same input twice -> same intent, same hit count growth."""
    bot, _ = make_bot()
    bot.respond("what time is it")
    bot.respond("what time is it")
    assert bot.hits["time"] == 2


def test_no_llm_imports():
    """The module must not import any network/LLM library."""
    import bdi_fsm.chatbot90 as c90
    src = open(c90.__file__).read()
    for banned in ("requests", "openai", "urllib.request", "http.client", "socket"):
        assert banned not in src, f"banned import: {banned}"


def test_persistence_across_instances():
    """Learned rules + weights survive a restart."""
    bot, d = make_bot()
    bot.respond("glorble snarf the wibble")
    bot.respond("teach status")
    bot.respond("my name is buddy")
    n_rules = len(bot.rules)
    bot2 = Chatbot90(state_path=os.path.join(d, "chatbot.mem"))
    assert len(bot2.rules) == n_rules
    assert bot2.facts.get("name") == "Buddy"


def test_save_does_not_crash_readonly():
    bot = Chatbot90(state_path="/nonexistent-dir/chatbot.mem")
    bot._default_tools()
    bot.respond("hello")
    bot.save()  # must not raise


def test_exit_saves_and_returns():
    bot, d = make_bot()
    reply = bot.respond("exit")
    assert "goodbye" in reply.lower() or "saving" in reply.lower()
    assert os.path.exists(os.path.join(d, "chatbot.mem"))


def test_joke_tool():
    bot, _ = make_bot()
    reply = bot.respond("tell me a joke")
    assert len(reply) > 10


def test_thanks_and_bye():
    bot, _ = make_bot()
    assert "welcome" in bot.respond("thank you").lower()
    bot.respond("exit")  # saves


def test_help_command():
    bot, _ = make_bot()
    assert "commands" in bot.respond("help").lower()


def test_empty_input():
    bot, _ = make_bot()
    assert bot.respond("") == "> ..."


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in fns:
        try:
            fn()
            passed += 1
            print(f"  ok  {fn.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {fn.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
