from bdi_fsm.topology import (map_code_line, map_concept_word, process_file,
                              line_hash, VECTOR_NAMES)


def test_comparison_is_evaluate_not_transition():
    # the precedence fix: '==' must map to EVALUATE (3), never TRANSITION (2)
    assert 3 in map_code_line("if x == y:")
    assert 2 not in map_code_line("if x == y:")


def test_bare_assignment_is_transition():
    assert map_code_line("x = 5") == (2,)


def test_compound_assignment_is_transition():
    assert map_code_line("count += 1") == (2,)


def test_import_is_bind():
    assert 5 in map_code_line("import os")


def test_emit_purge_loop():
    assert 1 in map_code_line("print('hello')")
    assert 4 in map_code_line("del x")
    assert 6 in map_code_line("for i in range(10):")


def test_line_can_touch_multiple_vectors():
    v = map_code_line("x = input()")
    assert 2 in v and 7 in v  # TRANSITION + LISTEN


def test_concept_word_sensory_stripping():
    assert map_concept_word("eat") == 4
    assert map_concept_word("touch") == 5
    assert map_concept_word("hear") == 7
    assert map_concept_word("speak") == 1
    assert map_concept_word("walk") == 6


def test_line_hash_is_stable():
    assert line_hash("x = 5") == line_hash("x = 5")
    assert line_hash("x = 5") != line_hash("x = 6")


def test_process_file_frames():
    code = "import os\nif os.path.exists('f'):\n    print('found')\n    del f\n"
    frames = process_file(code, ".py")
    assert len(frames) == 4
    assert frames[0]["universal_actions"] == ["BIND"]
    assert frames[2]["depth"] == 1  # indented block
    assert all(isinstance(f["line_hash"], int) for f in frames)
