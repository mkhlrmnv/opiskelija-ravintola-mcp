# Menssa (Otaniemi) data-source research

Status: **INCOMPLETE. menssa.fi could not be reached from this session.**
Research date: 2026-11-01.

## 1. Access status (observed)

| Host | Method | Result |
|---|---|---|
| https://menssa.fi | WebFetch | `getaddrinfo ENOTFOUND menssa.fi` (DNS failure; the session reports the host is outside the allowed network domains) |
| https://www.aalto.fi/fi/kampus/kampusravintolat-ja-kahvilat | WebFetch | `getaddrinfo ENOTFOUND www.aalto.fi` (same failure) |
| WebSearch "menssa.fi ruokalista Otaniemi" | WebSearch | Search returned aalto.fi and kanttiinit-related pages, but **no menssa.fi page** |
| WebSearch "Menssa Otaniemi lounas kanttiinit" | WebSearch | Same as above |

Because two hosts failed DNS resolution, I stopped fetching further sites, as the session instructions require. **To complete this research, `menssa.fi` (and `www.aalto.fi` / `kanttiinit.fi`) must be added to the session's allowed network domains, and the research re-run.**

Nothing below was read from menssa.fi itself. The only observations come from WebSearch result snippets, which are search-tool summaries and not verbatim page text.

## 2. What was observed (secondary sources, via search snippets only)

- Menssa is listed as a student restaurant at **Otakaari 7, Otaniemi** on Aalto's campus restaurant list (Finnish and English versions).
- That list says a **student-priced meal is available 1.6.–23.8.** This is a summer window. Today is 2026-11-01, so that price window is over and should not be assumed to apply now.
- Aalto's page says the most current details (opening hours, meal prices, lunch menus) are on **each restaurant's own website**.
- Aalto's page names **kanttiinit.fi** as a site that compiles the day's menus for the campus student restaurants. Whether Menssa is included there is **UNVERIFIED**.
- Aalto's June 2026 campus map (`https://www.aalto.fi/sites/default/files/2026-06/16.6.26-Otaniemi_kampuskartta_kampuskarta.pdf`) lists Menssa among the student restaurants. An older 2025 map gives it as "Menssa 29 A3".
- Other campus lunch places mentioned in the same snippets (not Menssa): Factory Otaniemi (weekday 10:30–14:00 per snippet), Fat Lizard, MOO, MAU-KAS, Bliss, Tasteat, Subway T-talo.

## 3. Items the task asked for, all still open

1. **Operator and delivery mechanism (menssa.fi):** NOT OBSERVED. Whether the page is server-rendered HTML, a JSON API, or an embedded third-party system (Jamix, Aromi, Mealdoo, Compass/Sodexo, etc.) cannot be determined. No script, iframe or API URLs were inspected.
2. **Date selection (current week only vs. date parameter):** NOT OBSERVED.
3. **Structure (dish names, diet codes, prices, fi/en versions):** NOT OBSERVED. No sample HTML or JSON was obtained, so none is included.
4. **Macros / nutrition:** NOT OBSERVED. Nothing is known about whether Menssa's system exposes kcal, protein, carbs, fat, fibre, salt, sugar or saturated fat. Do not assume any of these exist.
5. **Plain GET vs. JS rendering (Playwright):** NOT DETERMINED.
6. **Lunch hours:** NOT FOUND for Menssa. The only hours seen were for other restaurants (Factory 10:30–14:00).

## 4. Suggested next steps (once hosts are allowed)

1. WebFetch `https://menssa.fi` with a prompt asking for every `<script src>`, `<iframe src>`, and every URL or API path in the HTML, verbatim. Look for references to known lunch systems (`jamix`, `aromi`, `mealdoo`, `compass`, `sodexo`, `fazer`) in those URLs.
2. Fetch `https://www.aalto.fi/fi/kampus/kampusravintolat-ja-kahvilat` and `https://www.aalto.fi/en/campus/campus-restaurants-and-cafes` to confirm the Menssa entry text, hours, and any menu link.
3. Fetch the kanttiinit.fi site and check whether Menssa is listed, its menu URL pattern, and whether it exposes a JSON endpoint. Do not assume the slug or endpoint.
4. If the menssa.fi page is JS-rendered, check the network calls it makes before considering Playwright. Playwright is the last resort.

## 5. Gotchas to watch for

- The student-price window noted by Aalto (1.6.–23.8.) is stale for the current date.
- Aalto explicitly says the restaurant websites, not the aalto.fi pages, are authoritative for menus and hours.
- Search snippets are not page content. Any field name, endpoint, or hour quoted in a snippet must be confirmed against the live page before use.

## 6. Unverified / needs in-container check

- Everything in section 3 (all Menssa-specific facts) is UNVERIFIED because menssa.fi was not reachable.
- Whether Menssa is included in kanttiinit.fi: UNVERIFIED.
- Operator of Menssa (the organisation running it): UNVERIFIED.
- Lunch hours for Menssa: UNVERIFIED.
- Any JSON API, diet codes, price structure, or nutrition fields: UNVERIFIED, none observed.
- Access requirement: `menssa.fi` and `www.aalto.fi` must be allowed in the session's network settings before this research can be completed.
