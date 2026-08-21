# Paper Access Router

A small, dependency-free browser extension that turns a DOI into the best legal route to full text. It is optimized for University of Toronto users while remaining useful to researchers at other LibKey institutions.

## Why this exists

INFORMS moved institutional online access to EBSCO Business Source packages in 2026. University of Toronto subscribes to Business Source Premier, but researchers may begin from a DOI, Google Scholar, an email, or the INFORMS publisher page. The result is a fragmented route involving LibKey, OpenAthens, EBSCO, and sometimes open-access copies.

This extension keeps that routing in one place. Authentication remains between the user, their institution, and the content provider.

## What it does

- detects a DOI from common article-page metadata and `doi.org` links;
- accepts pasted DOI strings or DOI URLs;
- opens the article through LibKey, which can check institutional holdings and open-access alternatives;
- provides a University of Toronto button to begin an OpenAthens/EBSCO Business Source Premier session;
- adds a right-click action for selected DOIs and DOI links.

## What it does not do

- bypass Duo or any other MFA;
- store institutional credentials or authentication cookies;
- scrape publisher sites or perform bulk downloads;
- redistribute PDFs;
- guarantee access when a library does not license an article.

## Install locally

1. Open `chrome://extensions` in Chrome or `edge://extensions` in Edge.
2. Enable **Developer mode**.
3. Select **Load unpacked**.
4. Choose this repository directory.
5. Pin **Paper Access Router** to the toolbar.

## University of Toronto workflow

1. At the start of a research session, select **Start 8-hour session** and complete UTORid/Duo authentication.
2. If Duo offers **Yes, this is my device**, use it only on your personal device; U of T may remember the MFA session for 24 hours.
3. Open an article page or paste its DOI into the extension.
4. Select **Open through LibKey**. The first time, choose **University of Toronto** in LibKey.
5. Use the PDF or full-text option that LibKey provides.

See [manual test cases](docs/test-cases.md) for current INFORMS examples.

## 中文快速说明

每天开始查论文时，先点击 **Start 8-hour session**，用 UTORid 和 Duo 建立 U of T 的 OpenAthens 会话。之后打开论文页面，扩展会尝试识别 DOI；也可以直接粘贴 DOI，再通过 LibKey 查找 U of T 已订阅全文或合法开放版本。

本项目不会保存账号、密码、Duo 信息或 PDF，也不会绕过学校和出版社权限。

## Test

Requires a current Node.js release with the built-in test runner.

```sh
npm test
```

Manual authentication and full-text routing must be tested in a browser by an authorized user. Automated tests intentionally stop before institutional login.

## Sharing and contribution

The code is intentionally small enough to audit. Before publishing it in a public repository:

- run the automated and manual tests;
- capture no screenshots containing names, UTORids, email addresses, or library-account information;
- keep downloads user-initiated and article-by-article;
- document institution-specific routes rather than hard-coding credentials.

## License

MIT. See [LICENSE](LICENSE).
