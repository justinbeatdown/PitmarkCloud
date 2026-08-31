# Pitmark Cloud v0.16.7

- Replaces generic search-page scraping with a corroborated public-research fallback.
- When both publisher HTML and WordPress REST are blocked, Pitmark discovers matching public coverage through Bing/Google News RSS.
- Candidate articles are fetched through the existing Shield-safe redirect path.
- Recovery requires strong article-identity matching and independent-domain corroboration before article generation can proceed.
- Desktop and mobile share this backend path.
