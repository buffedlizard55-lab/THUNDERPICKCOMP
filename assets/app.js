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

  document.addEventListener("DOMContentLoaded", function () {
    var types = { "master-list": masterList, teams: teamCards, "teams-table": teamTable,
      "vrs-snapshot": vrsSnapshot, matches: matches, "fixture-signals": fixtureSignals,
      markets: marketSources, "quote-table": quoteTable, "market-events": marketEvents,
      pulse: pulse, checks: checks, changes: changes, feed: feed,
      leaderboard: leaderboard, strategies: strategies, ledger: ledger,
      "archive-status": archiveStatus,
      "backtest-leaderboard": backtestLeaderboard, "backtest-analytics": backtestAnalytics,
      "backtest-ledger": backtestLedger, "historical-matches": historicalMatches };
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
