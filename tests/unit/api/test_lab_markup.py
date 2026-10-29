"""The visible action outcome choices must submit the API's actual statuses."""
from html.parser import HTMLParser
from pathlib import Path


def test_guardrail_outcome_selector_includes_blocked():
    class Options(HTMLParser):
        selected = False
        values = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'select':
                self.selected = attrs.get('id') == 'expected-outcome'
            if tag == 'option' and self.selected:
                self.values.append(attrs.get('value'))

        def handle_endtag(self, tag):
            if tag == 'select':
                self.selected = False

    parser = Options()
    parser.feed((Path(__file__).resolve().parents[3] / 'frontend/lab/index.html').read_text(encoding='utf-8'))
    assert parser.values == ['', 'blocked', 'simulated']
