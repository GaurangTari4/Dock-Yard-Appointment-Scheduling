import os
from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_navigation_and_pagination_widgets():
    os.environ['API_BASE_URL']='http://logistics-api-test:8000'
    at=AppTest.from_file(Path(__file__).parents[1] / 'dashboard' / 'app.py').run()
    assert not at.exception
    at.radio[0].set_value('Appointments').run()
    assert not at.exception
    assert at.number_input[0].label == 'Result offset'
    at.radio[0].set_value('Dock calendar').run()
    assert not at.exception
