/* THUNDERPICKCOMP — renders verified JSON data into the static pages.
   Single source of truth: /data/*.json. Failures are shown visibly, never silent. */
(function () {
  "use strict";

  function esc(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function badge(status) {
    var map = {
      verified: ["verified", "Verified"],
      flagged: ["flagged", "Verified · flagged"],
      unverified: ["unverified", "Unverified"],
      stale: ["unverified", "Stale"],
      tbd: ["tbd", "TBD"],
      final: ["verified", "Final"],
      scheduled: ["sim", "Scheduled"],
      active: ["sim", "Active"]
    };
    var m = map[status] || ["tbd", status];
    return '<span class="badge ' + m[0] + '">' + esc(m[1]) + "</span>";
  }

  function sourceLinks(sources) {
    if (!sources || !sources.length) return '<span class="muted">No source recorded.</span>';
    var items = sources.map(function (s) {
      var type = s.type ? ' <span class="muted small">(' + esc(s.type) + " · " + esc(s.accessed_utc) + ")</span>" : "";
      return '<li><a href="' + esc(s.url) + '" rel="noopener" target="_blank">' + esc(s.label) + "</a>" + type + "</li>";
    });
    return '<ul class="source-list">' + items.join("") + "</ul>";
  }

  function failVisible(el, err) {
    el.innerHTML = '<div class="error-box" role="alert"><strong>Data failed to load.</strong> ' +
      "This section renders from the repository's JSON data files. " +
      "Error: " + esc(err && err.message ? err.message : err) + "</div>";
  }

  function fetchJSON(path) {
    return fetch(path, { cache: "no-store" }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status + " for " + path);
      return res.json();
    });
  }

  function basePath() {
    // Pages can live at repo root; data is always ./data relative to page.
    return "data/";
  }

  /* ---------- Master list ---------- */
  function renderMasterList(el) {
    fetchJSON(basePath() + "master_list.json").then(function (entries) {
      var filter = el.getAttribute("data-filter");
      var rows = entries
        .filter(function (e) { return !filter || e.category === filter; })
        .map(function (e) {
          var flags = (e.flags && e.flags.length)
            ? '<div class="notice warn small"><strong>Flag:</strong> ' + e.flags.map(esc).join("<br>") + "</div>"
            : "";
          var notes = e.notes ? '<div class="muted small">' + esc(e.notes) + "</div>" : "";
          return "<tr><td class='mono'>" + esc(e.id) + "</td><td><strong>" + esc(e.claim) +
            "</strong><br><span class='small'>" + esc(e.detail) + "</span>" + flags + notes +
            "</td><td>" + badge(e.status) + "<br><span class='muted small'>" + esc(e.verified_utc) +
            "</span></td><td class='small'>" + sourceLinks(e.sources) + "</td></tr>";
        });
      el.innerHTML = '<div class="table-scroll"><table class="data"><thead><tr>' +
        "<th>ID</th><th>Verified claim</th><th>Status</th><th>Sources (open to re-check)</th>" +
        "</tr></thead><tbody>" + rows.join("") + "</tbody></table></div>" +
        '<p class="muted small">Showing ' + rows.length + " of " + entries.length + ' entries. ' +
        "Every claim links to the source it was checked against.</p>";
    }).catch(function (err) { failVisible(el, err); });
  }

  /* ---------- Teams ---------- */
  function rosterList(team) {
    var items = team.roster.map(function (p) {
      var name = p.real_name ? esc(p.handle) + " (" + esc(p.real_name) + ")" : esc(p.handle);
      return "<li>" + name + ' <span class="muted small">' + esc(p.nation) + "</span></li>";
    });
    items.push("<li><strong>Coach:</strong> " + esc(team.coach.handle) +
      ' <span class="muted small">' + esc(team.coach.nation) + "</span></li>");
    return '<ul class="roster">' + items.join("") + "</ul>";
  }

  function renderTeams(el) {
    fetchJSON(basePath() + "teams.json").then(function (teams) {
      var cards = teams.map(function (t) {
        var flags = (t.flags && t.flags.length)
          ? '<div class="notice warn small"><strong>Flag:</strong> ' + t.flags.map(esc).join("<br>") + "</div>"
          : "";
        return '<div class="card team-card"><h3>' + esc(t.name) +
          ' <span class="muted small">' + esc(t.nation) + " · " + esc(t.route) + "</span></h3>" +
          "<p class='small'><strong>VRS (Sep 16 reveal):</strong> #" + esc(t.vrs_rank_2026_09_16) +
          " &nbsp;·&nbsp; <strong>HLTV observed:</strong> #" + esc(t.hltv_rank_observed) +
          ' <span class="muted">(' + esc(t.hltv_rank_observed_utc) + ")</span></p>" +
          rosterList(t) +
          (t.note ? '<p class="small">' + esc(t.note) + "</p>" : "") + flags +
          '<details><summary class="small">Sources + master list ref (' + esc(t.master_list) + ")</summary>" +
          sourceLinks(t.sources) + "</details></div>";
      });
      el.innerHTML = '<div class="grid-2">' + cards.join("") + "</div>";
    }).catch(function (err) { failVisible(el, err); });
  }

  function renderTeamsTable(el) {
    fetchJSON(basePath() + "teams.json").then(function (teams) {
      var rows = teams.map(function (t) {
        var roster = t.roster.map(function (p) { return p.handle; }).join(", ") + " (coach: " + t.coach.handle + ")";
        return "<tr><td><strong>" + esc(t.name) + "</strong><br><span class='muted small'>" + esc(t.route) +
          "</span></td><td>#" + esc(t.vrs_rank_2026_09_16) + "</td><td>#" + esc(t.hltv_rank_observed) +
          "</td><td class='small'>" + esc(roster) + "</td></tr>";
      });
      el.innerHTML = '<div class="table-scroll"><table class="data"><thead><tr>' +
        "<th>Team</th><th>VRS Sep 16</th><th>HLTV Sep 24</th><th>Roster + coach</th>" +
        "</tr></thead><tbody>" + rows.join("") + "</tbody></table></div>";
    }).catch(function (err) { failVisible(el, err); });
  }

  /* ---------- Matches / feed ---------- */
  function renderMatches(el) {
    fetchJSON(basePath() + "matches.json").then(function (matches) {
      var rows = matches.map(function (m) {
        var fixture = (m.team_a && m.team_b) ? esc(m.team_a) + " vs " + esc(m.team_b) : "—";
        return "<tr><td class='mono'>" + esc(m.id) + "</td><td>" + esc(m.event) + "<br><span class='muted small'>" +
          esc(m.stage) + "</span></td><td>" + fixture + "</td><td>" + (m.score ? esc(m.score) : "—") +
          "</td><td>" + badge(m.status) + "</td><td class='small'>" + esc(m.detail) + "<br>" +
          sourceLinks(m.sources) + "</td></tr>";
      });
      el.innerHTML = '<div class="table-scroll"><table class="data"><thead><tr>' +
        "<th>ID</th><th>Event / stage</th><th>Fixture</th><th>Score</th><th>Status</th><th>Detail + sources</th>" +
        "</tr></thead><tbody>" + rows.join("") + "</tbody></table></div>";
    }).catch(function (err) { failVisible(el, err); });
  }

  /* ---------- Market sources ---------- */
  function renderMarkets(el) {
    fetchJSON(basePath() + "market_sources.json").then(function (srcs) {
      var rows = srcs.map(function (s) {
        var docs = s.docs_url ? '<br><a href="' + esc(s.docs_url) + '" target="_blank" rel="noopener">API docs</a>' : "";
        return "<tr><td><strong>" + esc(s.name) + "</strong><br><span class='muted small'>" + esc(s.kind) +
          "</span><br><a href='" + esc(s.url) + "' target='_blank' rel='noopener' class='small'>Website</a>" + docs +
          "</td><td class='small'>" + esc(s.access) + "</td><td class='small'>" + esc(s.coverage) +
          "</td><td class='small'>" + esc(s.status) + "<br><span class='muted'>checked " + esc(s.last_checked_utc) +
          "</span></td></tr>";
      });
      el.innerHTML = '<div class="table-scroll"><table class="data"><thead><tr>' +
        "<th>Source</th><th>Free access path</th><th>TWC 2026 coverage</th><th>Status</th>" +
        "</tr></thead><tbody>" + rows.join("") + "</tbody></table></div>";
    }).catch(function (err) { failVisible(el, err); });
  }

  /* ---------- Leaderboard (computed from strategies + ledger) ---------- */
  function computeStandings(strategies, ledger) {
    return strategies.map(function (s) {
      var mine = (ledger.entries || []).filter(function (e) { return e.username === s.username; });
      var settled = mine.filter(function (e) { return e.settlement && e.settlement.result; });
      var staked = settled.reduce(function (a, e) { return a + Number(e.stake); }, 0);
      var pnl = settled.reduce(function (a, e) { return a + Number(e.profit); }, 0);
      var wins = settled.filter(function (e) { return e.settlement.result === "win"; }).length;
      return {
        username: s.username,
        strategy: s.strategy,
        start: Number(s.bankroll_start),
        bets: settled.length,
        pending: mine.length - settled.length,
        wins: wins,
        staked: staked,
        pnl: pnl,
        bankroll: Number(s.bankroll_start) + pnl,
        roi: staked > 0 ? (pnl / staked) * 100 : 0
      };
    }).sort(function (a, b) { return b.bankroll - a.bankroll; });
  }

  function fmt(n) { return (Math.round(n * 100) / 100).toFixed(2); }

  function renderLeaderboard(el) {
    Promise.all([
      fetchJSON(basePath() + "strategies.json"),
      fetchJSON(basePath() + "ledger.json")
    ]).then(function (pair) {
      var standings = computeStandings(pair[0], pair[1]);
      var rows = standings.map(function (r, i) {
        var pnlCls = r.pnl > 0 ? "color:var(--good)" : (r.pnl < 0 ? "color:var(--bad)" : "");
        return "<tr><td>#" + (i + 1) + "</td><td><span class='mono'>" + esc(r.username) + "</span> " +
          '<span class="badge sim">SIM</span><br><span class="small">' + esc(r.strategy) + "</span></td>" +
          "<td>" + r.bets + (r.pending ? " (+" + r.pending + " pending)" : "") + "</td><td>" + r.wins +
          "</td><td>" + fmt(r.staked) + "</td><td style='" + pnlCls + "'>" + (r.pnl >= 0 ? "+" : "") + fmt(r.pnl) +
          "</td><td>" + fmt(r.roi) + "%</td><td><strong>" + fmt(r.bankroll) + "</strong></td></tr>";
      });
      el.innerHTML =
        '<div class="notice"><strong>Simulated competition.</strong> All usernames, strategies, stakes and bankrolls are simulated units — no real money, no real wagers. ' +
        "Standings are recomputed live from <span class='mono'>data/ledger.json</span>: bankroll = start + Σ profit.</div>" +
        '<div class="table-scroll"><table class="data"><thead><tr>' +
        "<th>#</th><th>User / strategy</th><th>Settled</th><th>Wins</th><th>Staked</th><th>P/L</th><th>ROI</th><th>Bankroll</th>" +
        "</tr></thead><tbody>" + rows.join("") + "</tbody></table></div>";
      var meta = document.querySelector("[data-ledger-meta]");
      if (meta) meta.textContent = "Ledger: " + pair[1].entries.length + " entries · updated " + pair[1].meta.last_updated_utc + " · " + pair[1].meta.currency;
    }).catch(function (err) { failVisible(el, err); });
  }

  function renderStrategies(el) {
    fetchJSON(basePath() + "strategies.json").then(function (strategies) {
      var cards = strategies.map(function (s) {
        var rules = s.rules.map(function (r) { return "<li>" + esc(r) + "</li>"; }).join("");
        return '<div class="card"><h3><span class="mono">' + esc(s.username) + "</span> " +
          '<span class="badge sim">SIMULATED</span></h3>' +
          "<p><strong>" + esc(s.strategy) + ".</strong> " + esc(s.description) + "</p>" +
          "<ol class='small'>" + rules + "</ol>" +
          "<p class='small'><strong>Starting bankroll:</strong> " + fmt(s.bankroll_start) + " units · " +
          "<strong>Status:</strong> " + esc(s.status) + "</p>" +
          '<p class="muted small">' + esc(s.notes) + "</p></div>";
      });
      el.innerHTML = cards.join("");
    }).catch(function (err) { failVisible(el, err); });
  }

  /* ---------- Ledger ---------- */
  function renderLedger(el) {
    fetchJSON(basePath() + "ledger.json").then(function (ledger) {
      var html = '<div class="notice"><strong>' + esc(ledger.meta.currency) + ".</strong> " +
        esc(ledger.meta.settlement_policy) + "</div>";
      html += "<p class='small muted'>Formula: " + esc(ledger.meta.payout_formula) + " " +
        esc(ledger.meta.prediction_share_conversion) + "</p>";
      if (!ledger.entries.length) {
        html += '<div class="card"><h3>No simulated bets yet — by policy, not by accident</h3>' +
          "<p>" + esc(ledger.meta.note) + "</p>" +
          "<p>When the first verified price is captured (ticker + price + timestamp), every simulated user's exact position will appear here with selection, odds, stake, source, settlement rule, outcome and P/L. See <a href='markets.html'>Markets</a> for the free price sources being watched.</p></div>";
        el.innerHTML = html;
        return;
      }
      var rows = ledger.entries.map(function (e) {
        return "<tr><td class='mono'>" + esc(e.entry_id) + "</td><td class='mono'>" + esc(e.username) +
          "</td><td class='mono'>" + esc(e.match_id) + "</td><td>" + esc(e.market) + "<br><strong>" + esc(e.selection) +
          "</strong></td><td>" + esc(e.decimal_odds) + "</td><td>" + esc(e.stake) + "</td><td class='small'>" +
          esc(e.price_source.venue) + " " + esc(e.price_source.ticker || e.price_source.market_id || "") +
          "<br>" + esc(e.placed_utc) + "</td><td>" + (e.settlement.result ? badge(e.settlement.result === "win" ? "verified" : "unverified") + " " + esc(e.settlement.result) : badge("tbd")) +
          "</td><td>" + esc(e.profit) + "</td></tr>";
      });
      el.innerHTML = html + '<div class="table-scroll"><table class="data"><thead><tr>' +
        "<th>ID</th><th>User</th><th>Match</th><th>Market / selection</th><th>Odds</th><th>Stake</th><th>Price source</th><th>Result</th><th>Profit</th>" +
        "</tr></thead><tbody>" + rows.join("") + "</tbody></table></div>";
    }).catch(function (err) { failVisible(el, err); });
  }

  /* ---------- Feed (latest verified items) ---------- */
  function renderFeed(el) {
    var limit = parseInt(el.getAttribute("data-limit") || "8", 10);
    fetchJSON(basePath() + "master_list.json").then(function (entries) {
      var items = entries.slice(-limit).reverse().map(function (e) {
        return "<li>" + badge(e.status) + " <strong>" + esc(e.claim) + "</strong> " +
          '<span class="muted small">(' + esc(e.id) + " · " + esc(e.verified_utc) + ")</span></li>";
      });
      el.innerHTML = "<ul>" + items.join("") + "</ul>" +
        '<p><a href="master-list.html">Open the full verified master list →</a></p>';
    }).catch(function (err) { failVisible(el, err); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-render]").forEach(function (el) {
      var kind = el.getAttribute("data-render");
      if (kind === "master-list") renderMasterList(el);
      else if (kind === "teams") renderTeams(el);
      else if (kind === "teams-table") renderTeamsTable(el);
      else if (kind === "matches") renderMatches(el);
      else if (kind === "markets") renderMarkets(el);
      else if (kind === "leaderboard") renderLeaderboard(el);
      else if (kind === "strategies") renderStrategies(el);
      else if (kind === "ledger") renderLedger(el);
      else if (kind === "feed") renderFeed(el);
    });
    // Footer timestamps
    document.querySelectorAll("[data-today]").forEach(function (el) {
      el.textContent = "2026-09-24";
    });
  });
})();
