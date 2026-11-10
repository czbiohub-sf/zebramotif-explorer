"""ZebraMotif package and console entry point."""


def main() -> None:
    """Load and start the dashboard when the console command is invoked."""
    from zebramotif.app import main as run_app

    run_app()
