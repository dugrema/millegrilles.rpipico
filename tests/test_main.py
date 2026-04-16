def test_main_output(capsys):
    import python_test1.main

    python_test1.main.main()
    out, err = capsys.readouterr()
    assert out.strip() == "Hello from python_test1!"
