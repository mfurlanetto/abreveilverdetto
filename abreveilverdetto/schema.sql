-- Schema del bot. Idempotente: viene eseguito a ogni avvio.

-- Partite di /centocentocento in attesa della risposta "un altro giro?".
CREATE TABLE IF NOT EXISTS c100_games (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT      NOT NULL,
    user_id     BIGINT      NOT NULL,
    value       INTEGER     NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS c100_games_created_at_idx ON c100_games (created_at);

-- Un tentativo al minuto per utente (come nella versione originale).
CREATE TABLE IF NOT EXISTS c100_cooldown (
    user_id  BIGINT PRIMARY KEY,
    last_run TIMESTAMPTZ NOT NULL
);

-- Miglior punteggio del giorno per chat.
CREATE TABLE IF NOT EXISTS c100_daily_best (
    chat_id   BIGINT  NOT NULL,
    day       DATE    NOT NULL,
    user_id   BIGINT  NOT NULL,
    user_name TEXT    NOT NULL,
    value     INTEGER NOT NULL,
    runs      INTEGER NOT NULL,
    PRIMARY KEY (chat_id, day)
);

-- Vittorie (esattamente 100) per utente e chat.
CREATE TABLE IF NOT EXISTS c100_wins (
    chat_id   BIGINT      NOT NULL,
    user_id   BIGINT      NOT NULL,
    user_name TEXT        NOT NULL,
    wins      INTEGER     NOT NULL,
    last_win  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (chat_id, user_id)
);

-- file_id Telegram delle immagini già caricate: evita di ricaricare i file ogni volta.
CREATE TABLE IF NOT EXISTS media_file_ids (
    media_key TEXT PRIMARY KEY,
    file_id   TEXT NOT NULL
);

-- Morra cinese: partite in corso e concluse (eliminate dopo 7 giorni).
CREATE TABLE IF NOT EXISTS morra_games (
    id                BIGSERIAL PRIMARY KEY,
    chat_id           BIGINT      NOT NULL,
    challenger_id     BIGINT      NOT NULL,
    challenger_name   TEXT        NOT NULL,
    target_id         BIGINT,
    target_name       TEXT,
    opponent_id       BIGINT,
    opponent_name     TEXT,
    status            TEXT        NOT NULL,
    challenger_choice TEXT,
    opponent_choice   TEXT,
    challenger_score  INTEGER     NOT NULL DEFAULT 0,
    opponent_score    INTEGER     NOT NULL DEFAULT 0,
    history           TEXT        NOT NULL DEFAULT '',
    created_at        TIMESTAMPTZ NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS morra_games_created_at_idx ON morra_games (created_at);
-- Scadenza della prossima azione e messaggio da cancellare (aggiunte dopo: ALTER idempotenti).
ALTER TABLE morra_games ADD COLUMN IF NOT EXISTS deadline TIMESTAMPTZ;
ALTER TABLE morra_games ADD COLUMN IF NOT EXISTS message_id BIGINT;
-- Partite aperte create prima delle scadenze: valeva "10 minuti dall'ultima mossa".
UPDATE morra_games SET deadline = updated_at + INTERVAL '10 minutes'
    WHERE deadline IS NULL AND status IN ('open', 'playing');
CREATE INDEX IF NOT EXISTS morra_games_deadline_idx ON morra_games (deadline)
    WHERE status IN ('open', 'playing');

-- Morra cinese: vittorie e sconfitte per utente e chat (per /bravitutti).
CREATE TABLE IF NOT EXISTS morra_stats (
    chat_id   BIGINT  NOT NULL,
    user_id   BIGINT  NOT NULL,
    user_name TEXT    NOT NULL,
    wins      INTEGER NOT NULL DEFAULT 0,
    losses    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, user_id)
);

-- Duello: partite in corso e concluse (eliminate dopo 7 giorni).
CREATE TABLE IF NOT EXISTS duel_games (
    id               BIGSERIAL PRIMARY KEY,
    chat_id          BIGINT      NOT NULL,
    challenger_id    BIGINT      NOT NULL,
    challenger_name  TEXT        NOT NULL,
    target_id        BIGINT,
    target_name      TEXT,
    opponent_id      BIGINT,
    opponent_name    TEXT,
    status           TEXT        NOT NULL,
    round            INTEGER     NOT NULL DEFAULT 1,
    challenger_score INTEGER     NOT NULL DEFAULT 0,
    opponent_score   INTEGER     NOT NULL DEFAULT 0,
    history          TEXT        NOT NULL DEFAULT '',
    deadline         TIMESTAMPTZ,
    message_id       BIGINT,
    created_at       TIMESTAMPTZ NOT NULL,
    updated_at       TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS duel_games_created_at_idx ON duel_games (created_at);
CREATE INDEX IF NOT EXISTS duel_games_deadline_idx ON duel_games (deadline)
    WHERE status IN ('open', 'armed', 'fire');

-- Duello: vittorie e sconfitte per utente e chat (per /bravitutti).
CREATE TABLE IF NOT EXISTS duel_stats (
    chat_id   BIGINT  NOT NULL,
    user_id   BIGINT  NOT NULL,
    user_name TEXT    NOT NULL,
    wins      INTEGER NOT NULL DEFAULT 0,
    losses    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, user_id)
);
