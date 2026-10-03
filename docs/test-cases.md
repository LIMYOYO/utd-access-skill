# Manual test cases

本页保留早期手工路由检查。0.6.0 的完整安装验收、native bridge、SSRN 和批量检查以 [INSTALL.zh-CN.md](../INSTALL.zh-CN.md) 第 6–7 节为准；这里的浏览器路由仍可用于 bridge 不可用时的单篇降级检查。

These checks deliberately use individual, user-initiated article requests. Do not use them for bulk downloading.

## 1. Establish a University of Toronto session

1. Open the extension.
2. Select **Start 8-hour session**.
3. Sign in with UTORid and approve Duo when U of T asks.
4. If Duo offers **Yes, this is my device**, select it only on a personal device.
5. Confirm that EBSCO Business Source Premier opens.

Expected: OpenAthens remains usable for up to eight hours in the same browser session. The extension never receives the password, Duo response or cookies; when site permission is granted, it can read the article metadata and normal download controls required by the UTD Access Skill workflow.

## 2. Current subscription-only INFORMS article

- DOI: `10.1287/mnsc.2025.00819`
- Title: *Political Polarization and Nonmarket Strategy over the Policy Life Cycle*

1. Paste the DOI into the extension and select **Open through LibKey**.
2. On first use, select **University of Toronto** in LibKey.
3. Follow the best full-text link.

Expected: LibKey checks U of T holdings and routes the request to the licensed full text, currently expected through EBSCO Business Source Premier.

## 3. INFORMS article with unverified open-access status

- DOI: `10.1287/mnsc.2023.00320`
- Title: *Collaborative Learning and Decision Making on Pricing and Recommendation: A Simple Framework for Planning*

Expected: LibKey resolves the article's currently available access options. Do not require an open-access result for this DOI: on September 25–26, 2026, OpenAlex reported it as closed with no cached full text, while a direct publisher PDF request returned HTTP 403. These observations do not definitively establish its access status, but do not support the previous claim that it is an OA test fixture. See the [access audit](research/2026-09-26-access-audit.md).

## 4. DOI detection

1. Visit an article page containing a `citation_doi` metadata field or a `doi.org` link.
2. Open the extension.

Expected: The DOI field is filled automatically. Restricted browser pages such as `chrome://` should instead ask for a pasted DOI.

## 5. Context menu

1. Select a DOI in a normal webpage.
2. Right-click and choose **Open paper through LibKey**.

Expected: A new LibKey tab opens for the selected DOI.

## Known boundary

The extension does not and must not bypass Duo, publisher authentication, license restrictions, download limits, or interlibrary-loan rules. A vendor or institution may require reauthentication earlier than expected.
