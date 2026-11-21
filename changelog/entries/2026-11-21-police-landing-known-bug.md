### The police station's own landing read as moved: a known bug

The editor follow-ups' stage P5 found that URB_PoliceStation, opened with nothing changed, hides its own Skyranger,
drop zone frame, dust and sound, as for a landing zone moved away. It is left for later, outside the follow-ups plan.

- [KNOWN-BUGS.md](../../KNOWN-BUGS.md) KB-13: what a user sees, since 18 November 2026, no workaround in the view.
- [T-51](../../research/findings-register.md) in the findings register: the cause, `spawns.js`' `landingUnmoved`
  comparing the map's own soldier points (on raised ground, 3 to 5 units off the layout) with the layout it works out
  from the zone, and a fix to try.

Checked: the page's `movedLandingActors()` read on test servers running main's code (before the refactor) and the
follow-ups' tip, on the same scratch cache: the same six pieces on both. Not checked: a Build after a zone change on
this map.
