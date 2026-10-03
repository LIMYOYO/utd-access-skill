# UTD Paper Access Privacy

UTD Paper Access has no project-operated backend, analytics, advertising, or account system. Browser and PDF processing occurs on the user's computer.

The Chrome extension can:

- read DOI, title, author and normal download-link metadata on sites for which the user grants access;
- open background tabs and initiate user-authorized downloads;
- observe Chrome download records needed to bind a completed file to its request;
- exchange request state and local file paths with the registered UTD Paper Access native host.

The local CLI and native host can copy, hash, parse, validate and extract text from downloaded papers, and store task state and reports in the user's local Paper Access data and output directories. The legacy `paper-access` storage identifier is retained so existing installations keep their data.

The system does not read or export browser cookies, passwords, institutional credentials, MFA responses or session tokens. It does not transmit papers or credentials to the project author. Metadata and files may be sent only to sources the user enables for acquisition, such as Crossref, OpenAlex, Unpaywall, LibKey, EBSCO, SSRN, publishers or institutional repositories; those services operate under their own policies and access terms.

Uninstalling the native bridge removes its Chrome registration but deliberately preserves downloaded papers, task databases and runtime files. The user controls later deletion of those local files.
