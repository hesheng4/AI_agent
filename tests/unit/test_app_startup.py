def test_create_app_without_frontend_dist():
    from app.main import create_app

    app = create_app()

    assert app.title == "Research Agent Platform"
