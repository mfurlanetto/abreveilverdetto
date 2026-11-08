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
