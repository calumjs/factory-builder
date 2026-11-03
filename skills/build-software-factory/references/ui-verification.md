# Verify the running UI and its diagnostics

Use this procedure when the change has a UI. It is guidance for authorized work,
not a browser runner, new gate or permission grant. Build records its own checks;
Verify independently exercises the final subject and captures new evidence.
When a required browser/tool/target is unavailable or denied, record BLOCKED/NOT
RUN and the exact limit. Do not retry a denied route, install tools, substitute
generated images or mark a screenshot review complete from source inspection.

## Plan the acceptance journeys and own the server

Map every applicable acceptance criterion to user actions, assertions, pages,
actors and existing A-rows/G2. Include layout and interaction states affected by
the diff: navigation, validation, loading, errors, empty states and persistence.
Use desktop and mobile widths that fit the app (1440px and 390px are examples),
with explicit heights; exercise light and dark when both are supported. Record
any non-applicable dimension and reason. A narrow viewport is not proof of real
mobile-device, touch or browser-engine compatibility. Use actual application
theme controls when themes are not solely driven by system color preference.

Inspect the existing start/test commands and permitted environment. Start your
own isolated app instance on an available non-default loopback port; record its
command, exact source revision, process ownership, port and startup/teardown
results in private evidence. Never stop, reuse, reconfigure or overwrite an
already-running server. If the chosen port is occupied, select another permitted
port; do not kill its owner. Match browser baseURL to your instance and verify the
served build identity rather than assuming the checkout is what the server serves.

When using an existing Playwright webServer setup, review an explicit
`reuseExistingServer: false`, finite startup timeout and project-supported port
argument. A generic `npm run start` is not a universal server command. Keep test,
action and total-session timeouts finite. Stop only your owned process using the
supported teardown path in finally/fixture cleanup; record failures to stop and
remaining ownership uncertainty. Separate writable fixtures, ports and artifact
directories for base/candidate and Build/Verify runs. A base comparison also
needs authorized isolated setup; never replace another worker's checkout/server.
See [Playwright webServer configuration](https://playwright.dev/docs/api/class-testconfig#test-config-web-server).

## Exercise and independently capture

Attach diagnostic listeners before the first navigation/action on each page.
Use the project's existing authorized headless browser setup. Drive the actual
user journeys, assert their outcomes and inspect wrapping,
clipping, contrast, missing images and responsive behavior. Preserve committed-save
success/failure/timeout checks before reload and durable readback afterwards;
optimistic paint, zero pending requests or a transport response alone is not a
successful save. Keep separate interruption tests where required.

Verify must take its own screenshots from its own run, never reuse the builder's
images as verifier evidence. Use separate private filenames per subject, role,
criterion, viewport, theme and state, and record capture time plus source/build
identity. Review the actual pixels; neither a successful screenshot call nor a
test count establishes visual acceptance. Screenshots can expose private data:
use approved fixtures and review/redact before sharing, documenting redactions
and any unverified region. Keep original private evidence within its allowed
retention scope. A mocked or synthetic image is not running-app evidence.

Playwright supports [viewport/color-scheme emulation](https://playwright.dev/docs/emulation)
and [screenshots](https://playwright.dev/docs/screenshots). Adapt these APIs to the
installed version and project, without installing or launching anything merely
because this guide exists.

## Keep four signal classes separate

Record console errors/assertions, uncaught page errors, failed transport requests
and HTTP 4xx/5xx responses separately on every visited page. HTTP error statuses
are responses, not `requestfailed` events; collect both paths. Do not assume one
listener covers them all. The [Page event API](https://playwright.dev/docs/api/class-page#page-event-request-failed)
documents this distinction; [console type](https://playwright.dev/docs/api/class-consolemessage#console-message-type)
identifies error/assert messages. Popups, service workers and non-page traffic
need their own reviewed capture strategy. A listener attached after popup creation
may miss its initial traffic; an uncovered required journey remains unverified.

The optional example below is an in-memory signal inventory for one already
authorized page. It has no file/network/browser launch code and no PASS decision.
It deliberately exports no raw URL, query, fragment, credentials, path, console
text/arguments, error stack, request body/headers or response body. Supply reviewed
non-secret route aliases and labels, not tokens disguised as labels. Unmapped
routes remain visible as `unmapped`; inspect them locally and add only reviewed
redacted details to a finding. The full revision is caller-supplied identity, not
proof that this page serves that revision. Limits or callback failures make the
capture incomplete, never clean. This inventory alone cannot explain an error's
root cause or replace application assertions.

```javascript
function collectUiSignals(page, { subject, role, pageLabel, routeLabels, limit = 200 }) {
  const label = value => typeof value === 'string' && value.length <= 32 && /^[a-z]/.test(value) && !/[^a-z0-9_-]/.test(value);
  if (typeof subject !== 'string' || ![40, 64].includes(subject.length) || /[^0-9a-f]/.test(subject) ||
      !['build', 'verify'].includes(role) || !label(pageLabel) ||
      !Number.isInteger(limit) || limit < 1 || limit > 500 ||
      !Array.isArray(routeLabels) || routeLabels.length > 64) {
    throw new Error('Invalid supplied UI capture metadata');
  }
  const aliases = new Map();
  for (const pair of routeLabels) {
    if (!Array.isArray(pair) || pair.length !== 2 || typeof pair[0] !== 'string' ||
        pair[0].length > 2048 || !label(pair[1])) throw new Error('Invalid route alias');
    let url;
    try { url = new URL(pair[0]); } catch { throw new Error('Invalid route alias'); }
    const key = url.origin + url.pathname;
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
        url.search || url.hash || key !== pair[0] || aliases.has(key)) {
      throw new Error('Invalid route alias');
    }
    aliases.set(key, pair[1]);
  }
  const route = raw => {
    if (typeof raw !== 'string' || raw.length > 4096) return 'unmapped';
    try {
      const url = new URL(raw);
      return aliases.get(url.origin + url.pathname) || 'unmapped';
    } catch { return 'unmapped'; }
  };
  const method = raw => ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'].includes(raw) ? raw : 'OTHER';
  const events = [];
  let step = 'unassigned', dropped = 0, callbackFailed = false, detached = false;
  const add = (kind, extra = {}) => {
    if (events.length >= limit) { dropped = Math.min(dropped + 1, Number.MAX_SAFE_INTEGER); return; }
    events.push({ ordinal: events.length + 1, kind, step, pageRoute: route(page.url()), ...extra });
  };
  const guarded = fn => event => { try { fn(event); } catch { callbackFailed = true; } };
  const listeners = {
    console: guarded(message => {
      const level = message.type();
      if (level === 'error' || level === 'assert') add('console_error', { level });
    }),
    pageerror: guarded(() => add('page_error')),
    requestfailed: guarded(request => add('request_failed', {
      requestRoute: route(request.url()), method: method(request.method())
    })),
    response: guarded(response => {
      const status = response.status();
      if (!Number.isInteger(status) || status < 100 || status > 599) throw new Error('Invalid status');
      if (status >= 400) add('http_error', {
        status, requestRoute: route(response.url()), method: method(response.request().method())
      });
    })
  };
  for (const [name, listener] of Object.entries(listeners)) page.on(name, listener);
  return {
    setStep(value) {
      if (!label(value)) throw new Error('Use a reviewed non-secret step label');
      step = value;
    },
    snapshot() {
      return { subject, role, pageLabel, events: events.map(event => ({ ...event })),
        dropped, callbackFailed, detached, scope: 'supplied identity; page signals only; no verdict' };
    },
    detach() {
      for (const [name, listener] of Object.entries(listeners)) page.off(name, listener);
      detached = true;
    }
  };
}
```

For example, map the exact approved local origin/path
`http://127.0.0.1:4177/profile` to `profile`, set step `a1-save`, and attach before
navigation. The collector strips query/fragment/user-info from lookup and never
exports the underlying string. Unknown paths get no guessed label. Take a final
snapshot after the bounded journey has settled, detach only these listeners in
finally, and preserve a sanitized artifact outside the factory with the relevant
screenshots. Choose a bounded window and page count in the test plan; zero signals
within that window do not prove absence outside it. If the cap is hit or a callback
fails, classify coverage as incomplete and obtain a bounded adequate capture.
Do not silently discard the overflow or turn an empty inventory into PASS.

## Classify findings and record existing evidence

Treat a new unexplained console/page/network failure on a touched page as a Major
finding pending task-specific triage. Record the criterion, affected journey,
source class, sanitized details, subject, target, reproduction and evidence path.
Build and Verify keep separate capture sets and authorship. Reproduce against the
comparison base only within authority, recording its actual subject and conditions.
A pre-existing base failure is not automatically nonblocking: if it violates
still-required acceptance, the check remains FAILED/BLOCKED until repaired or
explicitly waived. Out-of-scope findings need their own owner/disposition; their
age alone never grants a waiver. No baseline run means baseline status unknown.

Expected negative/authentication responses need a narrow documented exception:
the exact criterion, journey step, approved route/method/status, expected visible
outcome, rationale and evidence. Preserve the observation and verify that outcome.
Do not blanket-ignore all 401/403/404, all third-party requests, every console error
or every failure also seen on base. The example filters none of these exceptions
automatically; an unmapped route or redacted message cannot justify an exception
without sufficient reviewed local evidence.

Record results in the existing A-rows/G2 for the exact tested subject, including
matrix scope, screenshots, diagnostic counts, exceptions, failures, skips and
unverified dimensions. Retain underlying observations on optional WAIVED rows;
no new UI gate is invented. An expected negative response is not an unexpected
failure, but its asserted outcome still needs evidence. A missing required
dimension cannot be covered by another viewport/theme's PASS. Use the real runner's
collection and final results; distinguish repeats/retries from distinct tests.
The builder only records supplied claims and does not attest that this procedure
ran. Existing factories need reviewed guide adoption; a plugin update rewrites
neither their contracts nor their evidence.

Before compact-phase migration, an older factory must separately adopt and
register a reviewed `ui-verification.md` support contract. The migration refuses
if it is absent, captures its existing raw bytes for concurrent-change checks,
and does not create or overwrite it. A custom reviewed guide remains unchanged;
its content is not automatically certified by the migration.
