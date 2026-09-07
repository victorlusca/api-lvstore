CREATE TABLE players (
	id INTEGER NOT NULL, 
	"playerName" VARCHAR, 
	"playerID" INTEGER, 
	"playerLogin" VARCHAR, 
	"discordUserID" INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE ("discordUserID")
);
CREATE TABLE supervisor_checkins (
	id INTEGER NOT NULL, 
	"playerName" VARCHAR, 
	"playerID" INTEGER, 
	"playerLogin" VARCHAR, 
	"discordUserID" INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id)
);
CREATE TABLE supervisor_profiles (
	id INTEGER NOT NULL, 
	"discordUserID" INTEGER, 
	available_from VARCHAR, 
	available_to VARCHAR, 
	about_me VARCHAR, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE ("discordUserID")
);
CREATE TABLE staff_actions_summary (
	id INTEGER NOT NULL, 
	discord_user_id INTEGER NOT NULL, 
	advertencias_aplicadas INTEGER NOT NULL, 
	exoneracoes_aplicadas INTEGER NOT NULL, 
	transfs_aceitas INTEGER NOT NULL, 
	transfs_recusadas INTEGER NOT NULL, 
	recrutamentos_qtd INTEGER NOT NULL, 
	media_avaliacoes FLOAT NOT NULL, 
	updated_at DATETIME, tickets_atendidos INTEGER DEFAULT 0, transferencias_aprovadas INTEGER DEFAULT 0, transferencias_recusadas INTEGER DEFAULT 0, avaliacoes_qtd INTEGER DEFAULT 0, pontos_totais INTEGER DEFAULT 0, media_estrelas REAL DEFAULT 0.0, upamentos_feitos INTEGER DEFAULT 0, warnings_applied INTEGER DEFAULT 0, exonerations_applied INTEGER DEFAULT 0, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_staff_actions_summary_discord_user_id ON staff_actions_summary (discord_user_id);
CREATE TABLE attendant_ratings (
	id INTEGER NOT NULL, 
	attendant_id BIGINT NOT NULL, 
	total_stars INTEGER NOT NULL, 
	attendances INTEGER NOT NULL, 
	average FLOAT NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_attendant_ratings_attendant_id ON attendant_ratings (attendant_id);
CREATE TABLE player_warnings (
	id INTEGER NOT NULL, 
	user_id_save INTEGER, 
	game_user_id INTEGER, 
	adv_tipo VARCHAR, 
	motivo VARCHAR, 
	expires_at VARCHAR, 
	message_id INTEGER, 
	PRIMARY KEY (id)
);
CREATE TABLE player_absences (
	id INTEGER NOT NULL, 
	user_id_save INTEGER, 
	reason VARCHAR, 
	sended_at DATETIME, 
	expires_at DATETIME, 
	message_id INTEGER, 
	PRIMARY KEY (id)
);
CREATE TABLE recruiter_ratings (
	id INTEGER NOT NULL, 
	recruiter_discord_id BIGINT NOT NULL, 
	recrutamentos_qtd INTEGER NOT NULL, 
	avaliacoes_qtd INTEGER NOT NULL, 
	media_estrelas FLOAT NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_recruiter_ratings_recruiter_discord_id ON recruiter_ratings (recruiter_discord_id);
CREATE TABLE active_sessions (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	message_id INTEGER NOT NULL, 
	channel_id INTEGER NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_active_sessions_user_id ON active_sessions (user_id);
CREATE TABLE player_hierarchy_progress (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	total_hours VARCHAR, 
	role INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (user_id)
);
CREATE TABLE tickets (
	id INTEGER NOT NULL, 
	channel_id BIGINT NOT NULL, 
	opened_by_id BIGINT NOT NULL, 
	attended_by_id BIGINT, 
	closed_by_id BIGINT, 
	opened_at_ts INTEGER, 
	attended_at_ts INTEGER, 
	closed_at_ts INTEGER, 
	ticket_type VARCHAR(32), 
	transcript_filename VARCHAR(255), 
	transcript_url VARCHAR(500), 
	stars INTEGER, 
	log_message_id BIGINT, transcript_name TEXT, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_tickets_channel_id ON tickets (channel_id);
CREATE TABLE player_points (
	id INTEGER NOT NULL, 
	discord_id BIGINT NOT NULL, 
	game_id INTEGER, 
	total_points INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_player_points_discord_id ON player_points (discord_id);
CREATE TABLE daily_routes (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	routes INTEGER, 
	horas_inicio INTEGER, 
	minutos_inicio INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (user_id)
);
CREATE TABLE total_routes (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	total_routes INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (user_id)
);
CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                event_type TEXT,
                system_key TEXT,
                action_key TEXT,
                actor_discord_id INTEGER,
                actor_name TEXT,
                target_discord_id INTEGER,
                target_game_id INTEGER,
                target_name TEXT,
                details_json TEXT,
                status TEXT,
                message TEXT,
                guild_id INTEGER,
                channel_id INTEGER,
                message_id INTEGER,
                bot_id INTEGER,
                source TEXT,
                severity INTEGER,
                site_user_id INTEGER
            );
CREATE INDEX idx_audit_created_at ON audit_log(created_at);
CREATE INDEX idx_audit_system_key ON audit_log(system_key);
CREATE INDEX idx_audit_action_key ON audit_log(action_key);
CREATE INDEX idx_audit_actor ON audit_log(actor_discord_id);
CREATE INDEX idx_audit_target_discord ON audit_log(target_discord_id);
CREATE INDEX idx_audit_status ON audit_log(status);
CREATE INDEX idx_audit_guild ON audit_log(guild_id);
CREATE INDEX idx_audit_sys_action_created ON audit_log(system_key, action_key, created_at);
CREATE INDEX idx_staff_points ON staff_actions_summary(pontos_totais DESC);
CREATE TABLE global_blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id INTEGER,
                game_id INTEGER,
                player_name TEXT,
                reason TEXT,
                blacklist_type TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                expires_at TEXT,
                created_by_discord_id INTEGER,
                created_by_name TEXT,
                removed_at TEXT,
                removed_by_discord_id INTEGER,
                removed_by_name TEXT,
                notes TEXT,
                details_json TEXT
            );
CREATE INDEX idx_gbl_discord ON global_blacklist(discord_id);
CREATE INDEX idx_gbl_game ON global_blacklist(game_id);
CREATE INDEX idx_gbl_active ON global_blacklist(is_active);
CREATE INDEX idx_gbl_expires ON global_blacklist(expires_at);
CREATE INDEX idx_gbl_created ON global_blacklist(created_at);
CREATE TABLE point_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                message_id INTEGER,
                channel_id INTEGER,
                status TEXT
            );
CREATE TABLE player_total_hours (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                total_hours TEXT
            );
CREATE TABLE bots (
                nome TEXT NOT NULL,
                premium INTEGER NOT NULL DEFAULT 0,
                mensalidade_valor REAL NOT NULL DEFAULT 0,
                mensalidade_vencimento INTEGER,
                cliente TEXT
            );
CREATE TABLE security_whitelist_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_key TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
CREATE TABLE security_whitelist_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_key TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
CREATE UNIQUE INDEX idx_sec_user_action ON security_whitelist_users(action_key, user_id);
CREATE UNIQUE INDEX idx_sec_role_action ON security_whitelist_roles(action_key, role_id);
CREATE TABLE security_whitelist_global_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE security_whitelist_global_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER NOT NULL UNIQUE,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_sec_g_user ON security_whitelist_global_users(user_id);
CREATE INDEX idx_sec_g_role ON security_whitelist_global_roles(role_id);
CREATE TABLE security_systems (
    system_name TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE security_limits (
    guild_id INTEGER NOT NULL,
    system_name TEXT NOT NULL,
    infraction_limit INTEGER NOT NULL,
    punishment_type TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (guild_id, system_name)
);
CREATE TABLE security_infractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    system_name TEXT NOT NULL,
    event_ts TEXT DEFAULT (datetime('now')),
    details_json TEXT
);
CREATE TABLE security_punishments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    system_name TEXT NOT NULL,
    punishment_type TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    details_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE security_processed_events (
    event_key TEXT PRIMARY KEY,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_sec_inf_user_action
    ON security_infractions(guild_id, user_id, action_type);
CREATE INDEX idx_sec_inf_system
    ON security_infractions(guild_id, system_name);
CREATE INDEX idx_sec_punish_user
    ON security_punishments(guild_id, user_id, created_at);
CREATE UNIQUE INDEX idx_tickets_transcript_name ON tickets(transcript_name);
CREATE TABLE transfer_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                status TEXT,
                channel_id INTEGER,
                started_at TEXT,
                decided_at TEXT,
                responsavel_id INTEGER
            );
CREATE TABLE panel_access_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                status TEXT,
                requested_at TEXT,
                decided_at TEXT,
                decided_by INTEGER
            );
CREATE UNIQUE INDEX ix_tickets_transcript_name ON tickets(transcript_name);
CREATE TABLE bot_migrations (key_name TEXT PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now')));
CREATE TABLE BP_Users_Opens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id_save INTEGER UNIQUE,
                horas_inicio INTEGER,
                minutos_inicio INTEGER,
                dia_inicio INTEGER,
                mes_inicio INTEGER
            );
CREATE TABLE BP_Users_Ends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id_save INTEGER UNIQUE,
                horas_end INTEGER,
                minutos_end INTEGER,
                dia_end INTEGER,
                mes_end INTEGER
            );
CREATE TABLE BP_HoursAll (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                total_hours TEXT
            );
