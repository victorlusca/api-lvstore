CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_name TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL
            );
CREATE TABLE configuracoes_organizacao (
                id INTEGER PRIMARY KEY,
                sigla TEXT,
                nome TEXT,
                tag TEXT,
                tag_change TEXT,
                tipo TEXT,
                mudar_tag INTEGER
            );
CREATE TABLE configuracoes_servidor (
                id INTEGER PRIMARY KEY,
                guild_id TEXT,
                store_id TEXT,
                pontos_origem_server TEXT,
                pontos_origem_canal TEXT
            );
CREATE TABLE configuracoes_plano (
                id INTEGER PRIMARY KEY,
                premium INTEGER,
                cliente TEXT,
                vencimento INTEGER,
                pix_copia_e_cola TEXT
            , paid_until_ts INTEGER, plan_key TEXT, valor_renovacao REAL, scheduled_plan_key TEXT);
CREATE TABLE cargos_gerais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_name TEXT UNIQUE NOT NULL,
                value TEXT
            );
CREATE TABLE chats_gerais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_name TEXT UNIQUE NOT NULL,
                value TEXT
            );
CREATE TABLE calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_name TEXT UNIQUE NOT NULL,
                value TEXT
            );
CREATE TABLE categorias_gerais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_name TEXT UNIQUE NOT NULL,
                value TEXT
            );
CREATE TABLE logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_name TEXT UNIQUE NOT NULL,
                value TEXT
            );
CREATE TABLE configuracoes_e_numeros (
                id INTEGER PRIMARY KEY,
                acertos_minimos_edital INTEGER,
                meta_diaria_rotas INTEGER,
                delay_rotas INTEGER,
                margem_horas_upamento INTEGER
            );
CREATE TABLE hierarquia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hierarchy_index INTEGER,
                cargo_id INTEGER,
                nome TEXT,
                sigla TEXT,
                horas INTEGER
            , is_superior INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1);
CREATE TABLE api_tokens (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT    NOT NULL UNIQUE,
                label      TEXT    NOT NULL DEFAULT 'default',
                scopes     TEXT    NOT NULL DEFAULT 'admin:*',
                is_active  INTEGER NOT NULL DEFAULT 1,
                created_at TEXT    DEFAULT (datetime('now')),
                last_used  TEXT,
                last_ip    TEXT
            );
CREATE TABLE api_audit_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ts            TEXT    DEFAULT (datetime('now')),
                actor         TEXT,
                ip            TEXT,
                method        TEXT,
                route         TEXT,
                resource_type TEXT,
                resource_key  TEXT,
                old_value     TEXT,
                new_value     TEXT,
                status        INTEGER,
                message       TEXT
            );
CREATE INDEX idx_audit_ts   ON api_audit_log(ts);
CREATE INDEX idx_audit_actor ON api_audit_log(actor);
CREATE INDEX idx_audit_res   ON api_audit_log(resource_type, resource_key);
CREATE TABLE api_flags (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT DEFAULT(datetime('now')));
CREATE TABLE recruitment_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL
        );
CREATE TABLE recruitment_question_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            option_text TEXT NOT NULL,
            is_correct INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(question_id) REFERENCES recruitment_questions(id) ON DELETE CASCADE
        );
CREATE TABLE superior_application_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL
        );
CREATE TABLE api_bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id TEXT NOT NULL UNIQUE,
                token_hash TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                last_seen TEXT,
                last_ip TEXT
            );
CREATE TABLE api_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                payload_json TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                priority INTEGER NOT NULL DEFAULT 100,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                available_at TEXT DEFAULT (datetime('now')),
                locked_at TEXT,
                locked_by TEXT,
                idempotency_key TEXT,
                result_json TEXT,
                last_error TEXT,
                created_by TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
CREATE UNIQUE INDEX idx_api_tasks_idem
                ON api_tasks(bot_id, idempotency_key)
                WHERE idempotency_key IS NOT NULL;
CREATE INDEX idx_api_tasks_poll
                ON api_tasks(bot_id, status, available_at, priority, id);
CREATE TABLE bot_configuration (
                    id INTEGER PRIMARY KEY,
                    bot_token TEXT,
                    manutencao INTEGER DEFAULT 0
                );
