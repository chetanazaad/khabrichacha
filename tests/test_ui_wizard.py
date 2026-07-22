from khabrichacha.ui.wizard import SetupWizard


def test_setup_wizard_launch_invokes_callback():
    called = []
    wizard = SetupWizard(on_launch=lambda: called.append("launched"))

    wizard._launch_ui()

    assert called == ["launched"]
