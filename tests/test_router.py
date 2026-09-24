from app.router import route


def test_image_routes_to_vision():
    agents = route(text=None, image_base64="fakebase64data")
    assert "vision" in agents


def test_sensor_data_routes_to_sensor():
    agents = route(text=None, sensor_data={"ph": 6.0})
    assert "sensor" in agents


def test_question_routes_to_knowledge():
    agents = route(text="Why is my pH high?")
    assert "knowledge" in agents


def test_action_request_routes_to_controller():
    agents = route(text="Turn the pump on for 30 seconds.")
    assert "controller" in agents


def test_combined_image_and_sensor_routes_both():
    agents = route(text=None, image_base64="abc", sensor_data={"ph": 6.0})
    assert "vision" in agents and "sensor" in agents


def test_plain_statement_defaults_to_knowledge():
    agents = route(text="hydroponics is interesting")
    assert "knowledge" in agents


def test_no_input_defaults_to_knowledge():
    agents = route()
    assert agents == ["knowledge"]
