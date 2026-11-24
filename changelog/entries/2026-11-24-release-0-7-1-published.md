### Release 0.7.1 published

On the user's word ("ok go ahead and push and publish"), after the notes were shown in full.

- Main pushed (`8f3ba42`, the commit the release was built from), then the release created on it:
  <https://github.com/ruskyandrei/xcom-map-workshop/releases/tag/v0.7.1>, marked latest.
- Checked: both files' sizes and SHA-256 digests on GitHub equal the local ones (70,365,132 and 109,431,786 bytes);
  `releases/latest` names `v0.7.1`; both `releases/latest/download/` links answer (206 to a one-byte range request);
  the published notes equal [0.7.1.md](../../tools/release/notes/0.7.1.md) but for one trailing blank line; the tag
  is on `8f3ba42`.
- The guide page was republished by the push (the guide workflow passed on `8f3ba42`), and it equals the page
  `guide.inline()` makes here byte for byte.
