-- Aggiunge message_id (UUID), rating e user_feedback a chat_log
-- per il sistema di feedback utente sulle risposte.
-- Migrazione idempotente: sicura da eseguire più volte.

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chat_log' AND column_name = 'message_id'
    ) THEN
        ALTER TABLE chat_log ADD COLUMN message_id UUID;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chat_log' AND column_name = 'rating'
    ) THEN
        ALTER TABLE chat_log ADD COLUMN rating SMALLINT CHECK (rating >= 1 AND rating <= 5);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chat_log' AND column_name = 'user_feedback'
    ) THEN
        ALTER TABLE chat_log ADD COLUMN user_feedback TEXT;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_chatlog_message_id ON chat_log(message_id) WHERE message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chatlog_rating ON chat_log(rating) WHERE rating IS NOT NULL;
