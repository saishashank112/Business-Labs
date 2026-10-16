"""Shared test fixtures."""

import pytest


@pytest.fixture
def sample_sitemap_xml() -> str:
    """A small sitemap XML for testing (3 articles + 1 folder to skip)."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://support.brilliantdirectories.com/support/solutions/articles/5000665570-ssl-https-faq</loc>
        <lastmod>2026-09-22T23:13:12+05:30</lastmod>
        <changefreq>always</changefreq>
        <priority>0.512</priority>
      </url>
      <url>
        <loc>https://support.brilliantdirectories.com/support/solutions/articles/5000673365-toolbox-sidebar-manager</loc>
        <lastmod>2026-06-13T05:20:26+05:30</lastmod>
        <changefreq>always</changefreq>
        <priority>0.512</priority>
      </url>
      <url>
        <loc>https://support.brilliantdirectories.com/support/solutions/articles/5000673655-emails-forms-inbox</loc>
        <lastmod>2026-05-21T08:13:50+05:30</lastmod>
        <changefreq>always</changefreq>
        <priority>0.512</priority>
      </url>
      <url>
        <loc>https://support.brilliantdirectories.com/support/solutions/folders/12000005578</loc>
        <lastmod>2026-10-11T08:00:54+00:00</lastmod>
        <changefreq>always</changefreq>
        <priority>0.64</priority>
      </url>
    </urlset>"""


@pytest.fixture
def sample_article_html() -> str:
    """Minimal HTML that mimics a Brilliant Directories article page."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test Article</title></head>
    <body>
      <header class="banner"><nav>skip this</nav></header>
      <article class="article-body" id="article-body">
        <h1 class="post-title heading">How to Set Up Payments</h1>
        <h2>Step 1: Go to Settings</h2>
        <p>Navigate to Admin &gt; Settings &gt; Payments.</p>
        <ul>
          <li>Select your payment gateway</li>
          <li>Enter your API keys</li>
        </ul>
        <h2>Step 2: Test a Payment</h2>
        <p>Use the test mode to verify everything works.</p>
        <img src="https://example.com/screenshot.png" alt="Payment settings screen">
        <table>
          <thead><tr><th>Gateway</th><th>Fee</th></tr></thead>
          <tbody>
            <tr><td>Stripe</td><td>2.9%</td></tr>
            <tr><td>PayPal</td><td>3.5%</td></tr>
          </tbody>
        </table>
      </article>
      <footer>skip this too</footer>
    </body>
    </html>
    """
