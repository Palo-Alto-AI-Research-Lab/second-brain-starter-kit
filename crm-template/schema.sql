-- CRM schema — the SQLite half of a two-layer CRM.
-- The other half is markdown cards in the vault (see card-template.md).
-- Rule: SQLite holds FACTS AND NUMBERS, markdown holds JUDGEMENT AND STORY.
-- Never duplicate one into the other; cross-reference by `lead_slug`.

-- ---------------------------------------------------------------------------
-- leads — one row per relationship you are actually working
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS leads (
    lead_slug   TEXT PRIMARY KEY,   -- 'marta-costa' — the join key to the markdown card
    title       TEXT,               -- display name
    company     TEXT,
    role        TEXT,
    country     TEXT,

    -- channel identity (one row can carry several; add columns per channel you use)
    handle      TEXT,               -- @username
    crm_tg_id   TEXT,               -- stable numeric id; handles change, ids do not

    -- history: typed by a human, therefore treated as HISTORY, never as truth
    status      TEXT,               -- new / contacted / qualifying / interested /
                                    -- negotiating / won / lost / no-show / refund / stale
    category    TEXT,               -- founder / investor / vc / fund / b2b / kol / service
    first_contact TEXT,             -- ISO date
    last_contact  TEXT,
    last_inbound  TEXT,             -- last time THEY reached us — the honest signal
    n_calls       INTEGER DEFAULT 0,
    lead_msgs     INTEGER DEFAULT 0,

    -- COMPUTED nightly by reference/temperature.py — never typed by a human
    temperature_band      TEXT,     -- Hot / Warm / Lukewarm / Cold / Archived
    reactivation_priority INTEGER,  -- 0..100
    reactivation_band     TEXT,     -- Now / This week / This month / Park
    rp_recency    REAL,             -- the five components are stored so that any
    rp_frequency  REAL,             -- ranking can be explained to the human without
    rp_depth      REAL,             -- re-running the model: "why is this one #1"
    rp_resurgence REAL,
    rp_penalty    REAL,
    temp_reason   TEXT,             -- one-line human-readable trace of the above
    needs_review  INTEGER DEFAULT 0,-- 1 = too thin for arithmetic, hand to an LLM
    retag_ts      TEXT,             -- when the score was last recomputed
    retag_v       INTEGER           -- model version, so a rescore is detectable
);
CREATE INDEX IF NOT EXISTS ix_leads_band ON leads(temperature_band);
CREATE INDEX IF NOT EXISTS ix_leads_pri  ON leads(reactivation_priority DESC);

-- ---------------------------------------------------------------------------
-- people — the identity resolution layer underneath leads
-- ---------------------------------------------------------------------------
-- The same human arrives from a contact export, a chat archive, an investor
-- database and a vault note, four times, spelled four ways. `people` is where
-- they become one entity; `src_*` records WHERE each claim came from so a merge
-- can always be undone.
CREATE TABLE IF NOT EXISTS people (
    id         INTEGER PRIMARY KEY,
    name       TEXT,
    name_key   TEXT,                -- normalized for matching (lowercase, no punctuation)
    handle     TEXT,
    tg_id      INTEGER,
    role       TEXT,
    status     TEXT,
    category   TEXT,

    src_crm      INTEGER DEFAULT 0, -- provenance flags: which sources asserted this person
    src_contacts INTEGER DEFAULT 0,
    src_vault    INTEGER DEFAULT 0,
    src_chat     INTEGER DEFAULT 0,

    lead_slug   TEXT,               -- -> leads.lead_slug   (working relationship)
    vault_slug  TEXT,               -- -> markdown card in the second brain
    dup_of      INTEGER             -- soft merge: point at the survivor, delete nothing
);
CREATE INDEX IF NOT EXISTS ix_people_key ON people(name_key);

-- ---------------------------------------------------------------------------
-- outbound safety — see reference/budget.py
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS send_budget (
    account     TEXT NOT NULL,
    day         TEXT NOT NULL,
    sent        INTEGER NOT NULL DEFAULT 0,
    daily_limit INTEGER NOT NULL,
    PRIMARY KEY (account, day)
);

-- Every single message the agent sent, with a preview. This table is the reason
-- a human can ask "what did you send today" and get an answer instead of a promise.
CREATE TABLE IF NOT EXISTS send_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    account   TEXT NOT NULL,
    day       TEXT NOT NULL,
    ts        TEXT NOT NULL,
    lead_slug TEXT,
    kind      TEXT,                 -- drip / reply / intro / reactivation
    preview   TEXT
);
CREATE INDEX IF NOT EXISTS ix_sendlog_day ON send_log(day);
