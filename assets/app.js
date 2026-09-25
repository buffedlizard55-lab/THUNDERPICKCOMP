/* THUNDERPICKCOMP — static Pages client. Facts and simulations live in data/*.json.
   External data is escaped before injection. A failed/stale feed is visible. */
(function () {
  "use strict";
  var cache = Object.create(null);

  function esc(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function link(url, label) {
    if (typeof url !== "string" || !/^https:\/\/[^\s]+$/i.test(url)) {
      return '<span class="muted">No review link</span>';
    }
    return '<a href="' + esc(url) + '" rel="noopener noreferrer" target="_blank">' + esc(label) + "</a>";
  }
  function badge(status) {
    var types = {
      verified: ["verified", "Verified"], flagged: ["flagged", "Flagged"],
      unverified: ["unverified", "Unverified"], stale: ["unverified", "Stale"],
      tbd: ["tbd", "TBD"], final: ["verified", "Final"],
      scheduled: ["sim", "Scheduled"], active: ["verified", "Active"],
      paused: ["tbd", "Paused"], pending: ["tbd", "Pending"],
      win: ["verified", "Win"], loss: ["unverified", "Loss"],
      void: ["flagged", "Void"], partial: ["flagged", "Partial"],
      ok: ["verified", "Checked"], error: ["unverified", "Feed error"]
    };
    var entry = types[status] || ["flagged", status || "Unknown"];
    return '<span class="badge ' + entry[0] + '">' + esc(entry[1]) + "</span>";
  }
  function sources(list) {
    if (!Array.isArray(list) || !list.length) return '<span class="muted">No source recorded.</span>';
    return '<ul class="source-list">' + list.map(function (s) {
      return "<li>" + link(s.url, s.label) +
        ' <span class="muted small">(' + esc(s.type) + " · checked " + esc(s.accessed_utc) + ")</span></li>";
    }).join("") + "</ul>";
  }
  function utc(value) { return value ? esc(value) : "Not recorded"; }
  function since(value) {
    var delta = Date.now() - Date.parse(value);
    if (!Number.isFinite(delta)) return "age unknown";
    if (delta < -60000) return "device clock differs from feed";
    if (delta < 3600000) return Math.max(0, Math.floor(delta / 60000)) + "m ago";
    if (delta < 86400000) return Math.floor(delta / 3600000) + "h ago";
    return Math.floor(delta / 86400000) + "d ago";
  }
  function old(value, ms) { return !Number.isFinite(Date.parse(value)) || Date.now() - Date.parse(value) > ms; }
  function fmt(value) { return (Math.round(Number(value) * 100) / 100).toFixed(2); }
  function fail(el, error) {
    el.innerHTML = '<div class="error-box" role="alert"><strong>Data unavailable.</strong> This section was not refreshed. ' +
      esc(error && error.message ? error.message : error) + "</div>";
  }
  function load(name) {
    if (!cache[name]) {
      cache[name] = fetch("data/" + name + ".json", { cache: "no-store" }).then(function (response) {
        if (!response.ok) throw new Error(name + ": HTTP " + response.status);
        return response.json();
      });
    }
    return cache[name];
  }
  function show(el, task) { task.catch(function (error) { fail(el, error); }); }

  function masterList(el) {
    show(el, load("master_list").then(function (entries) {
      var category = el.getAttribute("data-filter");
      var filtered = entries.filter(function (e) { return !category || e.category === category; });
      var rows = filtered.map(function (e) {
        var flags = e.flags && e.flags.length ? '<div class="notice warn small"><strong>Flag:</strong> ' + e.flags.map(esc).join("<br>") + "</div>" : "";
        return '<tr id="' + esc(e.id) + '"><td class="mono">' + esc(e.id) +
          '</td><td><strong>' + esc(e.claim) + '</strong><br><span class="small">' + esc(e.detail) +
          '</span>' + flags + '<p class="small muted">' + esc(e.notes) +
          '</p></td><td>' + badge(e.status) + '<br><span class="muted small">' + utc(e.verified_utc) +
          '</span></td><td class="small">' + sources(e.sources) + '</td></tr>';
      });
      el.innerHTML = '<div class="table-scroll"><table class="data"><thead><tr><th scope="col">ID</th><th scope="col">Claim &amp; evidence</th><th scope="col">Status</th><th scope="col">Sources</th></tr></thead><tbody>' + rows.join("") + '</tbody></table></div><p class="small muted">Showing ' + filtered.length + " / " + entries.length + " claims, each with a direct source link. Published snapshots are dated, not continuously verified.</p>";
      // Anchor may be a deep link before JSON finishes loading.
      if (location.hash && document.getElementById(location.hash.slice(1))) document.getElementById(location.hash.slice(1)).scrollIntoView();
    }));
  }

  function roster(team) {
    return '<ul class="roster">' + team.roster.map(function (p) {
      return '<li>' + esc(p.handle) + (p.real_name ? " (" + esc(p.real_name) + ")" : "") +
        ' <span class="muted small">' + esc(p.nation) + "</span></li>";
    }).join("") + '<li><strong>Coach:</strong> ' + esc(team.coach.handle) +
      ' <span class="muted small">' + esc(team.coach.nation) + "</span></li></ul>";
  }
  function teamCards(el) {
    show(el, load("teams").then(function (teams) {
      el.innerHTML = '<div class="grid-2">' + teams.map(function (t) {
        var flags = t.flags && t.flags.length ? '<div class="notice warn small"><strong>Flag:</strong> ' + t.flags.map(esc).join("<br>") + "</div>" : "";
        return '<article class="card team-card"><h3>' + esc(t.name) +
          ' <span class="muted small">' + esc(t.nation) + "</span></h3>" +
          '<p class="small">' + esc(t.route) + ' · Organizer’s Sep 16 VRS #<strong>' + esc(t.vrs_rank_2026_09_16) +
          '</strong> · HLTV #<strong>' + esc(t.hltv_rank_observed) + '</strong> (checked ' + utc(t.hltv_rank_observed_utc) + ")</p>" + roster(t) +
          (t.note && t.note !== "None." ? '<p class="small">' + esc(t.note) + "</p>" : "") + flags +
          '<details><summary>Source links · ' + esc(t.master_list) + "</summary>" + sources(t.sources) + "</details></article>";
      }).join("") + "</div>";
    }));
  }
  function teamTable(el) {
    show(el, load("teams").then(function (teams) {
      el.innerHTML = '<div class="table-scroll"><table class="data"><thead><tr><th scope="col">Team</th><th scope="col">Organizer VRS Sep 16</th><th scope="col">HLTV checked Sep 24</th><th scope="col">Sep 24 lineup &amp; coach</th><th scope="col">Source</th></tr></thead><tbody>' +
        teams.map(function (t) {
          return '<tr><td><strong>' + esc(t.name) + '</strong><br><span class="muted small">' + esc(t.route) + '</span></td><td>#' + esc(t.vrs_rank_2026_09_16) + '</td><td>#' + esc(t.hltv_rank_observed) + '</td><td class="small">' + esc(t.roster.map(function (p) { return p.handle; }).join(", ")) + ' · coach ' + esc(t.coach.handle) + '</td><td>' + link(t.sources[0].url, "Roster source ↗") + '</td></tr>';
        }).join("") + "</tbody></table></div>";
    }));
  }
  function vrsSnapshot(el) {
    show(el, load("observations").then(function (obs) {
      if (!obs.vrs_history.length) {
        el.innerHTML = '<div class="notice warn">Valve snapshot not collected. Do not infer current ranks.</div>';
        return;
      }
      var snap = obs.vrs_history[obs.vrs_history.length - 1];
      el.innerHTML = '<p class="small muted">Official Valve Global VRS dated <strong>' + esc(snap.snapshot_date) +
        '</strong> · captured ' + utc(snap.observed_utc) + ' · ' + link(snap.url, "Open exact ranking file ↗") +
        '. VRS ranked roster is not necessarily the event starting five.</p><div class="table-scroll"><table class="data"><thead><tr><th scope="col">Team</th><th scope="col">Rank</th><th scope="col">Points</th><th scope="col">Ranked five on snapshot date</th></tr></thead><tbody>' +
        snap.teams.slice().sort(function (a, b) { return a.rank - b.rank; }).map(function (t) {
          return '<tr><td>' + esc(t.team_id) + '</td><td>#' + esc(t.rank) + '</td><td>' + esc(t.points) + '</td><td class="small">' + t.roster.map(esc).join(", ") + "</td></tr>";
        }).join("") + '</tbody></table></div>';
    }));
  }

  function matches(el) {
    show(el, load("matches").then(function (items) {
      el.innerHTML = '<div class="table-scroll"><table class="data"><thead><tr><th scope="col">Record</th><th scope="col">Event / stage</th><th scope="col">Fixture</th><th scope="col">Status</th><th scope="col">Detail &amp; source</th></tr></thead><tbody>' +
        items.map(function (m) {
          return '<tr><td class="mono">' + esc(m.id) + '</td><td>' + esc(m.event) + '<br><span class="muted small">' + esc(m.stage) + '</span></td><td>' + (m.team_a && m.team_b ? esc(m.team_a) + " vs " + esc(m.team_b) : "—") + '</td><td>' + badge(m.status) + '</td><td class="small">' + esc(m.detail) + sources(m.sources) + '</td></tr>';
        }).join("") + '</tbody></table></div>';
    }));
  }
  function fixtureSignals(el) {
    show(el, Promise.all([load("observations"), load("teams")]).then(function (pair) {
      var obs = pair[0], teamNames = Object.create(null);
      pair[1].forEach(function (t) { teamNames[t.id] = t.name; });
      var statusBadge = { "scheduled-unconfirmed": "flagged", "scheduled-confirmed": "ok", "conflict": "flagged" };
      var rows = obs.fixtures.map(function (m) {
        var cross = m.result_status === "confirmed"
          ? badge("ok") + " result double-sourced: " + esc(teamNames[m.result.winner] || m.result.winner) + " wins " +
            esc(((m.result && m.result.series_score) || []).join(":")) + " · confirmed " + utc(m.result && m.result.confirmed_utc) +
            " <span class='muted'>(derived from map scores; not an official ruling)</span>"
          : (m.status === "scheduled-confirmed"
              ? badge("ok") + " schedule double-sourced (HLTV check " + utc(m.hltv_verified_utc) + ")"
              : badge("flagged") + " " + esc(m.status) + " — not eligible for any paper decision");
        return "<li>" + badge(statusBadge[m.status] || "flagged") + " <strong>" + esc(teamNames[m.team_a] || m.team_a) + " vs " +
          esc(teamNames[m.team_b] || m.team_b) + "</strong> · " + utc(m.scheduled_utc) + " UTC · " + esc(m.id) +
          (m.group && m.group !== "?" ? " · Group " + esc(m.group) : "") +
          "<br><span class='small'>" + cross + "</span><br><span class='small muted'>Liquipedia template + " + link(m.source_url, "HLTV match page") +
          " · a pre-start paper decision additionally requires a fresh first-party ask whose top-of-book size covers the stake</span></li>";
      });
      el.innerHTML = rows.length ? '<ul class="signal-list">' + rows.join("") + '</ul>'
        : '<div class="notice">No unambiguous Finals fixtures found by the strict source parser. This is not proof no fixtures exist; see source checks below.</div>';
    }));
  }

  function marketSources(el) {
    show(el, load("market_sources").then(function (items) {
      el.innerHTML = '<div class="table-scroll"><table class="data"><thead><tr><th scope="col">Venue</th><th scope="col">Free data</th><th scope="col">Coverage &amp; limits</th><th scope="col">Original check</th></tr></thead><tbody>' + items.map(function (s) {
        return '<tr><td><strong>' + esc(s.name) + '</strong><br>' + link(s.url, "Website") + (s.docs_url ? " · " + link(s.docs_url, "API docs") : "") + '</td><td class="small">' + esc(s.access) + '</td><td class="small">' + esc(s.coverage) + '</td><td class="small">' + esc(s.status) + '<br>' + utc(s.last_checked_utc) + '</td></tr>';
      }).join("") + '</tbody></table></div>';
    }));
  }
  function quoteTable(el) {
    show(el, load("observations").then(function (obs) {
      if (!obs.quotes.length) {
        el.innerHTML = '<div class="notice warn"><strong>No pre-event asks captured.</strong> The observed TWC 2026 qualifier market below is <em>closed</em>; its 0/1 resolution values are NOT pre-match prices. The paper ledger cannot backfill them. Live API polling must capture future quotes first.</div>';
        return;
      }
      var latest = Object.create(null);
      obs.quotes.forEach(function (q) { latest[q.venue + "|" + q.market_id + "|" + q.selection] = q; });
      var rows = Object.keys(latest).map(function (k) { return latest[k]; }).sort(function (a, b) { return b.observed_utc.localeCompare(a.observed_utc); });
      el.innerHTML = '<p class="small muted">' + obs.quotes.length + ' immutable observation(s) in the journal. Showing latest per outcome. Prices are historical observations, NOT live executable orders or confirmed fills.</p>' +
        '<div class="table-scroll"><table class="data"><thead><tr><th scope="col">Venue / market</th><th scope="col">Selection</th><th scope="col">Best ask / size</th><th scope="col">Observed UTC</th><th scope="col">Source / rule</th></tr></thead><tbody>' + rows.slice(0, 50).map(function (q) {
          return '<tr><td><strong>' + esc(q.venue) + '</strong><br>' + esc(q.market_title) + '<br><span class="mono">' + esc(q.market_id) + '</span></td><td>' + esc(q.selection) + '</td><td>$' + esc(q.raw_price) + ' · ' + esc(q.ask_size === null ? "size unavailable" : q.ask_size + " contracts/shares") + '<br>' + (old(q.observed_utc, 30 * 60000) ? badge("stale") : badge(q.quote_status === "fresh" ? "ok" : "flagged")) + '</td><td class="mono small">' + utc(q.observed_utc) + '<br>Venue update ' + utc(q.source_updated_utc) + '</td><td class="small">' + link(q.source_url, "Original API quote ↗") + '<br>' + link(q.event_url, "Event / market ↗") + '<details><summary>Market resolution rule</summary><div class="rule-text">' + esc(q.resolution_rule) + '</div></details><span class="muted mono">' + esc(q.quote_id) + '</span></td></tr>';
        }).join("") + '</tbody></table></div>';
    }));
  }
  function marketEvents(el) {
    show(el, load("observations").then(function (obs) {
      if (!obs.events.length) {
        el.innerHTML = '<div class="notice">No relevant event confirmed in the limited queries so far; this is <em>not</em> an exchange-wide absence claim.</div>';
        return;
      }
      el.innerHTML = '<ul class="signal-list">' + obs.events.slice().reverse().slice(0, 20).map(function (e) {
        var state = e.status === "closed" ? "closed (at last check)" : (old(e.last_seen_utc, 2 * 3600000) ? "last seen open; current status unknown" : "open at last check");
        return '<li>' + badge(e.status === "closed" ? "tbd" : (old(e.last_seen_utc, 2 * 3600000) ? "stale" : "ok")) + ' <strong>' + esc(e.title) + '</strong> · ' + esc(e.venue) + ' · ' + esc(e.stage) + ' · ' + esc(state) + ' · last seen ' + utc(e.last_seen_utc) +
          '<br>' + link(e.source_url, "Official API record ↗") + ' · ' + link(e.review_url, "Market page ↗") + (e.status === "closed" ? ' <span class="muted small">(resolved prices are not historical odds)</span>' : "") + '</li>';
      }).join("") + '</ul>';
    }));
  }
  function pulse(el) {
    show(el, load("observations").then(function (obs) {
      if (!obs.last_completed_utc) {
        el.innerHTML = '<div class="notice bad" role="status">Collection has never completed. No current feed is available.</div>';
        return;
      }
      var stale = old(obs.last_completed_utc, 2 * 3600000);
      var failures = obs.checks.filter(function (c) { return c.status === "error"; });
      var mode = obs.mode === "offline-replay" ? ' <strong>Offline research replay — NOT a running live feed.</strong>' : "";
      el.innerHTML = '<div class="notice ' + (stale || failures.length || obs.mode !== "live" ? "warn" : "good") + '" role="status"><strong>Feed check finished:</strong> ' + utc(obs.last_completed_utc) + ' (' + esc(since(obs.last_completed_utc)) + ').' + mode +
        (stale ? ' <strong>Stale:</strong> scheduled jobs may be delayed/failed; do not use prices as live odds.' : "") +
        (failures.length ? ' <strong>' + failures.length + ' source error(s) flagged.</strong>' : "") +
        ' <a href="markets.html#source-checks">Inspect checks ↗</a></div>';
    }));
  }
  function checks(el) {
    show(el, load("observations").then(function (obs) {
      var alerts = obs.alerts.length ? '<h3>Irregularities</h3><ul class="signal-list">' + obs.alerts.map(function (a) {
        return '<li>' + badge("flagged") + ' ' + esc(a.message) + (a.source_url ? " · " + link(a.source_url, "Review source") : "") + '</li>';
      }).join("") + '</ul>' : '<p class="muted small">No parser/source irregularities recorded in the last attempt; coverage limits still apply.</p>';
      el.innerHTML = '<p class="small muted">Last attempt ' + utc(obs.last_attempt_utc) + '; finished ' + utc(obs.last_completed_utc) + '. Status <strong>' + esc(obs.mode) + '</strong>. “Checked” means only the documented query scope was inspected; zero hits is NOT proof the venue has no other markets.</p>' +
        '<div class="table-scroll"><table class="data"><thead><tr><th scope="col">Source</th><th scope="col">Result</th><th scope="col">Scope</th><th scope="col">Query / checked</th></tr></thead><tbody>' + obs.checks.map(function (c) {
          return '<tr><td><strong>' + esc(c.source) + '</strong></td><td>' + badge(c.status) + '<br><span class="small">' + esc(c.detail) + '</span></td><td class="small">' + esc(c.scope) + ' (' + esc(c.records_checked) + ' checked)</td><td class="small">' + link(c.url, "Query ↗") + '<br>' + utc(c.checked_utc) + '</td></tr>';
        }).join("") + '</tbody></table></div>' + alerts;
    }));
  }
  function changes(el) {
    show(el, Promise.all([load("roster_changes"), load("observations"), load("teams")]).then(function (all) {
      var moves = all[0], obs = all[1], teamNames = Object.create(null);
      all[2].forEach(function (t) { teamNames[t.id] = t.name; });
      var verified = moves.slice().reverse().map(function (r) {
        return '<article class="change-item"><p>' + badge("verified") + ' <strong>' + esc(teamNames[r.team_id] || r.team_id) + ': ' + esc(r.player) + ' — ' + esc(r.kind) + '</strong></p><p>' + esc(r.fact) + '</p><p class="muted small">Impact: ' + esc(r.impact) + ' · announced ' + utc(r.published_utc) + ' · checked ' + utc(r.verified_utc) + ' · <a href="master-list.html#' + esc(r.master_list) + '">' + esc(r.master_list) + "</a></p>" + sources(r.sources) + '</article>';
      });
      var signals = obs.roster_signals.map(function (s) {
        return '<li>' + badge("flagged") + ' <strong>' + esc(teamNames[s.team_id] || s.team_id) + '</strong> ' + esc(s.old_snapshot_date) + ' → ' + esc(s.new_snapshot_date) +
          ': out ' + esc(s.removed.join(", ") || "none") + ', in ' + esc(s.added.join(", ") || "none") +
          '. ' + esc(s.note) + ' ' + link(s.old_url, "Older Valve file") + ' · ' + link(s.new_url, "Newer Valve file") + '</li>';
      });
      var snap = obs.vrs_history.length && obs.vrs_history[obs.vrs_history.length - 1];
      if (snap) all[2].forEach(function (team) {
        var ranked = snap.teams.find(function (r) { return r.team_id === team.id; });
        if (!ranked) return;
        var baseline = team.roster.map(function (p) { return p.handle; });
        var missing = ranked.roster.filter(function (p) { return baseline.indexOf(p) === -1; });
        var added = baseline.filter(function (p) { return ranked.roster.indexOf(p) === -1; });
        if (missing.length || added.length) signals.push('<li>' + badge("flagged") + ' <strong>' + esc(team.name) +
          '</strong> · Valve ranked roster dated ' + esc(snap.snapshot_date) + ' differs from Sep 24 event-lineup baseline. Valve-only: ' + esc(missing.join(", ") || "none") +
          '; event-only: ' + esc(added.join(", ") || "none") + '. This is a <em>dated source difference, NOT a confirmed transfer or its date.</em> ' +
          link(snap.url, "Valve file ↗") + ' · ' + link(team.sources[0].url, "Event lineup ↗") + '</li>');
      });
      el.innerHTML = '<h3>Verified team announcements</h3>' + (verified.join("") || '<p>No independently confirmed announcement entries yet; absence is not a claim of no moves.</p>') +
        '<h3>Dated ranking-roster differences (analysis / flags)</h3>' + (signals.length ? '<ul class="signal-list">' + signals.join("") + '</ul>' : '<p class="muted">No differences in the stored snapshots. This does NOT mean rosters stayed unchanged.</p>');
    }));
  }
  function feed(el) {
    show(el, Promise.all([load("master_list"), load("roster_changes"), load("observations")]).then(function (all) {
      var changeRefs = all[1].map(function (r) { return r.master_list; });
      var entries = all[0].filter(function (m) { return changeRefs.indexOf(m.id) === -1; }).map(function (m) {
        return { date: m.verified_utc, html: badge(m.status) + ' <strong>' + esc(m.claim) + '</strong> <span class="muted small">' + esc(m.id) + ' · checked ' + utc(m.verified_utc) + '</span> ' + link(m.sources[0].url, "Source ↗") };
      });
      all[1].forEach(function (r) {
        entries.push({ date: r.verified_utc, html: badge("verified") + ' <strong>' + esc(r.player) + ' — ' + esc(r.kind) + '</strong> <span class="muted small">announced ' + utc(r.published_utc) + ' · checked ' + utc(r.verified_utc) + '</span> ' + link(r.sources[0].url, "Team statement ↗") });
      });
      all[2].events.forEach(function (e) {
        entries.push({ date: e.first_seen_utc, html: badge(e.status === "closed" ? "tbd" : "ok") + ' <strong>' + esc(e.title) + '</strong> <span class="muted small">' + esc(e.venue) + ' · ' + esc(e.status) + ' · detected ' + utc(e.first_seen_utc) + '</span> ' + link(e.source_url, "Market API ↗") });
      });
      all[2].vrs_history.forEach(function (snapshot) {
        entries.push({ date: snapshot.observed_utc, html: badge("ok") + ' <strong>Valve Global VRS snapshot dated ' + esc(snapshot.snapshot_date) + '</strong> <span class="muted small">captured ' + utc(snapshot.observed_utc) + ' · ranked five ≠ current event lineup</span> ' + link(snapshot.url, "Valve file ↗") });
      });
      all[2].roster_signals.forEach(function (signal) {
        var relevant = all[2].vrs_history.find(function (snapshot) { return snapshot.snapshot_date === signal.new_snapshot_date; });
        entries.push({ date: relevant ? relevant.observed_utc : all[2].last_completed_utc, html: badge("flagged") + ' <strong>' + esc(signal.team_id) + ' ranking-roster difference: ' + esc(signal.old_snapshot_date) + ' → ' + esc(signal.new_snapshot_date) + '</strong> <span class="muted small">not a verified transfer</span> ' + link(signal.new_url, "Valve file ↗") });
      });
      all[2].alerts.forEach(function (issue) {
        entries.push({ date: all[2].last_completed_utc, html: badge("flagged") + ' <strong>Collector irregularity:</strong> ' + esc(issue.message) + (issue.source_url ? ' ' + link(issue.source_url, "Review ↗") : "") });
      });
      var limit = Math.min(20, Number(el.getAttribute("data-limit")) || 6);
      entries.sort(function (a, b) { return b.date.localeCompare(a.date); });
      el.innerHTML = '<ul class="signal-list">' + entries.slice(0, limit).map(function (e) { return '<li>' + e.html + '</li>'; }).join("") + '</ul><p class="small muted">Different dates mean different things: published, detected, or last verified. Older facts do not automatically become current facts.</p>';
    }));
  }

  function standings(strategies, ledger) {
    return strategies.map(function (s) {
      var mine = (ledger.entries || []).filter(function (e) { return e.username === s.username; });
      var done = mine.filter(function (e) { return e.settlement && ["win", "loss", "void", "partial"].indexOf(e.settlement.result) !== -1; });
      var open = mine.filter(function (e) { return e.settlement && e.settlement.result === "pending"; });
      var staked = done.reduce(function (a, e) { return a + Number(e.stake); }, 0);
      var locked = open.reduce(function (a, e) { return a + Number(e.stake); }, 0);
      var pnl = done.reduce(function (a, e) { return a + Number(e.profit); }, 0);
      var start = Number(s.bankroll_start);
      return { username: s.username, strategy: s.strategy, status: s.status, settled: done.length,
        open: open.length, wins: done.filter(function (e) { return e.settlement.result === "win"; }).length,
        staked: staked, locked: locked, pnl: pnl, bankroll: start + pnl,
        available: start + pnl - locked, roi: staked ? pnl / staked * 100 : null };
    }).sort(function (a, b) { return b.bankroll - a.bankroll || a.username.localeCompare(b.username); });
  }
  function leaderboard(el) {
    show(el, Promise.all([load("strategies"), load("ledger")]).then(function (pair) {
      var rows = standings(pair[0], pair[1]);
      el.innerHTML = '<div class="notice"><strong>100% simulated.</strong> Rank uses settled P/L only (T1 = tied for first); pending positions lock units but have no realized P/L. No real order, guaranteed fill, or fee-adjusted return is claimed.</div>' +
        '<div class="table-scroll"><table class="data"><thead><tr><th scope="col">Rank</th><th scope="col">User / policy</th><th scope="col">Settled / open</th><th scope="col">Wins</th><th scope="col">Settled stake / locked</th><th scope="col">Realized P/L</th><th scope="col">ROI</th><th scope="col">Realized / available units</th></tr></thead><tbody>' + rows.map(function (r, i) {
          var rank = 1 + rows.filter(function (other) { return other.bankroll > r.bankroll; }).length;
          var tied = rows.some(function (other, j) { return j !== i && other.bankroll === r.bankroll; });
          return '<tr><td>' + (tied ? "T" : "#") + rank + '</td><td><span class="mono">' + esc(r.username) + '</span> ' + badge(r.status) + '<br><span class="small">' + esc(r.strategy) + '</span></td><td>' + r.settled + ' / ' + r.open + '</td><td>' + r.wins + '</td><td>' + fmt(r.staked) + ' / ' + fmt(r.locked) + '</td><td class="' + (r.pnl < 0 ? "negative" : "") + '">' + (r.pnl >= 0 ? "+" : "") + fmt(r.pnl) + '</td><td>' + (r.roi === null ? '—' : fmt(r.roi) + '%') + '</td><td><strong>' + fmt(r.bankroll) + '</strong> / ' + fmt(r.available) + '</td></tr>';
        }).join("") + '</tbody></table></div>';
      document.querySelectorAll("[data-ledger-meta]").forEach(function (meta) {
        meta.textContent = "Ledger: " + pair[1].entries.length + " paper decision(s) · last changed " + pair[1].meta.last_updated_utc + " · " + pair[1].meta.currency;
      });
    }));
  }
  function strategies(el) {
    show(el, load("strategies").then(function (items) {
      el.innerHTML = items.map(function (s) {
        return '<article class="card"><h3 class="mono">' + esc(s.username) + ' <span class="badge sim">SIMULATED</span> ' + badge(s.status) + '</h3><p><strong>' + esc(s.strategy) + '.</strong> ' + esc(s.description) + '</p><ol class="small">' + s.rules.map(function (r) { return '<li>' + esc(r) + '</li>'; }).join("") + '</ol><p class="small"><strong>Starting units:</strong> ' + fmt(s.bankroll_start) + '</p><p class="muted small">' + esc(s.notes) + '</p></article>';
      }).join("");
    }));
  }
  function ledger(el) {
    show(el, Promise.all([load("ledger"), load("settlements").catch(function () { return null; })]).then(function (pair) {
      var book = pair[0], journal = pair[1];
      var html = '<div class="notice"><strong>' + esc(book.meta.currency) + '.</strong> ' + esc(book.meta.settlement_policy) + '</div><p class="small muted">Gross math: ' + esc(book.meta.payout_formula) + ' ' + esc(book.meta.prediction_share_conversion) + '</p>';
      var receipts = "";
      if (journal && journal.rows && journal.rows.length) {
        var kindLabel = { venue_resolution: "Venue resolution receipt", result_confirmation: "Independent result confirmation",
                          settlement_decision: "Settlement decision applied", settlement_hold: "Settlement held — stays pending" };
        receipts = '<h3>Settlement journal (append-only, SHA-256 chained)</h3><p class="small muted">' + journal.rows.length +
          ' receipt(s); chain head <span class="mono">' + esc(String(journal.chain_head || "").slice(0, 16)) + '…</span>. Any edit or deletion of an old receipt breaks the chain and fails validation. Void is never assumed: canceled/unresolved venues stay pending.</p><ul class="signal-list">' +
          journal.rows.slice().reverse().slice(0, 12).map(function (r) {
            return '<li>' + badge(r.kind === "settlement_decision" ? "ok" : (r.kind === "settlement_hold" ? "flagged" : "tbd")) +
              ' <strong>' + esc(kindLabel[r.kind] || r.kind) + '</strong>' + (r.venue ? ' · ' + esc(r.venue) : '') +
              ' <span class="small muted">entry <span class="mono">' + esc(r.entry_id) + '</span> · recorded ' + utc(r.recorded_utc) +
              ' · receipt <span class="mono">' + esc(String(r.receipt_id).slice(0, 12)) + '…</span></span>' +
              (r.note ? '<br><span class="small muted">' + esc(r.note) + '</span>' : '') +
              (r.source_url ? ' ' + link(r.source_url, "Source ↗") : '') + '</li>';
          }).join("") + '</ul>';
      } else {
        receipts = '<h3>Settlement journal</h3><p class="small muted">No receipts yet: no position has reached a venue resolution. Empty is not settled.</p>';
      }
      if (!book.entries.length) {
        el.innerHTML = html + '<div class="notice warn"><strong>No simulated positions yet.</strong> ' + esc(book.meta.note) + ' A paper position can only be made forward at a timestamped first-party ask with enough size, never from a settled price. <a href="markets.html">Inspect the market discovery checks →</a></div>' + receipts;
        return;
      }
      el.innerHTML = html + '<div class="table-scroll"><table class="data"><thead><tr><th scope="col">Decision ID / SIM user</th><th scope="col">Event / selection</th><th scope="col">Exact paper amount &amp; line</th><th scope="col">Pricing receipt</th><th scope="col">Outcome &amp; settlement</th></tr></thead><tbody>' + book.entries.map(function (e) {
        var p = e.price_source, s = e.settlement;
        return '<tr><td class="mono">' + esc(e.entry_id) + '<br>' + esc(e.username) + '</td><td>' + esc(e.market) + '<br><strong>' + esc(e.selection) + '</strong><br><span class="small mono">' + esc(e.event_key) + ' · ' + esc(e.match_id) + '</span>' + (e.fixture ? '<br><span class="small muted">cross-checked fixture ' + esc(e.fixture.scheduled_utc) + ' · ' + esc(e.fixture.crosscheck && e.fixture.crosscheck.fixture_status) + '</span>' : '') + '</td><td>' + esc(e.stake) + ' SIM units at best ask $' + esc(p.raw_price) + '<br>gross 1/p = ' + esc(e.decimal_odds) + '<br>size ' + esc(p.ask_size) + '</td><td class="small">' + esc(p.venue) + '<br>' + esc(p.market_id) + '<br>observed ' + utc(p.observed_utc) + '<br>exchange book time ' + utc(p.source_updated_utc) + '<br>' + link(p.url, "Original API quote ↗") + '<br>' + link(p.event_url, "Market event ↗") + '<br><span class="muted mono">quote ' + esc(p.quote_id) + '</span><details><summary>Paper fill policy</summary>' + esc(e.fill_policy) + '</details></td><td>' + badge(s.result) + '<br>Payout: ' + (e.payout === null ? 'pending' : esc(e.payout)) + '<br>P/L: ' + (e.profit === null ? 'pending' : esc(e.profit)) + (s.payout_fraction ? '<br>venue payout fraction ' + esc(s.payout_fraction) : '') + '<details><summary>Exact market settlement rule</summary><div class="rule-text">' + esc(s.rule) + '</div></details>' + (s.result_source ? sources(s.result_source) : '') + '</td></tr>';
      }).join("") + '</tbody></table></div>' + receipts;
    }));
  }

  function archiveStatus(el) {
    show(el, load("archive_manifest").then(function (m) {
      var files = Object.keys(m.files || {}).map(function (name) {
        return '<li><span class="mono">' + esc(name) + '</span> — SHA-256 <span class="mono small">' + esc(m.files[name]) + '</span></li>';
      }).join("");
      el.innerHTML = '<div class="notice"><strong>Long-term archive is versioned.</strong> Every successful publication run commits the full journal to the <span class="mono">journal-archive</span> git branch (one commit per run, outliving 30-day Actions artifacts) with this manifest.</div>' +
        '<p class="small">Snapshot from run <span class="mono">' + esc(m.run_id || "local") + '</span> at ' + utc(m.created_utc) +
        ' · journal mode ' + esc((m.journal && m.journal.mode) || "?") + ' · last attempt ' + utc(m.journal && m.journal.last_attempt_utc) +
        ' · ' + esc(m.settlement_rows || 0) + ' chained settlement receipts (head <span class="mono">' + esc(String(m.settlement_chain_head || "").slice(0, 16)) + '…</span>)</p>' +
        '<ul class="signal-list">' + files + '</ul>' +
        '<p class="small muted">A stalled hourly job alerts through the watchdog workflow (a failing scheduled run). The site also flags the feed as stale after 2 hours above.</p>';
    }));
  }

  function backtestLeaderboard(el) {
    show(el, load("backtest_results").then(function (data) {
      var rows = data.strategies || [];
      el.innerHTML = '<div class="table-scroll"><table class="data"><thead><tr><th scope="col">Rank</th><th scope="col">User / policy</th><th scope="col">Bets</th><th scope="col">W-L</th><th scope="col">Win%</th><th scope="col">Staked</th><th scope="col">P/L</th><th scope="col">ROI</th><th scope="col">Bankroll</th></tr></thead><tbody>' +
        rows.map(function (r, i) {
          var rank = i + 1;
          return '<tr><td>#' + rank + '</td><td><span class="mono">' + esc(r.username) + '</span> ' + badge(r.status) + '<br><span class="small">' + esc(r.strategy) + '</span></td>' +
            '<td>' + esc(r.total_bets) + '</td><td>' + esc(r.wins) + '-' + esc(r.losses) + '</td>' +
            '<td>' + (r.win_rate === null ? '—' : fmt(r.win_rate) + '%') + '</td>' +
            '<td>' + fmt(r.staked) + '</td>' +
            '<td class="' + (r.profit < 0 ? 'negative' : '') + '">' + (r.profit >=0 ? '+' : '') + fmt(r.profit) + '</td>' +
            '<td>' + (r.roi === null ? '—' : fmt(r.roi) + '%') + '</td>' +
            '<td><strong>' + fmt(r.bankroll) + '</strong></td></tr>';
        }).join("") + '</tbody></table></div>' +
        '<p class="small muted">Generated ' + utc(data.meta.generated_utc) + ' · ' + esc(data.meta.matches_count) + ' matches · ' + esc(data.meta.ledger_entries) + ' simulated bets · ' + esc(data.meta.currency) + '</p>';
      document.querySelectorAll("[data-backtest-matches]").forEach(function (e) { e.textContent = data.meta.matches_count; });
      document.querySelectorAll("[data-backtest-bets]").forEach(function (e) { e.textContent = data.meta.ledger_entries; });
      document.querySelectorAll("[data-backtest-meta]").forEach(function (e) { e.textContent = 'Generated ' + data.meta.generated_utc; });
    }));
  }
  function backtestAnalytics(el) {
    show(el, load("backtest_results").then(function (data) {
      var a = data.analytics || {};
      var vrs = a.vrs_ranks_used || {};
      var vrsRows = Object.keys(vrs).map(function (k) { return '<li><span class="mono">' + esc(k) + '</span> VRS #' + esc(vrs[k]) + '</li>'; }).join("");
      el.innerHTML = '<div class="grid-2"><div><h3>Coverage</h3><ul class="small"><li>Total matches: ' + esc(a.total_matches) + '</li><li>Inter-finalist: ' + esc(a.inter_finalist_matches) + '</li><li>Range: ' + utc(a.date_range && a.date_range.earliest) + ' → ' + utc(a.date_range && a.date_range.latest) + '</li></ul><h3>VRS ranks used (ML-008)</h3><ul class="small">' + vrsRows + '</ul></div>' +
        '<div><h3>Odds policy</h3><p class="small">' + esc(a.odds_policy && a.odds_policy.description) + '</p><p class="small mono">' + esc(a.odds_policy && a.odds_policy.formula) + '</p><p class="small muted">' + esc(a.note) + '</p></div></div>';
    }));
  }
  function backtestLedger(el) {
    show(el, load("backtest_ledger").then(function (data) {
      var entries = data.entries || [];
      if (!entries.length) {
        el.innerHTML = '<div class="notice">No backtest bets yet.</div>';
        return;
      }
      el.innerHTML = '<div class="table-scroll"><table class="data"><thead><tr><th>Date</th><th>Match</th><th>Pick / odds / stake</th><th>Result / P/L</th><th>Reason &amp; source</th></tr></thead><tbody>' +
        entries.slice().reverse().slice(0,100).map(function (e) {
          return '<tr><td class="small mono">' + utc(e.date) + '<br>' + esc(e.match_id) + '</td>' +
            '<td><strong>' + esc(e.team_a_name) + ' vs ' + esc(e.team_b_name) + '</strong><br><span class="small muted">' + esc(e.event) + ' · winner ' + esc(e.winner_name) + ' ' + esc(e.score || '') + '</span></td>' +
            '<td><span class="mono">' + esc(e.username) + '</span><br><strong>' + esc(e.pick_name) + '</strong> @ ' + esc(e.decimal_odds) + '<br>' + esc(e.stake) + ' units · ' + badge(e.odds_type === 'MODELED' ? 'sim' : 'verified') + ' ' + esc(e.odds_type) + '<br><span class="small muted">' + esc(e.odds_detail) + '</span></td>' +
            '<td>' + badge(e.result) + '<br><span class="' + (e.profit <0 ? 'negative' : '') + '">' + (e.profit>=0?'+':'') + fmt(e.profit) + '</span><br><span class="small">fair ' + esc(JSON.stringify(e.fair_probs)) + '<br>market ' + esc(JSON.stringify(e.market_implied)) + '</span></td>' +
            '<td class="small">' + esc(e.reason) + '<br>' + sources(e.sources) + '</td></tr>';
        }).join("") + '</tbody></table></div>' +
        '<p class="small muted">Showing latest 100 of ' + entries.length + ' simulated bets. Full JSON in data/backtest_ledger.json for strategy building.</p>';
    }));
  }
  function historicalMatches(el) {
    show(el, load("historical_matches").then(function (items) {
      el.innerHTML = '<div class="table-scroll"><table class="data"><thead><tr><th>ID / date</th><th>Event</th><th>Match</th><th>Winner / score</th><th>Sources</th></tr></thead><tbody>' +
        items.slice().sort(function (a,b){return b.date.localeCompare(a.date);}).map(function (m) {
          return '<tr><td class="mono">' + esc(m.id) + '<br>' + utc(m.date) + '</td>' +
            '<td>' + esc(m.event) + '<br><span class="small muted">' + esc(m.stage) + '</span></td>' +
            '<td><strong>' + esc(m.team_a_name || m.team_a) + ' vs ' + esc(m.team_b_name || m.team_b) + '</strong></td>' +
            '<td>' + badge("verified") + ' <strong>' + esc(m.winner_name || m.winner) + '</strong><br>' + esc(m.score) + (m.map_scores ? '<br><span class="small">' + m.map_scores.map(function (ms){return esc(ms.join(" "));}).join(", ") + '</span>' : '') + '</td>' +
            '<td class="small">' + sources(m.sources) + '<p class="small muted">' + esc(m.notes || '') + '</p></td></tr>';
        }).join("") + '</tbody></table></div>';
    }));
  }


  /* ---- Real-line strategy lab (data/lab/*.json, built by scripts/strategy_lab.py) ---- */
  function pct(x) { return x === null || x === undefined ? "—" : (x * 100).toFixed(1) + "%"; }
  function num(x, d) { return x === null || x === undefined ? "—" : Number(x).toFixed(d); }
  function isoTime(t) { return new Date(t * 1000).toISOString().replace(".000Z", "Z"); }
  function spark(points, start) {
    if (!Array.isArray(points) || points.length < 2) return '<span class="muted small">no bets</span>';
    var all = points.concat([start]), min = Math.min.apply(null, all), max = Math.max.apply(null, all);
    var span = max - min || 1, w = 90, h = 24;
    var d = points.map(function (v, i) { return (i * w / (points.length - 1)).toFixed(1) + "," + (h - (v - min) / span * h).toFixed(1); }).join(" ");
    var base = (h - (start - min) / span * h).toFixed(1);
    return '<svg class="spark" viewBox="0 0 90 24" width="90" height="24" role="img" aria-label="Equity curve, ' + esc(points[0]) + ' to ' + esc(points[points.length - 1]) + ' units">' +
      '<line x1="0" x2="90" y1="' + base + '" y2="' + base + '" class="spark-base"></line>' +
      '<polyline points="' + d + '" class="' + (points[points.length - 1] >= start ? "spark-up" : "spark-down") + '"></polyline></svg>';
  }
  function options(values, label) {
    return '<option value="">All ' + esc(label) + '</option>' + values.map(function (v) { return '<option value="' + esc(v) + '">' + esc(v) + '</option>'; }).join("");
  }
  function labFacts(a) {
    var d = a.dataset || {}, x = a.distinctness || {};
    var facts = {
      lines: (d.lines_total || 0) + " (" + Object.keys(d.lines_by_venue || {}).map(function (k) { return k + " " + d.lines_by_venue[k]; }).join(" · ") + ")",
      matches: String(d.matches_simulated || 0), range: d.first_cutoff_utc ? d.first_cutoff_utc.slice(0, 10) + " → " + d.last_cutoff_utc.slice(0, 10) : "not collected yet",
      strategies: String(x.strategy_definitions || 0), selections: String(x.unique_bet_selection_sets || 0) + " / " + String(x.unique_ledgers_incl_stakes || 0),
      qualified: String(x.qualified || 0), updated: a.generated_from_lines_run_utc || "never"
    };
    document.querySelectorAll("[data-lab-fact]").forEach(function (node) { node.textContent = facts[node.getAttribute("data-lab-fact")] || "—"; });
  }
  function labLeaderboard(el) {
    show(el, Promise.all([load("lab/leaderboard"), load("lab/strategies")]).then(function (pair) {
      var board = pair[0], rules = {}, start = board.start_bankroll || 1000;
      pair[1].strategies.forEach(function (s) { rules[s.id] = s; });
      var rows = board.rows || [];
      if (!rows.length) { el.innerHTML = '<div class="notice warn">No strategies yet.</div>'; return; }
      var uniq = function (key) { return rows.map(function (r) { return r[key]; }).filter(function (v, i, arr) { return arr.indexOf(v) === i; }).sort(); };
      var anyQualified = rows.some(function (r) { return r.qualified; });
      var state = { family: "", venue: "", checkpoint: "", stake: "", q: "", qualified: anyQualified, sort: "bankroll", limit: 50 };
      var sorters = {
        bankroll: function (r) { return -r.all.final_bankroll; }, roi: function (r) { return -(r.all.roi === null ? -9 : r.all.roi); },
        test_roi: function (r) { return -(r.test.roi === null ? -9 : r.test.roi); }, clv: function (r) { return -(r.all.avg_clv === null ? -9 : r.all.avg_clv); },
        bets: function (r) { return -r.all.bets; }, p: function (r) { return r.all.p_value === null ? 9 : r.all.p_value; },
        drawdown: function (r) { return r.all.max_drawdown === undefined || r.all.max_drawdown === null ? 9 : r.all.max_drawdown; }
      };
      el.innerHTML = '<div class="lab-controls" role="group" aria-label="Filter strategies">' +
        '<label>Family <select data-f="family">' + options(uniq("family"), "families") + '</select></label>' +
        '<label>Venue <select data-f="venue">' + options(uniq("venue"), "venues") + '</select></label>' +
        '<label>Checkpoint <select data-f="checkpoint">' + options(uniq("checkpoint"), "checkpoints") + '</select></label>' +
        '<label>Staking <select data-f="stake">' + options(uniq("stake"), "staking") + '</select></label>' +
        '<label>Sort <select data-f="sort"><option value="bankroll">Final bankroll</option><option value="roi">ROI (all)</option><option value="test_roi">Out-of-sample ROI</option><option value="clv">Avg closing-line value</option><option value="p">p-value vs price</option><option value="drawdown">Smallest drawdown</option><option value="bets">Most bets</option></select></label>' +
        '<label>Search <input type="search" data-f="q" placeholder="user, S0123, rule text"></label>' +
        '<label class="check"><input type="checkbox" data-f="qualified"' + (anyQualified ? ' checked' : '') + '> Qualified only (≥' + esc(board.qualify_bets) + ' bets)</label></div>' +
        (anyQualified ? '' : '<div class="notice warn"><strong>No strategy has ' + esc(board.qualify_bets) + '+ bets yet.</strong> The real-line collector has not stored enough settled matches; ranks are provisional (all users start at ' + esc(start) + ' units).</div>') +
        '<div data-lab-table></div><div data-lab-ledger></div>';
      var tableEl = el.querySelector ? el.querySelector("[data-lab-table]") : null;
      var ledgerEl = el.querySelector ? el.querySelector("[data-lab-ledger]") : null;
      function draw() {
        var q = state.q.toLowerCase();
        var list = rows.filter(function (r) {
          return (!state.family || r.family === state.family) && (!state.venue || r.venue === state.venue) &&
            (!state.checkpoint || r.checkpoint === state.checkpoint) && (!state.stake || r.stake === state.stake) &&
            (!state.qualified || r.qualified) &&
            (!q || (r.id + " " + r.username + " " + ((rules[r.id] || {}).rule || "")).toLowerCase().indexOf(q) !== -1);
        });
        var key = sorters[state.sort] || sorters.bankroll;
        list.sort(function (a, b) { return key(a) - key(b) || a.rank - b.rank; });
        var html = '<p class="small muted">' + list.length + ' of ' + rows.length + ' simulated strategies match. Rank = competition rank by final bankroll across all strategies.</p>' +
          '<div class="table-scroll"><table class="data lab-table"><thead><tr><th scope="col">Rank</th><th scope="col">Simulated user / rule</th><th scope="col">Bets (W-L)</th><th scope="col">ROI</th><th scope="col" title="Out-of-sample: last 30% of matches by date">Test ROI</th><th scope="col" title="Average (T-0 buy price − entry price)">CLV</th><th scope="col" title="One-sided p-value of P/L vs the entry prices themselves">p</th><th scope="col">Max DD</th><th scope="col">Bankroll</th><th scope="col">Curve</th><th scope="col">Ledger</th></tr></thead><tbody>' +
          list.slice(0, state.limit).map(function (r) {
            var a = r.all, s = rules[r.id] || {};
            return '<tr><td>#' + esc(r.rank) + (r.qualified ? '' : '<br><span class="badge tbd">&lt;' + esc(board.qualify_bets) + '</span>') + '</td>' +
              '<td><span class="mono">' + esc(r.username) + '</span> <span class="badge sim">SIM</span> <span class="small muted mono">' + esc(r.id) + ' · ' + esc(r.family) + '</span><br><span class="small">' + esc(s.rule) + '</span></td>' +
              '<td>' + esc(a.bets) + '<br><span class="small muted">' + esc(a.wins) + '-' + esc(a.losses) + '</span></td>' +
              '<td class="' + (a.roi < 0 ? 'negative' : '') + '">' + pct(a.roi) + '</td>' +
              '<td class="' + (r.test.roi < 0 ? 'negative' : '') + '">' + pct(r.test.roi) + '<br><span class="small muted">' + esc(r.test.bets) + ' bets</span></td>' +
              '<td>' + num(a.avg_clv, 3) + '</td><td>' + num(a.p_value, 4) + '</td><td>' + pct(a.max_drawdown) + '</td>' +
              '<td><strong>' + fmt(a.final_bankroll) + '</strong></td><td>' + spark(r.spark, start) + '</td>' +
              '<td>' + (r.ledger_published ? '<button type="button" class="btn-small" data-ledger="' + esc(r.id) + '">View bets</button>' : '<span class="small muted">CLI: <span class="mono">--ledger ' + esc(r.id) + '</span></span>') + '</td></tr>';
          }).join("") + '</tbody></table></div>' +
          (list.length > state.limit ? '<p><button type="button" class="btn-small" data-more>Show 50 more</button></p>' : '');
        if (tableEl) tableEl.innerHTML = html; else el.innerHTML += html;
      }
      function ledger(sid) {
        if (!ledgerEl) return;
        ledgerEl.innerHTML = '<p class="muted">Loading ledger ' + esc(sid) + '…</p>';
        Promise.all([load("lab/matches"), load("lab/ledgers/" + sid)]).then(function (pair) {
          var table = pair[0].matches, led = pair[1], col = {};
          led.columns.forEach(function (c, i) { col[c] = i; });
          var s = rules[sid] || {};
          ledgerEl.innerHTML = '<h3 id="lab-ledger-title">Every bet of <span class="mono">' + esc(s.username) + '</span> (' + esc(sid) + ') <span class="badge sim">SIMULATED</span></h3><p class="small">' + esc(s.rule) + '</p>' +
            '<div class="table-scroll"><table class="data"><thead><tr><th scope="col">Match (cutoff UTC)</th><th scope="col">Pick</th><th scope="col">Quote used</th><th scope="col">Amount</th><th scope="col">Outcome</th><th scope="col">Equity</th><th scope="col">Receipts</th></tr></thead><tbody>' +
            led.bets.map(function (b) {
              var m = table[b[col.match_idx]], venue = b[col.venue] === "k" ? "kalshi" : "polymarket", line = m.lines[venue] || {};
              var vside = line.side_map ? line.side_map[b[col.side]] : b[col.side];
              return '<tr><td>' + esc(m.teams[0]) + ' vs ' + esc(m.teams[1]) + '<br><span class="small muted">' + esc(m.competition) + (m.format ? ' · ' + esc(m.format) : '') + ' · ' + esc(m.cutoff_utc) + (m.cross_checked ? ' · results cross-checked on both venues' : '') + '</span></td>' +
                '<td><strong>' + esc(m.teams[b[col.side]]) + '</strong></td>' +
                '<td>' + esc(venue) + ' ' + (venue === "kalshi" ? 'ask' : 'ref+1c') + ' <strong>' + num(b[col.price], 4) + '</strong><br><span class="small muted">quote ' + esc(isoTime(b[col.quote_t])) + '</span>' + (b[col.model_prob] !== null ? '<br><span class="small">model ' + num(b[col.model_prob], 3) + '</span>' : '') + '</td>' +
                '<td>' + esc(b[col.contracts]) + ' × ' + num(b[col.price], 4) + ' = ' + num(b[col.cost], 2) + '<br><span class="small muted">fee ' + num(b[col.fee], 4) + '</span></td>' +
                '<td>' + (b[col.settle] === 1 ? badge("win") : b[col.settle] === 0 ? badge("loss") : badge("partial")) + ' settle ' + esc(b[col.settle]) + '<br>P/L <span class="' + (b[col.pnl] < 0 ? 'negative' : '') + '">' + num(b[col.pnl], 2) + '</span><br><span class="small muted">settled ' + esc(m.settled_utc) + '</span></td>' +
                '<td>' + num(b[col.equity_after_settle], 2) + '</td>' +
                '<td class="small">' + link((line.price_urls || [])[vside], "Price history ↗") + '<br>' + link(line.review_url, "Market page ↗") + '</td></tr>';
            }).join("") + '</tbody></table></div><p class="small muted">Equity = cash plus open positions at cost, recorded when the bet settled. Receipts are the exact free public API queries the quote was read from.</p>';
        }).catch(function (error) {
          ledgerEl.innerHTML = '<div class="error-box" role="alert"><strong>Ledger unavailable.</strong> Ledgers are generated at deploy time (run <span class="mono">python3 -m scripts.strategy_lab</span> locally). ' + esc(error && error.message ? error.message : error) + '</div>';
        });
      }
      if (el.addEventListener) {
        var update = function (event) {
          var f = event.target.getAttribute && event.target.getAttribute("data-f");
          if (!f) return;
          state[f] = event.target.type === "checkbox" ? event.target.checked : event.target.value;
          state.limit = 50;
          draw();
        };
        el.addEventListener("change", update);
        el.addEventListener("input", update);
        el.addEventListener("click", function (event) {
          var t = event.target;
          if (t.hasAttribute && t.hasAttribute("data-more")) { state.limit += 50; draw(); }
          var sid = t.getAttribute && t.getAttribute("data-ledger");
          if (sid) { ledger(sid); if (ledgerEl.scrollIntoView) ledgerEl.scrollIntoView({ behavior: "smooth" }); }
        });
      }
      draw();
    }));
  }
  function groupTable(title, list) {
    return '<h3>' + esc(title) + '</h3><div class="table-scroll"><table class="data"><thead><tr><th scope="col">Group</th><th scope="col">Strategies (qualified)</th><th scope="col">Median ROI</th><th scope="col">Best ROI</th><th scope="col">Share profitable</th><th scope="col">Median test ROI</th></tr></thead><tbody>' +
      (list || []).map(function (g) {
        return '<tr><td class="mono">' + esc(g.group) + '</td><td>' + esc(g.strategies) + ' (' + esc(g.qualified) + ')</td><td>' + pct(g.median_roi) + '</td><td>' + pct(g.best_roi) + '</td><td>' + pct(g.share_profitable) + '</td><td>' + pct(g.median_test_roi) + '</td></tr>';
      }).join("") + '</tbody></table></div>';
  }
  function labAnalytics(el) {
    show(el, load("lab/analytics").then(function (a) {
      labFacts(a);
      var d = a.dataset || {}, x = a.distinctness || {}, mt = a.multiple_testing || {}, oos = a.out_of_sample || {};
      var cal = (a.calibration || []).filter(function (c) { return c.checkpoint === "T-1h" || c.checkpoint === "T-0"; });
      el.innerHTML = '<div class="grid-2"><div><h3>Dataset</h3><ul class="small">' +
        '<li>Real lines stored: ' + esc(d.lines_total) + ' · matches simulated: ' + esc(d.matches_simulated) + ' (' + esc(d.matches_cross_venue) + ' on both venues, ' + esc(d.matches_cross_checked_results) + ' results cross-checked)</li>' +
        '<li>Range: ' + utc(d.first_cutoff_utc) + ' → ' + utc(d.last_cutoff_utc) + ' · train/test split ' + utc(d.train_test_split_utc) + '</li>' +
        '<li>Venue result conflicts excluded: ' + esc(d.venue_result_conflicts) + ' · late cross-venue quotes dropped: ' + esc(d.quotes_dropped_after_match_cutoff) + '</li></ul>' +
        '<h3>Distinct strategies</h3><ul class="small"><li>' + esc(x.strategy_definitions) + ' unique definitions (' + esc(x.unique_definition_hashes) + ' hashes)</li><li>' + esc(x.unique_bet_selection_sets) + ' distinct sets of bets · ' + esc(x.unique_ledgers_incl_stakes) + ' distinct ledgers including stakes</li><li>' + esc(x.qualified) + ' qualified with ≥' + esc(x.qualified_strategies_min_bets) + ' bets</li></ul></div>' +
        '<div><h3>Is any of it real skill?</h3><ul class="small"><li>' + esc(mt.p_below_0_05) + ' of ' + esc(mt.tested) + ' strategies have p &lt; 0.05 — about ' + esc(mt.expected_false_positives_at_0_05) + ' would by pure chance.</li>' +
        '<li>Bonferroni survivors (p &lt; ' + num(mt.bonferroni_threshold, 6) + '): <strong>' + esc(mt.pass_bonferroni) + '</strong></li>' +
        '<li>Train→test ROI rank correlation (Spearman): <strong>' + num(oos.spearman_train_vs_test_roi, 3) + '</strong> over ' + esc(oos.pairs) + ' strategies</li>' +
        '<li>Top 20 by in-sample ROI: ' + pct(oos.top20_by_train_roi_mean_train) + ' in-sample → <strong>' + pct(oos.top20_by_train_roi_mean_test) + '</strong> out-of-sample</li></ul>' +
        '<p class="small muted">' + esc(mt.note) + '</p></div></div>' +
        '<h3>Market calibration (T-1h and T-0)</h3><p class="small muted">Do prices mean what they say? Win rate by implied-probability bucket, and flat-stake ROI after the documented fees for backing every side in that bucket.</p>' +
        '<div class="table-scroll"><table class="data"><thead><tr><th scope="col">Venue</th><th scope="col">Checkpoint</th><th scope="col">Implied bucket</th><th scope="col">n</th><th scope="col">Avg implied</th><th scope="col">Win rate</th><th scope="col">Avg buy</th><th scope="col">Flat ROI after fees</th></tr></thead><tbody>' +
        cal.map(function (c) { return '<tr><td>' + esc(c.venue) + '</td><td>' + esc(c.checkpoint) + '</td><td>' + esc(c.bucket) + '</td><td>' + esc(c.n) + '</td><td>' + num(c.avg_implied, 3) + '</td><td>' + num(c.win_rate, 3) + '</td><td>' + num(c.avg_buy, 3) + '</td><td class="' + (c.flat_roi_after_fees < 0 ? 'negative' : '') + '">' + pct(c.flat_roi_after_fees) + '</td></tr>'; }).join("") + '</tbody></table></div>' +
        groupTable("By strategy family", a.by_family) + groupTable("By venue", a.by_venue) + groupTable("By decision checkpoint", a.by_checkpoint) + groupTable("By staking method", a.by_stake) +
        '<h3>Irregularities flagged for review (' + esc(a.irregularities_total) + ')</h3><ul class="signal-list small">' +
        (a.irregularities || []).slice(0, 40).map(function (i) { return '<li><span class="badge flagged">' + esc(i.type) + '</span> ' + esc(i.line_id || (i.lines || []).join(", ")) + (i.detail ? ' — ' + esc(i.detail) : '') + ' ' + (i.review_urls || []).map(function (u) { return link(u, "review ↗"); }).join(" ") + '</li>'; }).join("") + '</ul>' +
        '<details><summary>Simulation assumptions (read before trusting any number)</summary><ul class="small">' + (a.assumptions || []).map(function (t) { return '<li>' + esc(t) + '</li>'; }).join("") + '</ul></details>';
    }));
  }

  document.addEventListener("DOMContentLoaded", function () {
    var types = { "master-list": masterList, teams: teamCards, "teams-table": teamTable,
      "vrs-snapshot": vrsSnapshot, matches: matches, "fixture-signals": fixtureSignals,
      markets: marketSources, "quote-table": quoteTable, "market-events": marketEvents,
      pulse: pulse, checks: checks, changes: changes, feed: feed,
      leaderboard: leaderboard, strategies: strategies, ledger: ledger,
      "archive-status": archiveStatus,
      "backtest-leaderboard": backtestLeaderboard, "backtest-analytics": backtestAnalytics,
      "backtest-ledger": backtestLedger, "historical-matches": historicalMatches,
      "lab-leaderboard": labLeaderboard, "lab-analytics": labAnalytics };
    document.querySelectorAll("[data-render]").forEach(function (el) {
      var fn = types[el.getAttribute("data-render")];
      if (fn) fn(el);
      else fail(el, "Unknown render target");
    });
    load("observations").then(function (obs) {
      document.querySelectorAll("[data-today]").forEach(function (el) {
        el.textContent = obs.last_completed_utc ? obs.last_completed_utc + (obs.mode === "offline-replay" ? " (offline research replay)" : "") : "not collected";
      });
    }).catch(function () {
      document.querySelectorAll("[data-today]").forEach(function (el) { el.textContent = "unavailable"; });
    });
    load("master_list").then(function (items) {
      document.querySelectorAll("[data-master-count]").forEach(function (el) { el.textContent = String(items.length); });
    }).catch(function () {
      document.querySelectorAll("[data-master-count]").forEach(function (el) { el.textContent = "unavailable"; });
    });
  });
})();
