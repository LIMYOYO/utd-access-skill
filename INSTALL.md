# Install Paper Access

Paper Access currently supports **macOS + Google Chrome + Codex with local command access**. Allow 10–20 minutes for the first setup.

## 1. Ask Codex to install it

Paste this into Codex:

> Install Paper Access from https://github.com/LIMYOYO/paper-access-router. Read INSTALL.md and skills/paper-access/references/installation.md first. Check the existing environment, then set up the dependencies, CLI, skill, Chrome extension, and native bridge. Ask me only when Chrome permission, institutional login, MFA, or website verification needs my action. Finally, download one real paper and confirm that the PDF is usable before reporting the installation complete.

Codex will install or locate `uv`, Python 3.11+, and the project dependencies. You do not need Node.js, an EDS API key, a LibKey API key, or a paid API for normal use. The repository can be cloned with Git or downloaded as a ZIP.

## 2. Complete the browser steps

1. Open Chrome with the profile you normally use to access papers.
2. Open `chrome://extensions`, enable **Developer mode**, choose **Load unpacked**, and select the repository folder that Codex gives you. Pin **Paper Access Router** to the toolbar.
3. Approve the requested website permissions. After Codex installs the native bridge, reload the extension. Keep Chrome's download folder aligned with the path configured by Codex and disable **Ask where to save each file before downloading**.
4. For INFORMS, install [LibKey Nomad](https://thirdiron.com/downloadnomad/), select **University of Toronto**, and complete the institutional login/MFA when asked. Codex can also use the University of Toronto LibKey route directly. SSRN-only users can skip Nomad and institutional login.
5. Let Codex run one real download for every route you plan to use. Then start a new Codex conversation so the installed skill is discovered.

Do not send passwords, cookies, or MFA codes to Codex. Chrome permissions and personal authentication cannot be completed by copying the skill alone.

## 3. Use it

Ask naturally:

> Investigate the Mobile AED literature. When abstracts are insufficient to judge relevance, download the key papers and read the full text.

You can also provide a DOI or SSRN URL. Download success and identity validation are reported separately. If you need both gates to pass, say: “Use strict validation; analyze only papers whose identity is verified.”

For manual setup, upgrades, troubleshooting, or exact commands, give Codex the [detailed installation guide](skills/paper-access/references/installation.md).
