# Manual test cases

These checks deliberately use individual, user-initiated article requests. Do not use them for bulk downloading.

## 1. Establish a University of Toronto session

1. Open the extension.
2. Select **Start 8-hour session**.
3. Sign in with UTORid and approve Duo when U of T asks.
4. If Duo offers **Yes, this is my device**, select it only on a personal device.
5. Confirm that EBSCO Business Source Premier opens.

Expected: OpenAthens remains usable for up to eight hours in the same browser session. The extension never sees the password, Duo response, cookies, or EBSCO content.

## 2. Current subscription-only INFORMS article

- DOI: `10.1287/mnsc.2025.00819`
- Title: *Political Polarization and Nonmarket Strategy over the Policy Life Cycle*

1. Paste the DOI into the extension and select **Open through LibKey**.
2. On first use, select **University of Toronto** in LibKey.
3. Follow the best full-text link.

Expected: LibKey checks U of T holdings and routes the request to the licensed full text, currently expected through EBSCO Business Source Premier.

## 3. Open-access INFORMS article

- DOI: `10.1287/mnsc.2023.00320`
- Title: *Collaborative Learning and Decision Making on Pricing and Recommendation*

Expected: LibKey offers an open-access copy without requiring institutional authentication.

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
