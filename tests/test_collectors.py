from aitrendigest.collectors.github_trending import parse_github_trending_html
from aitrendigest.collectors.arxiv import parse_arxiv_feed


def test_parse_github_trending_html_returns_normalized_item():
    html = """
    <article class="Box-row">
      <h2><a href="/owner/repo"> owner / repo </a></h2>
      <a href="/owner/repo/stargazers">1,234</a>
    </article>
    """

    items = parse_github_trending_html(html)

    assert len(items) == 1
    assert items[0].source_item_id == "owner/repo"
    assert items[0].raw_popularity_signal["stars"] == 1234


def test_parse_arxiv_feed_returns_entry_title_and_url():
    feed = """
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/1234.5678v1</id>
        <title>Agent Evaluation Systems</title>
      </entry>
    </feed>
    """

    items = parse_arxiv_feed(feed)

    assert items[0].title == "Agent Evaluation Systems"
    assert items[0].url == "http://arxiv.org/abs/1234.5678v1"
